"""The abstract values used by typegraphvm.

An abstract value in effect represents a type. Groups of types are
combined using typegraph and that is what we compute over.
"""

# Because of false positives:
# pylint: disable=unpacking-non-sequence
# pylint: disable=abstract-method
# pytype: disable=attribute-error

import collections
import contextlib
import hashlib
import inspect
import itertools
import logging


from pytype import exceptions
from pytype import function
from pytype import mro
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils

log = logging.getLogger(__name__)
chain = itertools.chain  # pylint: disable=invalid-name
WrapsDict = pytd_utils.WrapsDict  # pylint: disable=invalid-name


# Type parameter names matching the ones in __builtin__.pytd and typing.pytd.
T = "_T"
K = "_K"
V = "_V"
ARGS = "_ARGS"
RET = "_RET"


class ConversionError(ValueError):
  pass


class AsInstance(object):
  """Wrapper, used for marking things that we want to convert to an instance."""

  def __init__(self, cls):
    self.cls = cls


def get_atomic_value(variable, constant_type=None):
  if len(variable.bindings) == 1:
    v, = variable.bindings
    if isinstance(v.data, constant_type or object):
      return v.data
  name = "<any>" if constant_type is None else constant_type.__name__
  raise ConversionError(
      "Cannot get atomic value %s from variable. %s %s"
      % (name, variable, [a.data for a in variable.bindings]))


def get_atomic_python_constant(variable, constant_type=None):
  """Get the concrete atomic Python value stored in this variable.

  This is used for things that are stored in typegraph.Variable, but we
  need the actual data in order to proceed. E.g. function / class defintions.

  Args:
    variable: A typegraph.Variable. It can only have one possible value.
    constant_type: Optionally, the required type of the constant.
  Returns:
    A Python constant. (Typically, a string, a tuple, or a code object.)
  Raises:
    ValueError: If the value in this Variable is purely abstract, i.e. doesn't
      store a Python value, or if it has more than one possible value.
    IndexError: If there is more than one possibility for this value.
  """
  atomic = get_atomic_value(variable)
  return atomic.vm.convert.value_to_constant(atomic, constant_type)


def merge_values(values, vm, formal=False):
  """Merge a collection of values into a single one."""
  if not values:
    return vm.convert.nothing if formal else vm.convert.empty
  elif len(values) == 1:
    return next(iter(values))
  else:
    return Union(values, vm)


def get_views(variables, node, filter_strict=False):
  """Get all possible views of the given variables at a particular node.

  Args:
    variables: The variables.
    node: The node.
    filter_strict: If True, emit a view only when node.HasCombination is
      satisfied; else, use the faster node.CanHaveCombination.

  Yields:
    A variable->binding dictionary.
  """
  try:
    combinations = utils.deep_variable_product(variables)
  except utils.TooComplexError:
    combinations = ((var.AddBinding(node.program.default_data, [], node)
                     for var in variables),)
  for combination in combinations:
    view = {value.variable: value for value in combination}
    combination = view.values()
    check = node.HasCombination if filter_strict else node.CanHaveCombination
    if not check(combination):
      log.info("Skipping combination %r", combination)
      continue
    yield view


def get_signatures(func):
  if isinstance(func, PyTDFunction):
    return [sig.signature for sig in func.signatures]
  elif isinstance(func, InterpreterFunction):
    return [func.signature]
  elif isinstance(func, BoundFunction):
    sigs = get_signatures(func.underlying)
    return [sig.drop_first_parameter() for sig in sigs]  # drop "self"
  else:
    raise NotImplementedError(func.__class__.__name__)


class AtomicAbstractValue(object):
  """A single abstract value such as a type or function signature.

  This is the base class of the things that appear in Variables. It represents
  an atomic object that the abstract interpreter works over just as variables
  represent sets of parallel options.

  Conceptually abstract values represent sets of possible concrete values in
  compact form. For instance, an abstract value with .__class__ = int represents
  all ints.
  """

  _value_id = 0  # for pretty-printing
  formal = False  # is this type non-instantiable?

  def __init__(self, name, vm):
    """Basic initializer for all AtomicAbstractValues."""
    assert hasattr(vm, "program"), type(self)
    self.vm = vm
    self.mro = []
    self.cls = None
    AtomicAbstractValue._value_id += 1
    self.id = AtomicAbstractValue._value_id
    self.name = name
    self.module = None
    self.official_name = None
    self.template = ()
    self.late_annotations = {}

  @property
  def full_name(self):
    return (self.module + "." if self.module else "") + self.name

  def __repr__(self):
    return self.name

  def default_mro(self):
    return [self, self.vm.convert.object_type.data[0]]

  def get_fullhash(self):
    """Hash this value and all of its children."""
    m = hashlib.md5()
    seen_ids = set()
    stack = [self]
    while stack:
      data = stack.pop()
      data_id = id(data)
      if data_id in seen_ids:
        continue
      seen_ids.add(data_id)
      m.update(str(data_id))
      for mapping in data.get_children_maps():
        m.update(str(mapping.changestamp))
        stack.extend(mapping.data)
    return m.digest()

  def get_children_maps(self):
    """Get this value's dictionaries of children.

    Returns:
      A sequence of dictionaries from names to child values.
    """
    return ()

  def get_type_parameter(self, node, name):
    del name
    return self.vm.convert.create_new_unsolvable(node)

  def property_get(self, callself, callcls):  # pylint: disable=unused-argument
    """Bind this value to the given self and class.

    This function is similar to __get__ except at the abstract level. This does
    not trigger any code execution inside the VM. See __get__ for more details.

    Args:
      callself: The Variable that should be passed as self when the call is
        made. None if this is class call.
      callcls: The Variable that should be used as the class when the call is
        made.

    Returns:
      Another abstract value that should be returned in place of this one. The
      default implementation returns self, so this can always be called safely.
    """
    return self

  def get_special_attribute(self, unused_node, name, unused_valself):
    """Fetch a special attribute (e.g., __get__, __iter__)."""
    if name == "__class__":
      return self.get_class()
    return None

  def call(self, node, func, args):
    """Call this abstract value with the given arguments.

    The posargs and namedargs arguments may be modified by this function.

    Args:
      node: The CFGNode calling this function
      func: The typegraph.Binding containing this function.
      args: Arguments for the call.
    Returns:
      A tuple (cfg.Node, typegraph.Variable). The CFGNode corresponds
      to the function's "return" statement(s).
    Raises:
      FailedFunctionCall

    Make the call as required by this specific kind of atomic value, and make
    sure to annotate the results correctly with the origins (val and also other
    values appearing in the arguments).
    """
    raise NotImplementedError(self.__class__.__name__)

  def is_closure(self):
    """Return whether this is a closure. Overridden by subclasses.

    This can only return True for InterpreterFunction and NativeFunction
    (i.e., at the time of this writing, never for functions e.g. from PyTD,
    which doesn't know about closures), and only if they bind variables from
    their outer scope. Inner functions not binding anything are not considered a
    closure.

    Returns:
      True if this is a closure.
    """
    return False

  def register_instance(self, instance):  # pylint: disable=unused-arg
    """Treating self as a class definition, register an instance of it.

    This is used for keeping merging call records on instances when generating
    the formal definition of a class.

    Args:
      instance: An instance of this class (as an AtomicAbstractValue)
    """
    pass  # overridden by InterpreterClass and TupleClass

  def get_class(self):
    """Return the class of this object. Equivalent of x.__class__ in Python."""
    raise NotImplementedError(self.__class__.__name__)

  def get_instance_type(self, node=None, instance=None, seen=None, view=None):
    """Get the type an instance of us would have."""
    return self.vm.convert.pytd_convert.value_instance_to_pytd_type(
        node, self, instance, seen, view)

  def to_type(self, node=None, seen=None, view=None):
    """Get a PyTD type representing this object, as seen at a node."""
    return self.vm.convert.pytd_convert.value_to_pytd_type(
        node, self, seen, view)

  def to_detailed_type(self, node=None, seen=None, view=None):
    return self.vm.convert.pytd_convert.value_to_detailed_pytd_type(
        node, self, seen, view)

  def to_pytd_def(self, node, name):
    """Get a PyTD definition for this object."""
    return self.vm.convert.pytd_convert.value_to_pytd_def(node, self, name)

  def get_default_type_key(self):
    """Gets a default type key. See get_type_key."""
    return type(self)

  def get_type_key(self, seen=None):  # pylint: disable=unused-argument
    """Build a key from the information used to perform type matching.

    Get a hashable object containing this value's type information. Type keys
    are only compared amongst themselves, so we don't care what the internals
    look like, only that values with different types *always* have different
    type keys and values with the same type preferably have the same type key.

    Args:
      seen: The set of values seen before while computing the type key.

    Returns:
      A hashable object built from this value's type information.
    """
    return self.get_default_type_key()

  def instantiate(self, node, container=None):
    del container
    return Instance(self.to_variable(node), self.vm).to_variable(node)

  def to_variable(self, node):
    """Build a variable out of this abstract value.

    Args:
      node: The current CFG node.
    Returns:
      A typegraph.Variable.
    Raises:
      ValueError: If origins is an empty sequence. This is to prevent you from
        creating variables that have no origin and hence can never be used.
    """
    v = self.vm.program.NewVariable()
    v.AddBinding(self, source_set=[], where=node)
    return v

  def has_varargs(self):
    """Return True if this is a function and has a *args parameter."""
    return False

  def has_kwargs(self):
    """Return True if this is a function and has a **kwargs parameter."""
    return False

  def _unique_parameters(self):
    """Get unique parameter subtypes as variables.

    This will retrieve 'children' of this value that contribute to the
    type of it. So it will retrieve type parameters, but not attributes. To
    keep the number of possible combinations reasonable, when we encounter
    multiple instances of the same type, we include only one.

    Returns:
      A list of variables.
    """
    return [self.cls] if self.cls else []

  def unique_parameter_values(self):
    """Get unique parameter subtypes as bindings.

    Like _unique_parameters, but returns bindings instead of variables.

    Returns:
      A list of list of bindings.
    """
    # TODO(rechen): Remember which values were merged under which type keys so
    # we don't have to recompute this information in match_value_against_type.
    return [{value.data.get_type_key(): value
             for value in parameter.bindings}.values()
            for parameter in self._unique_parameters()]

  def compatible_with(self, logical_value):  # pylint: disable=unused-argument
    """Returns the conditions under which the value could be True or False.

    Args:
      logical_value: Either True or False.

    Returns:
      False: If the value could not evaluate to logical_value under any
          circumstance (i.e. value is the empty list and logical_value is True).
      True: If it is possible for the value to evaluate to the logical_value,
          and any ambiguity cannot be described by additional bindings.
      DNF: A list of lists of bindings under which the value can evaluate to
          the logical value.  For example, isinstance() could be reduced
          to the set of bindings that would satisfy th isinstance() condition.
    """
    # By default a value is ambiguous - if could potentially evaluate to
    # either True or False, thus we return True here regardless of
    # logical_value.
    return True

  def update_official_name(self, _):
    """Update the official name."""
    pass

  def cmp_eq(self, _):
    """Do special handling of the equality operator."""
    return None


class Empty(AtomicAbstractValue):
  """An empty value.

  These values represent items extracted from empty containers. Because of false
  positives in flagging containers as empty (consider:
    x = []
    def initialize():
      populate(x)
    def f():
      iterate(x)
  ), we treat these values as placeholders that we can do anything with, similar
  to Unsolvable, with the difference that they eventually convert to
  NothingType so that cases in which they are truly empty are discarded (see:
    x = ...  # type: List[nothing] or Dict[int, str]
    y = [i for i in x]  # The type of i is int; y is List[int]
  ). On the other hand, if Empty is the sole type candidate, we assume that the
  container was populated elsewhere:
    x = []
    def initialize():
      populate(x)
    def f():
      return x[0]  # Oops! The return type should be Any rather than nothing.
  The nothing -> anything conversion happens in
  convert.Converter._function_to_def and infer.CallTracer.pytd_for_types.
  """

  def __init__(self, vm):
    super(Empty, self).__init__("empty", vm)

  def get_special_attribute(self, node, name, valself):
    del name, valself
    return self.vm.convert.unsolvable.to_variable(node)

  def call(self, node, func, args):
    del func, args
    return node, self.vm.convert.unsolvable.to_variable(node)

  def get_class(self):
    return self.vm.convert.unsolvable.to_variable(self.vm.root_cfg_node)


class MixinMeta(type):
  """Metaclass for mix-ins."""

  def __init__(cls, name, superclasses, *args, **kwargs):
    super(MixinMeta, cls).__init__(name, superclasses, *args, **kwargs)
    for sup in superclasses:
      if hasattr(sup, "overloads"):
        for method in sup.overloads:
          if method not in cls.__dict__:
            setattr(cls, method, getattr(sup, method))

  def super(cls, method):
    """Imitate super() in a mix-in.

    This method is a substitute for
      super(MixinClass, self).overloaded_method(arg),
    which we can't use because mix-ins appear at the end of the MRO. It should
    be called as
      MixinClass.super(self.overloaded_method)(arg)
    . It works by finding the class on which MixinMeta.__init__ set
    MixinClass.overloaded_method and calling super() on that class.

    Args:
      method: The method in the mix-in.
    Returns:
      The method overloaded by 'method'.
    """
    for supercls in type(method.__self__).__mro__:
      # Fetch from __dict__ rather than using getattr() because we only want
      # to consider methods defined on supercls itself (not on a parent).
      m = supercls.__dict__.get(method.__name__)
      # m.im_class differs from supercls if m was set by MixinMeta.__init__.
      if getattr(m, "im_class", None) is cls:
        method_cls = supercls
        break
    return getattr(super(method_cls, method.__self__), method.__name__)


class PythonConstant(object):
  """A mix-in for storing actual Python constants, not just their types.

  This is used for things that are stored in typegraph.Variable, but where we
  may need the actual data in order to proceed later. E.g. function / class
  definitions, tuples. Also, potentially: Small integers, strings (E.g. "w",
  "r" etc.).
  """

  __metaclass__ = MixinMeta
  overloads = ("__repr__", "cmp_eq", "compatible_with",)

  def init_mixin(self, pyval):
    """Mix-in equivalent of __init__."""
    self.pyval = pyval

  def str_of_constant(self, printer):
    """Get a string representation of this constant.

    Args:
      printer: An AtomicAbstractValue -> str function that will be used to
        print abstract values.

    Returns:
      A string of self.pyval.
    """
    del printer
    return repr(self.pyval)

  def __repr__(self):
    return "<v%d %s %s>" % (self.id, self.name, self.str_of_constant(str))

  def cmp_eq(self, other):
    if (self.pyval.__class__ in self.vm.convert.primitive_classes and
        isinstance(other, PythonConstant) and
        other.pyval.__class__ in self.vm.convert.primitive_classes):
      return self.pyval == other.pyval
    return None

  def compatible_with(self, logical_value):
    return bool(self.pyval) == logical_value


class TypeParameter(AtomicAbstractValue):
  """Parameter of a type."""

  formal = True

  def __init__(self, name, vm, constraints=(), bound=None,
               covariant=False, contravariant=False):
    super(TypeParameter, self).__init__(name, vm)
    self.constraints = constraints
    self.bound = bound
    self.covariant = covariant
    self.contravariant = contravariant

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return (self.name == other.name and
              self.constraints == other.constraints and
              self.bound == other.bound and
              self.covariant == other.covariant and
              self.contravariant == other.contravariant)
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash((self.name, self.constraints, self.bound, self.covariant,
                 self.contravariant))

  def __repr__(self):
    return "TypeParameter(%r, constraints=%r)" % (self.name, self.constraints)

  def instantiate(self, node, container=None):
    var = self.vm.program.NewVariable()
    if container:
      instance = TypeParameterInstance(self, container, self.vm)
      return instance.to_variable(node)
    else:
      for c in self.constraints:
        var.PasteVariable(c.instantiate(node, container), node)
    if not var.bindings:
      var.AddBinding(self.vm.convert.unsolvable, [], node)
    return var

  def update_official_name(self, name):
    if self.name != name:
      message = "TypeVar(%r) must be stored as %r, not %r" % (
          self.name, self.name, name)
      self.vm.errorlog.invalid_typevar(self.vm.frames, message)

  def get_class(self):
    return self.to_variable(self.vm.root_cfg_node)


class TypeParameterInstance(AtomicAbstractValue):
  """An instance of a type parameter."""

  def __init__(self, param, instance, vm):
    super(TypeParameterInstance, self).__init__(param.name, vm)
    self.param = param
    self.instance = instance

  def get_class(self):
    return self.param.to_variable(self.vm.root_cfg_node)

  def __repr__(self):
    return "TypeParameterInstance(%r)" % self.name


class SimpleAbstractValue(AtomicAbstractValue):
  """A basic abstract value that represents instances.

  This class implements instances in the Python sense. Instances of the same
  class may vary.

  Note that the cls attribute will point to another abstract value that
  represents the class object itself, not to some special type representation.
  """
  is_lazy = False

  def __init__(self, name, vm):
    """Initialize a SimpleAbstractValue.

    Args:
      name: Name of this value. For debugging and error reporting.
      vm: The TypegraphVirtualMachine to use.
    """
    super(SimpleAbstractValue, self).__init__(name, vm)
    self.members = utils.MonitorDict()
    self.type_parameters = utils.LazyAliasingMonitorDict()
    self.maybe_missing_members = False
    # The latter caches the result of get_type_key. This is a recursive function
    # that has the potential to generate too many calls for large definitions.
    self._cached_type_key = (
        (self.members.changestamp, self.type_parameters.changestamp), None)

  def get_children_maps(self):
    return (self.type_parameters, self.members)

  def get_type_parameter(self, node, name):
    """Get the typegraph.Variable representing the type parameter of self.

    This will be a typegraph.Variable made up of values that have been used in
    place of this type parameter.

    Args:
      node: The current CFG node.
      name: The name of the type parameter.
    Returns:
      A Variable which may be empty.
    """
    param = self.type_parameters.get(name)
    if not param:
      log.info("Creating new empty type param %s", name)
      param = self.vm.program.NewVariable([], [], node)
      self.type_parameters[name] = param
    return param

  def merge_type_parameter(self, node, name, value):
    """Set the value of a type parameter.

    This will always add to the type_parameter unlike set_attribute which will
    replace value from the same basic block. This is because type parameters may
    be affected by a side effect so we need to collect all the information
    regardless of multiple assignments in one basic block.

    Args:
      node: The current CFG node.
      name: The name of the type parameter.
      value: The value that is being used for this type parameter as a Variable.
    """
    log.info("Modifying type param %s", name)
    if name in self.type_parameters:
      self.type_parameters[name].PasteVariable(value, node)
    else:
      self.type_parameters[name] = value

  def initialize_type_parameter(self, node, name, value):
    assert isinstance(name, str)
    assert name not in self.type_parameters
    log.info("Initializing type param %s: %r", name, value.data)
    self.type_parameters[name] = self.vm.program.NewVariable(
        value.data, [], node)

  def init_type_parameters(self, *names):
    """Initialize the named type parameters to nothing (empty)."""
    self.type_parameters = utils.LazyAliasingMonitorDict(
        (name, self.vm.program.NewVariable()) for name in names)

  def load_lazy_attribute(self, name):
    """Load the named attribute into self.members."""
    if name not in self.members and name in self._member_map:
      variable = self._convert_member(name, self._member_map[name])
      assert isinstance(variable, typegraph.Variable)
      self.members[name] = variable

  def call(self, node, _, args):
    self_var = self.to_variable(node)
    node, var = self.vm.attribute_handler.get_attribute(
        node, self, "__call__", self_var.bindings[0])
    if var is not None and var.bindings:
      return self.vm.call_function(node, var, args)
    elif self.cls and self.cls.data == self.vm.convert.none_type.data:
      raise NoneNotCallable()
    else:
      raise NotCallable(self)

  def __repr__(self):
    if self.cls:
      cls = self.cls.data[0]
      return "<v%d %s [%r]>" % (self.id, self.name, cls)
    else:
      return "<v%d %s>" % (self.id, self.name)

  def to_variable(self, node):
    return super(SimpleAbstractValue, self).to_variable(node)

  def get_class(self):
    # See Py_TYPE() in Include/object.h
    if self.cls:
      return self.cls
    elif isinstance(self, (AnnotationClass, Class)):
      return self.vm.convert.type_type

  def set_class(self, node, var):
    """Set the __class__ of an instance, for code that does "x.__class__ = y."""
    if self.cls:
      self.cls.PasteVariable(var, node)
    else:
      self.cls = var
    for cls in var.data:
      cls.register_instance(self)
    return node

  def get_type_key(self, seen=None):
    cached_changestamps, saved_key = self._cached_type_key
    if saved_key and cached_changestamps == (self.members.changestamp,
                                             self.type_parameters.changestamp):
      return saved_key
    if not seen:
      seen = set()
    seen.add(self)
    key = set()
    if self.cls:
      key.update(self.cls.data)
    for name, var in self.type_parameters.items():
      subkey = frozenset(value.data.get_default_type_key() if value.data in seen
                         else value.data.get_type_key(seen)
                         for value in var.bindings)
      key.add((name, subkey))
    if key:
      type_key = frozenset(key)
    else:
      type_key = super(SimpleAbstractValue, self).get_type_key()
    self._cached_type_key = (
        (self.members.changestamp, self.type_parameters.changestamp), type_key)
    return type_key

  def _unique_parameters(self):
    parameters = super(SimpleAbstractValue, self)._unique_parameters()
    parameters.extend(self.type_parameters.values())
    return parameters


class Instance(SimpleAbstractValue):
  """An instance of some object."""

  # Fully qualified names of types that are parameterized containers.
  _CONTAINER_NAMES = set([
      "__builtin__.list", "__builtin__.set", "__builtin__.frozenset"])

  def __init__(self, clsvar, vm):
    super(Instance, self).__init__(clsvar.data[0].name, vm)
    self.cls = clsvar
    for cls in clsvar.data:
      cls.register_instance(self)
      bad_names = set()
      for base in cls.mro:
        if isinstance(base, ParameterizedClass):
          if isinstance(base, TupleClass):
            if isinstance(self, Tuple):
              # Tuple.__init__ initializes T.
              params = []
            else:
              params = [(T, base.type_parameters[T])]
          elif isinstance(base, Callable):
            params = [(ARGS, base.type_parameters[ARGS]),
                      (RET, base.type_parameters[RET])]
          else:
            params = base.type_parameters.items()
          for name, param in params:
            if isinstance(param, TypeParameter):
              if name == param.name:
                continue
              # We have type parameter renaming, e.g.,
              #  class List(Generic[T]): pass
              #  class Foo(List[U]): pass
              try:
                self.type_parameters.add_alias(name, param.name)
              except utils.AliasingDictConflictError:
                bad_names |= {name, param.name}
            else:
              # We have either a non-formal parameter, e.g.,
              # class Foo(List[int]), or a non-1:1 parameter mapping, e.g.,
              # class Foo(List[K or V]). Initialize the corresponding instance
              # parameter appropriately.
              if name not in self.type_parameters:
                # TODO(rechen): We should be able to assert that either the
                # param name is not in type_parameters or the new param is equal
                # to the one that was previously added, but we first need to
                # change the parser to not accept things like
                #   class A(List[str], Sequence[int]): ...
                self.type_parameters.add_lazy_item(
                    name, param.instantiate, self.vm.root_cfg_node, self)
      # We can't reliably track changes to type parameters involved in naming
      # conflicts, so we'll set all of them to unsolvable.
      node = self.vm.root_cfg_node
      for name in bad_names:
        self.merge_type_parameter(
            node, name, self.vm.convert.create_new_unsolvable(node))

  def make_template_unsolvable(self, template, node):
    for formal in template:
      self.initialize_type_parameter(
          node, formal.name, self.vm.convert.unsolvable.to_variable(node))

  def compatible_with(self, logical_value):  # pylint: disable=unused-argument
    # Containers with unset parameters and NoneType instances cannot match True.
    name = self._get_full_name()
    if logical_value and name in Instance._CONTAINER_NAMES:
      return (T in self.type_parameters and
              bool(self.type_parameters[T].bindings))
    elif name == "__builtin__.NoneType":
      return not logical_value
    return True

  def _get_full_name(self):
    try:
      return get_atomic_value(self.get_class()).full_name
    except ConversionError:
      return None


class HasSlots(object):
  """Mix-in for overriding slots with custom methods.

  This makes it easier to emulate built-in classes like dict which need special
  handling of some magic methods (__setitem__ etc.)
  """

  __metaclass__ = MixinMeta
  overloads = ("get_special_attribute",)

  def init_mixin(self):
    self._slots = {}
    self._super = {}
    self._function_cache = {}

  def make_native_function(self, name, method):
    key = (name, method)
    if key not in self._function_cache:
      self._function_cache[key] = NativeFunction(name, method, self.vm)
    return self._function_cache[key]

  def set_slot(self, name, method):
    """Add a new slot to this value."""
    assert name not in self._slots, "slot %s already occupied" % name
    _, attr = self.vm.attribute_handler.get_attribute(
        self.vm.root_cfg_node, self, name,
        self.to_variable(self.vm.root_cfg_node).bindings[0])
    self._super[name] = attr
    f = self.make_native_function(name, method)
    self._slots[name] = f.to_variable(self.vm.root_cfg_node)

  def call_pytd(self, node, name, *args):
    """Call the (original) pytd version of a method we overwrote."""
    return self.vm.call_function(node, self._super[name], FunctionArgs(args))

  def get_special_attribute(self, node, name, valself):
    if name in self._slots:
      attr = self.vm.program.NewVariable()
      additional_sources = {valself} if valself else None
      attr.PasteVariable(self._slots[name], node, additional_sources)
      return attr
    return HasSlots.super(self.get_special_attribute)(node, name, valself)


class List(Instance, PythonConstant):
  """Representation of Python 'list' objects."""

  def __init__(self, content, vm):
    super(List, self).__init__(vm.convert.list_type, vm)
    PythonConstant.init_mixin(self, content)
    combined_content = vm.convert.build_content(content)
    self.initialize_type_parameter(vm.root_cfg_node, T, combined_content)
    self.could_contain_anything = False

  def str_of_constant(self, printer):
    return "[%s]" % ", ".join(" or ".join(printer(v) for v in val.data)
                              for val in self.pyval)

  def __repr__(self):
    if self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return PythonConstant.__repr__(self)

  def merge_type_parameter(self, node, name, value):
    self.could_contain_anything = True
    super(List, self).merge_type_parameter(node, name, value)

  def compatible_with(self, logical_value):
    return (self.could_contain_anything or
            PythonConstant.compatible_with(self, logical_value))


class Tuple(Instance, PythonConstant):
  """Representation of Python 'tuple' objects."""

  def __init__(self, content, vm):
    combined_content = vm.convert.build_content(content)
    class_params = {name: vm.convert.merge_classes(vm.root_cfg_node,
                                                   instance_param.data)
                    for name, instance_param in
                    tuple(enumerate(content)) + ((T, combined_content),)}
    cls = TupleClass(vm.convert.tuple_type.bindings[0].data, class_params, vm)
    super(Tuple, self).__init__(cls.to_variable(vm.root_cfg_node), vm)
    self.initialize_type_parameter(vm.root_cfg_node, T, combined_content)
    PythonConstant.init_mixin(self, content)
    self.tuple_length = len(self.pyval)

  def str_of_constant(self, printer):
    content = ", ".join(" or ".join(printer(v) for v in val.data)
                        for val in self.pyval)
    if self.tuple_length == 1:
      content += ","
    return "(%s)" % content

  def cmp_eq(self, other):
    if isinstance(other, Tuple) and self.tuple_length != other.tuple_length:
      return False
    return None

  def _unique_parameters(self):
    parameters = super(Tuple, self)._unique_parameters()
    parameters.extend(self.pyval)
    return parameters


class Dict(Instance, HasSlots, PythonConstant, WrapsDict("pyval")):
  """Representation of Python 'dict' objects.

  It works like __builtins__.dict, except that, for string keys, it keeps track
  of what got stored.
  """

  def __init__(self, vm):
    super(Dict, self).__init__(vm.convert.dict_type, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__contains__", self.contains_slot)
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__setitem__", self.setitem_slot)
    self.set_slot("setdefault", self.setdefault_slot)
    self.set_slot("update", self.update_slot)
    self.init_type_parameters(K, V)
    self.could_contain_anything = False
    PythonConstant.init_mixin(self, {})

  def str_of_constant(self, printer):
    return str({name: " or ".join(printer(v) for v in value.data)
                for name, value in self.pyval.items()})

  def __repr__(self):
    if self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return PythonConstant.__repr__(self)

  def getitem_slot(self, node, name_var):
    """Implements the __getitem__ slot."""
    results = []
    unresolved = False
    if not self.could_contain_anything:
      for val in name_var.bindings:
        try:
          name = self.vm.convert.value_to_constant(val.data, str)
        except ConversionError:
          unresolved = True
        else:
          try:
            results.append(self.pyval[name])
          except KeyError:
            unresolved = True
            raise DictKeyMissing(name)
    node, ret = self.call_pytd(node, "__getitem__", name_var)
    if unresolved or self.could_contain_anything:
      # We *do* know the overall type of the values through the "V" type
      # parameter, even if we don't know the exact type of self[name]. So let's
      # just use the (less accurate) value from pytd.
      results.append(ret)
    return node, self.vm.join_variables(node, results)

  def set_str_item(self, node, name, value_var):
    self.merge_type_parameter(node, K, self.vm.convert.build_string(node, name))
    self.merge_type_parameter(node, V, value_var)
    if name in self.pyval:
      self.pyval[name].PasteVariable(value_var, node)
    else:
      self.pyval[name] = value_var
    return node

  def setitem(self, node, name_var, value_var):
    assert isinstance(name_var, typegraph.Variable)
    assert isinstance(value_var, typegraph.Variable)
    for val in name_var.bindings:
      try:
        name = self.vm.convert.value_to_constant(val.data, str)
      except ConversionError:
        # Now the dictionary is abstract: We don't know what it contains
        # anymore. Note that the below is not a variable, so it'll affect
        # all branches.
        self.could_contain_anything = True
        continue
      if name in self.pyval:
        self.pyval[name].PasteVariable(value_var, node)
      else:
        self.pyval[name] = value_var

  def setitem_slot(self, node, name_var, value_var):
    """Implements the __setitem__ slot."""
    self.setitem(node, name_var, value_var)
    return self.call_pytd(node, "__setitem__", name_var, value_var)

  def setdefault_slot(self, node, name_var, value_var=None):
    if value_var is None:
      value_var = self.vm.convert.build_none(node)
    # We don't have a good way of modelling the exact setdefault behavior -
    # whether the key already exists might depend on a code path, so setting it
    # again should depend on an if-splitting condition, but we don't support
    # negative conditions.
    self.setitem(node, name_var, value_var)
    return self.call_pytd(node, "setdefault", name_var, value_var)

  def contains_slot(self, node, key_var):
    if self.could_contain_anything:
      value = None
    else:
      try:
        str_key = get_atomic_python_constant(key_var, str)
      except ConversionError:
        value = None
      else:
        value = str_key in self.pyval
    return node, self.vm.convert.build_bool(node, value)

  def update_slot(self, node, *args, **kwargs):
    posargs_handled = False
    if len(args) == 1:
      arg_data = args[0].Data(node)
      if len(arg_data) == 1:
        self.update(node, arg_data[0])
        posargs_handled = True
    elif not args:
      posargs_handled = True
    self.update(node, kwargs)
    if not posargs_handled:
      self.could_contain_anything = True
      return self.call_pytd(node, "update", *args)
    else:
      return node, self.vm.convert.none.to_variable(node)

  def update(self, node, other_dict, omit=()):
    if isinstance(other_dict, (Dict, dict)):
      for key, value in other_dict.items():
        # TODO(kramm): sources
        if key not in omit:
          self.set_str_item(node, key, value)
      if isinstance(other_dict, Dict):
        k = other_dict.get_type_parameter(node, K)
        v = other_dict.get_type_parameter(node, V)
        self.merge_type_parameter(node, K, k)
        self.merge_type_parameter(node, V, v)
        self.could_contain_anything |= other_dict.could_contain_anything
    else:
      assert isinstance(other_dict, AtomicAbstractValue)
      unsolvable = self.vm.convert.create_new_unsolvable(node)
      self.merge_type_parameter(node, K, unsolvable)
      self.merge_type_parameter(node, V, unsolvable)
      self.could_contain_anything = True

  def cmp_eq(self, other):
    if (not self.could_contain_anything and isinstance(other, Dict) and
        not other.could_contain_anything and
        set(self.pyval) != set(other.pyval)):
      return False
    return None

  def compatible_with(self, logical_value):
    if self.could_contain_anything:
      # Always compatible with False.  Compatible with True only if type
      # parameters have been established (meaning that the dict can be
      # non-empty).
      return not logical_value or bool(self.type_parameters[K].bindings)
    else:
      return PythonConstant.compatible_with(self, logical_value)


class AnnotationClass(SimpleAbstractValue, HasSlots):
  """Base class of annotations that can be parameterized."""

  def __init__(self, name, vm):
    super(AnnotationClass, self).__init__(name, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)

  @staticmethod
  def _maybe_extract_tuple(node, t):
    """Returns a tuple of Variables."""
    values = t.Data(node)
    if len(values) > 1:
      return (t,)
    v, = values
    if not isinstance(v, Tuple):
      return (t,)
    return v.pyval

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = self._maybe_extract_tuple(node, slice_var)
    inner, ends_with_ellipsis = self._build_inner(slice_content)
    value = self._build_value(node, tuple(inner), ends_with_ellipsis)
    return node, value.to_variable(node)

  def _build_inner(self, slice_content):
    """Build the list of parameters."""
    inner = []
    ends_with_ellipsis = False
    for var in slice_content:
      if len(var.bindings) > 1:
        self.vm.errorlog.ambiguous_annotation(self.vm.frames, var.data)
        inner.append(self.vm.convert.unsolvable)
      else:
        val = var.bindings[0].data
        if val is self.vm.convert.ellipsis:
          # An ellipsis is usually a shorthand for "Any", so we turn it into an
          # unsolvable. However, we also need to know if an ellipsis was at the
          # end of the parameters list, since in that case it can instead
          # indicate a homogeneous container.
          if len(inner) == len(slice_content) - 1:
            ends_with_ellipsis = True
          inner.append(self.vm.convert.unsolvable)
        else:
          inner.append(val)
    return inner, ends_with_ellipsis

  def _build_value(self, node, inner, ends_with_ellipsis):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return "AnnotationClass(%s)" % self.name


class AnnotationContainer(AnnotationClass):
  """Implementation of X[...] for annotations."""

  def __init__(self, name, vm, base_cls):
    super(AnnotationContainer, self).__init__(name, vm)
    self.base_cls = base_cls

  def _get_value_info(self, inner, ends_with_ellipsis):
    template = tuple(t.name for t in self.base_cls.template)
    if ends_with_ellipsis:
      inner = inner[:-1]
    return template, inner, ParameterizedClass

  def _build_value(self, node, inner, ends_with_ellipsis):
    template, inner, abstract_class = self._get_value_info(
        inner, ends_with_ellipsis)
    if len(inner) > len(template):
      error = "Expected %d parameter(s), got %d" % (len(template), len(inner))
      self.vm.errorlog.invalid_annotation(self.vm.frames, self, error)
    params = {name: inner[i] if i < len(inner) else self.vm.convert.unsolvable
              for i, name in enumerate(template)}
    return abstract_class(self.base_cls, params, self.vm)


class AbstractOrConcreteValue(Instance, PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, clsvar, vm):
    super(AbstractOrConcreteValue, self).__init__(clsvar, vm)
    PythonConstant.init_mixin(self, pyval)


class LazyConcreteDict(SimpleAbstractValue, PythonConstant):
  """Dictionary with lazy values."""

  is_lazy = True  # uses _convert_member

  def __init__(self, name, member_map, vm):
    SimpleAbstractValue.__init__(self, name, vm)
    self._member_map = member_map
    PythonConstant.init_mixin(self, self.members)

  def _convert_member(self, _, pyval):
    return self.vm.convert.constant_to_var(pyval)

  def compatible_with(self, logical_value):
    return bool(self._member_map) == logical_value


class Union(AtomicAbstractValue):
  """A list of types. Used for parameter matching.

  Attributes:
    options: Iterable of instances of AtomicAbstractValue.
  """

  def __init__(self, options, vm):
    super(Union, self).__init__("Union", vm)
    assert options
    self.options = tuple(options)
    # TODO(rechen): Don't allow a mix of formal and non-formal types
    self.formal = any(t.formal for t in options)

  def __repr__(self):
    return "%s[%s]" % (self.name, ", ".join(repr(o) for o in self.options))

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.options == other.options
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash(self.options)

  def instantiate(self, node, container=None):
    var = self.vm.program.NewVariable()
    for option in self.options:
      var.PasteVariable(option.instantiate(node, container), node)
    return var

  def get_class(self):
    var = self.vm.program.NewVariable()
    for o in self.options:
      var.PasteVariable(o.get_class(), self.vm.root_cfg_node)
    return var

  def call(self, node, func, args):
    var = self.vm.program.NewVariable(self.options, [], node)
    return self.vm.call_function(node, var, args)


class FunctionArgs(collections.namedtuple("_", ["posargs", "namedargs",
                                                "starargs", "starstarargs"])):
  """Represents the parameters of a function call."""

  def __new__(cls, posargs, namedargs=None, starargs=None, starstarargs=None):
    """Create arguments for a function under analysis.

    Args:
      posargs: The positional arguments. A tuple of typegraph.Variable.
      namedargs: The keyword arguments. A dictionary, mapping strings to
        typegraph.Variable.
      starargs: The *args parameter, or None.
      starstarargs: The **kwargs parameter, or None.
    Returns:
      A FunctionArgs instance.
    """
    assert isinstance(posargs, tuple), posargs
    cls.replace = cls._replace
    return super(FunctionArgs, cls).__new__(
        cls, posargs=posargs, namedargs=namedargs or {}, starargs=starargs,
        starstarargs=starstarargs)

  def starargs_as_tuple(self):
    try:
      args = self.starargs and get_atomic_python_constant(self.starargs, tuple)
    except ConversionError:
      args = None
    return args

  def starstarargs_as_dict(self):
    try:
      kws = self.starstarargs and get_atomic_value(self.starstarargs, Dict)
    except ConversionError:
      kws = None
    return kws

  def simplify(self, node):
    """Try to insert part of *args, **kwargs into posargs / namedargs."""
    # TODO(rechen): When we have type information about *args/**kwargs,
    # we need to check it before doing this simplification.
    posargs = self.posargs
    namedargs = self.namedargs
    starargs = self.starargs
    starstarargs = self.starstarargs
    starargs_as_tuple = self.starargs_as_tuple()
    if starargs_as_tuple is not None:
      posargs += starargs_as_tuple
      starargs = None
    starstarargs_as_dict = self.starstarargs_as_dict()
    if starstarargs_as_dict is not None:
      if namedargs is None:
        namedargs = starstarargs_as_dict
      else:
        namedargs.update(node, starstarargs_as_dict)
      starstarargs = None
    return FunctionArgs(posargs, namedargs, starargs, starstarargs)

  def get_variables(self):
    variables = list(self.posargs) + self.namedargs.values()
    if self.starargs is not None:
      variables.append(self.starargs)
    if self.starstarargs is not None:
      variables.append(self.starstarargs)
    return variables


class FailedFunctionCall(Exception):
  """Exception for failed function calls."""

  def __gt__(self, other):
    return other is None


class NotCallable(FailedFunctionCall):
  """For objects that don't have __call__."""

  def __init__(self, obj):
    super(NotCallable, self).__init__()
    self.obj = obj


class NoneNotCallable(FailedFunctionCall):
  """When trying to call None."""


class DictKeyMissing(Exception):
  """When retrieving a key that does not exist in a dict."""

  def __init__(self, name):
    super(DictKeyMissing, self).__init__()
    self.name = name

  def __gt__(self, other):
    return other is None


BadCall = collections.namedtuple("_", ["sig", "passed_args", "bad_param"])


BadParam = collections.namedtuple("_", ["name", "expected"])


class InvalidParameters(FailedFunctionCall):
  """Exception for functions called with an incorrect parameter combination."""

  def __init__(self, sig, passed_args, vm, bad_param=None):
    super(InvalidParameters, self).__init__()
    self.name = sig.name
    passed_args = [(name, merge_values(arg.data, vm))
                   for name, arg, _ in sig.iter_args(passed_args)]
    self.bad_call = BadCall(sig=sig, passed_args=passed_args,
                            bad_param=bad_param)


class WrongArgTypes(InvalidParameters):
  """For functions that were called with the wrong types."""

  def __gt__(self, other):
    return other is None or (isinstance(other, FailedFunctionCall) and
                             not isinstance(other, WrongArgTypes))


class WrongArgCount(InvalidParameters):
  """E.g. if a function expecting 4 parameters is called with 3."""
  pass


class WrongKeywordArgs(InvalidParameters):
  """E.g. an arg "x" is passed to a function that doesn't have an "x" param."""

  def __init__(self, sig, passed_args, vm, extra_keywords):
    super(WrongKeywordArgs, self).__init__(sig, passed_args, vm)
    self.extra_keywords = tuple(extra_keywords)


class DuplicateKeyword(InvalidParameters):
  """E.g. an arg "x" is passed to a function as both a posarg and a kwarg."""

  def __init__(self, sig, passed_args, vm, duplicate):
    super(DuplicateKeyword, self).__init__(sig, passed_args, vm)
    self.duplicate = duplicate


class MissingParameter(InvalidParameters):
  """E.g. a function requires parameter 'x' but 'x' isn't passed."""

  def __init__(self, sig, passed_args, vm, missing_parameter):
    super(MissingParameter, self).__init__(sig, passed_args, vm)
    self.missing_parameter = missing_parameter


class SuperInstance(AtomicAbstractValue):
  """The result of a super() call, i.e., a lookup proxy."""

  def __init__(self, cls, obj, vm):
    super(SuperInstance, self).__init__("super", vm)
    self.cls = self.vm.convert.super_type
    self.super_cls = cls
    self.super_obj = obj
    self.get = NativeFunction("__get__", self.get, self.vm)
    self.set = NativeFunction("__set__", self.set, self.vm)

  def get(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def set(self, node, *unused_args, **unused_kwargs):
    return node, self.to_variable(node)

  def get_special_attribute(self, node, name, valself):
    if name == "__get__":
      return self.get.to_variable(node)
    elif name == "__set__":
      return self.set.to_variable(node)
    else:
      return super(SuperInstance, self).get_special_attribute(
          node, name, valself)

  def get_class(self):
    return self.cls

  def call(self, node, _, args):
    self.vm.errorlog.not_callable(self.vm.frames, self)
    return node, Unsolvable(self.vm).to_variable(node)


class IsInstance(AtomicAbstractValue):
  """The isinstance() function."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "isinstance", ("obj", "type_or_types"), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(IsInstance, self).__init__("isinstance", vm)
    # Map of True/False/None (where None signals an ambiguous bool) to
    # vm values.
    self._vm_values = {
        True: vm.convert.true,
        False: vm.convert.false,
        None: vm.convert.primitive_class_instances[bool],
    }

  def call(self, node, _, args):
    try:
      if len(args.posargs) != 2:
        raise WrongArgCount(self._SIGNATURE, args, self.vm)
      elif args.namedargs.keys():
        raise WrongKeywordArgs(
            self._SIGNATURE, args, self.vm, args.namedargs.keys())
      else:
        result = self.vm.program.NewVariable()
        for left in args.posargs[0].bindings:
          for right in args.posargs[1].bindings:
            pyval = self._is_instance(left.data, right.data)
            result.AddBinding(self._vm_values[pyval],
                              source_set=(left, right), where=node)
    except InvalidParameters as ex:
      self.vm.errorlog.invalid_function_call(self.vm.frames, ex)
      result = self.vm.convert.create_new_unsolvable(node)

    return node, result

  def _is_instance(self, obj, class_spec):
    """Check if the object matches a class specification.

    Args:
      obj: An AtomicAbstractValue, generally the left hand side of an
          isinstance() call.
      class_spec: An AtomicAbstractValue, generally the right hand side of an
          isinstance() call.

    Returns:
      True if the object is derived from a class in the class_spec, False if
      it is not, and None if it is ambiguous whether obj matches class_spec.
    """
    if isinstance(obj, AMBIGUOUS_OR_EMPTY):
      return None
    # Assume a single binding for the object's class variable.  If this isn't
    # the case, treat the call as ambiguous.
    cls_var = obj.get_class()
    if cls_var is None:
      return None
    try:
      obj_class = get_atomic_value(cls_var)
    except ConversionError:
      return None

    # Determine the flattened list of classes to check.
    classes = []
    ambiguous = self._flatten(class_spec, classes)

    for c in classes:
      if c in obj_class.mro:
        return True  # A definite match.
    # No matches, return result depends on whether _flatten() was
    # ambiguous.
    return None if ambiguous else False

  def _flatten(self, value, classes):
    """Flatten the contents of value into classes.

    If value is a Class, it is appended to classes.
    If value is a PythonConstant of type tuple, then each element of the tuple
    that has a single binding is also flattened.
    Any other type of value, or tuple elements that have multiple bindings are
    ignored.

    Args:
      value: An abstract value.
      classes: A list to be modified.

    Returns:
      True iff a value was ignored during flattening.
    """
    if isinstance(value, Class):
      # A single class, no ambiguity.
      classes.append(value)
      return False
    elif isinstance(value, Tuple):
      # A tuple, need to process each element.
      ambiguous = False
      for var in value.pyval:
        if (len(var.bindings) != 1 or
            self._flatten(var.bindings[0].data, classes)):
          # There were either multiple bindings or ambiguity deeper in the
          # recursion.
          ambiguous = True
      return ambiguous
    else:
      return True


class Function(SimpleAbstractValue):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, vm):
    super(Function, self).__init__(name, vm)
    self.cls = self.vm.convert.function_type
    self.is_attribute_of_class = False
    self.members["func_name"] = self.vm.convert.build_string(
        self.vm.root_cfg_node, name)

  def property_get(self, callself, callcls):
    if self.name == "__new__" or not callself or not callcls:
      return self
    self.is_attribute_of_class = True
    # We'd like to cache this, but we can't. "callself" contains Variables
    # that would be tied into a BoundFunction instance. However, those
    # Variables aren't necessarily visible from other parts of the CFG binding
    # this function. See test_duplicate_getproperty() in tests/test_flow.py.
    return self.bound_class(callself, callcls, self)

  def _match_args(self, node, args):
    """Check whether the given arguments can match the function signature."""
    if not all(a.bindings for a in args.posargs):
      raise exceptions.ByteCodeTypeError(
          "Can't call function with <nothing> parameter")
    error = None
    matched = []
    for view in get_views(args.get_variables(), node):
      log.debug("args in view: %r", [(a.bindings and view[a].data)
                                     for a in args.posargs])
      try:
        match = self._match_view(node, args, view)
      except FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        matched.append(match)
    if not matched and error:
      raise error  # pylint: disable=raising-bad-type
    return matched

  def _match_view(self, node, args, view):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return self.name + "(...)"


class Mutation(collections.namedtuple("_", ["instance", "name", "value"])):
  pass


class PyTDSignature(object):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, name, pytd_sig, vm):
    self.vm = vm
    self.name = name
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.vm.convert.constant_to_value(
            p.type, subst={}, node=self.vm.root_cfg_node)
        for p in self.pytd_sig.params]
    self.signature = function.Signature.from_pytd(vm, name, pytd_sig)

  def match_args(self, node, args, view):
    """Match arguments against this signature. Used by PyTDFunction."""
    arg_dict = {name: view[arg]
                for name, arg in zip(self.signature.param_names, args.posargs)}
    for name, arg in args.namedargs.items():
      if name in arg_dict:
        raise DuplicateKeyword(self.signature, args, self.vm, name)
      arg_dict[name] = view[arg]

    for p in self.pytd_sig.params:
      if p.name not in arg_dict:
        if (not p.optional and args.starargs is None and
            args.starstarargs is None):
          raise MissingParameter(self.signature, args, self.vm, p.name)
        # Assume the missing parameter is filled in by *args or **kwargs.
        # Unfortunately, we can't easily use *args or **kwargs to fill in
        # something more precise, since we need a Value, not a Variable.
        var = self.vm.convert.create_new_unsolvable(node)
        arg_dict[p.name] = var.bindings[0]

    for p in self.pytd_sig.params:
      if not (p.optional or p.name in arg_dict):
        raise MissingParameter(self.signature, args, self.vm, p.name)
    if not self.pytd_sig.has_optional:
      if len(args.posargs) > len(self.pytd_sig.params):
        raise WrongArgCount(self.signature, args, self.vm)
      invalid_names = set(args.namedargs) - {p.name
                                             for p in self.pytd_sig.params}
      if invalid_names:
        raise WrongKeywordArgs(self.signature, args, self.vm, invalid_names)

    formal_args = [(p.name, self.signature.annotations[p.name])
                   for p in self.pytd_sig.params]
    subst, bad_arg = self.vm.matcher.compute_subst(
        node, formal_args, arg_dict, view)
    if subst is None:
      raise WrongArgTypes(self.signature, args, self.vm, bad_param=bad_arg)
    if log.isEnabledFor(logging.DEBUG):
      log.debug("Matched arguments against sig%s", pytd.Print(self.pytd_sig))
    for nr, p in enumerate(self.pytd_sig.params):
      log.info("param %d) %s: %s <=> %s", nr, p.name, p.type, arg_dict[p.name])
    for name, var in sorted(subst.items()):
      log.debug("Using %s=%r %r", name, var, var.data)

    return arg_dict, subst

  def call_with_args(self, node, func, arg_dict, subst, ret_map):
    """Call this signature. Used by PyTDFunction."""
    return_type = self.pytd_sig.return_type
    t = (return_type, subst)
    sources = [func] + arg_dict.values()
    if t not in ret_map:
      try:
        ret_map[t] = self.vm.convert.constant_to_var(
            AsInstance(return_type), subst, node, source_sets=[sources])
      except self.vm.convert.TypeParameterError:
        # The return type contains a type parameter without a substitution.
        subst = subst.copy()
        for t in self.pytd_sig.template:
          if t.name not in subst:
            subst[t.name] = self.vm.convert.empty.to_variable(node)
        ret_map[t] = self.vm.convert.constant_to_var(
            AsInstance(return_type), subst, node, source_sets=[sources])
      else:
        if (not ret_map[t].bindings and
            isinstance(return_type, pytd.TypeParameter)):
          ret_map[t].AddBinding(self.vm.convert.empty, [], node)
    else:
      # add the new sources
      for data in ret_map[t].data:
        ret_map[t].AddBinding(data, sources, node)
    mutations = self._get_mutation(node, arg_dict, subst)
    self.vm.trace_call(node, func, (self,),
                       tuple(arg_dict[p.name] for p in self.pytd_sig.params),
                       {},
                       ret_map[t])
    return node, ret_map[t], mutations

  def _get_mutation(self, node, arg_dict, subst):
    """Mutation for changing the type parameters of mutable arguments.

    This will adjust the type parameters as needed for pytd functions like:
      def append_float(x: list[int]):
        x := list[int or float]
    This is called after all the signature matching has succeeded, and we
    know we're actually calling this function.

    Args:
      node: The current CFG node.
      arg_dict: A map of strings to pytd.Bindings instances.
      subst: Current type parameters.
    Returns:
      A list of Mutation instances.
    Raises:
      ValueError: If the pytd contains invalid information for mutated params.
    """
    # Handle mutable parameters using the information type parameters
    mutations = []
    for formal in self.pytd_sig.params:
      actual = arg_dict[formal.name]
      arg = actual.data
      if (formal.mutated_type is not None and
          isinstance(arg, SimpleAbstractValue)):
        if (isinstance(formal.type, pytd.GenericType) and
            isinstance(formal.mutated_type, pytd.GenericType) and
            formal.type.base_type == formal.mutated_type.base_type and
            isinstance(formal.type.base_type, pytd.ClassType) and
            formal.type.base_type.cls):
          names_actuals = zip(formal.mutated_type.base_type.cls.template,
                              formal.mutated_type.parameters)
          for tparam, type_actual in names_actuals:
            log.info("Mutating %s to %s",
                     tparam.name,
                     pytd.Print(type_actual))
            type_actual_val = self.vm.convert.constant_to_var(
                AsInstance(type_actual), subst, node,
                discard_concrete_values=True)
            mutations.append(Mutation(arg, tparam.name, type_actual_val))
        else:
          log.error("Old: %s", pytd.Print(formal.type))
          log.error("New: %s", pytd.Print(formal.mutated_type))
          log.error("Actual: %r", actual)
          raise ValueError("Mutable parameters setting a type to a "
                           "different base type is not allowed.")
    return mutations

  def get_positional_names(self):
    return [p.name for p in self.pytd_sig.params
            if not p.kwonly]

  def __repr__(self):
    return pytd.Print(self.pytd_sig)


class ClassMethod(AtomicAbstractValue):
  """Implements @classmethod methods in pyi."""

  def __init__(self, name, method, callself, callcls, vm):
    super(ClassMethod, self).__init__(name, vm)
    self.method = method
    self.callself = callself  # unused
    self.callcls = callcls  # unused
    self.signatures = self.method.signatures

  def call(self, node, func, args):
    # Since this only used in pyi, we don't need to verify the type of the "cls"
    # arg a second time. So just pass an unsolveable. (All we care about is the
    # return type, anyway.)
    cls = self.vm.convert.create_new_unsolvable(node)
    return self.method.call(
        node, func, args.replace(posargs=(cls,) + args.posargs))

  def get_class(self):
    return self.vm.convert.function_type


class StaticMethod(AtomicAbstractValue):
  """Implements @staticmethod methods in pyi."""

  def __init__(self, name, method, callself, callcls, vm):
    super(StaticMethod, self).__init__(name, vm)
    self.method = method
    self.callself = callself  # unused
    self.callcls = callcls  # unused
    self.signatures = self.method.signatures

  def call(self, *args, **kwargs):
    return self.method.call(*args, **kwargs)

  def get_class(self):
    return self.vm.convert.function_type


class PyTDFunction(Function):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  def __init__(self, name, signatures, kind, vm):
    super(PyTDFunction, self).__init__(name, vm)
    assert signatures
    self.kind = kind
    self.bound_class = BoundPyTDFunction
    self.signatures = signatures
    self._signature_cache = {}
    self._return_types = {sig.pytd_sig.return_type for sig in signatures}
    self._has_mutable = any(param.mutated_type is not None
                            for sig in signatures
                            for param in sig.pytd_sig.params)
    for sig in signatures:
      sig.function = self
      sig.name = self.name

  def property_get(self, callself, callcls):
    if self.kind == pytd.STATICMETHOD:
      return StaticMethod(self.name, self, callself, callcls, self.vm)
    elif self.kind == pytd.CLASSMETHOD:
      return ClassMethod(self.name, self, callself, callcls, self.vm)
    else:
      return Function.property_get(self, callself, callcls)

  def _log_args(self, arg_values_list, level=0, logged=None):
    if log.isEnabledFor(logging.DEBUG):
      if logged is None:
        logged = set()
      for i, arg_values in enumerate(arg_values_list):
        if level:
          if arg_values and any(v.data not in logged for v in arg_values):
            log.debug("%s%s:", "  " * level, arg_values[0].variable.id)
        else:
          log.debug("Arg %d", i)
        for value in arg_values:
          if value.data not in logged:
            log.debug("%s%s [var %d]", "  " * (level + 1), value.data,
                      value.variable.id)
            self._log_args(value.data.unique_parameter_values(), level + 2,
                           logged | {value.data})

  def call(self, node, func, args):
    args = args.simplify(node)
    self._log_args(arg.bindings for arg in args.posargs)
    ret_map = {}
    retvar = self.vm.program.NewVariable()
    all_mutations = []
    # The following line may raise FailedFunctionCall
    possible_calls = self._match_args(node, args)
    for view, signatures in possible_calls:
      if len(signatures) > 1:
        ret = self._call_with_signatures(node, func, args, view, signatures)
      else:
        (sig, arg_dict, subst), = signatures
        ret = sig.call_with_args(node, func, arg_dict, subst, ret_map)
      node, result, mutations = ret
      retvar.PasteVariable(result, node)
      all_mutations += mutations

    log.info("Applying %d mutations", len(all_mutations))
    for obj, name, value in all_mutations:
      obj.merge_type_parameter(node, name, value)

    return node, retvar

  def _get_mutation_to_unknown(self, node, values):
    """Mutation for making all type parameters in a list of instances "unknown".

    This is used if we call a function that has mutable parameters and
    multiple signatures with unknown parameters.

    Args:
      node: The current CFG node.
      values: A list of instances of AtomicAbstractValue.

    Returns:
      A list of Mutation instances.
    """
    return [Mutation(v, name, self.vm.convert.create_new_unknown(
        node, action="type_param_" + name))
            for v in values if isinstance(v, SimpleAbstractValue)
            for name in v.type_parameters]

  def _match_view(self, node, args, view):
    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, if multiple
    # signatures are possible matches, we don't know which got called. Check
    # if this is the case.
    if (len(self.signatures) > 1 and
        any(isinstance(view[arg].data, AMBIGUOUS_OR_EMPTY)
            for arg in args.get_variables())):
      signatures = tuple(self._yield_matching_signatures(node, args, view))
    else:
      # We take the first signature that matches, and ignore all after it.
      # This is because in the pytds for the standard library, the last
      # signature(s) is/are fallback(s) - e.g. list is defined by
      # def __init__(self: x: list)
      # def __init__(self, x: iterable)
      # def __init__(self, x: generator)
      # def __init__(self, x: object)
      # with the last signature only being used if none of the others match.
      sig = next(self._yield_matching_signatures(node, args, view))
      signatures = (sig,)
    return (view, signatures)

  def _call_with_signatures(self, node, func, args, view, signatures):
    """Perform a function call that involves multiple signatures."""
    if len(self._return_types) == 1:
      ret_type, = self._return_types
      try:
        # Even though we don't know which signature got picked, if the return
        # type is unique and does not contain any type parameter, we can use it.
        result = self.vm.convert.constant_to_var(AsInstance(ret_type), {}, node)
      except self.vm.convert.TypeParameterError:
        # The return type contains a type parameter
        result = None
      else:
        log.debug("Unknown args. But return is always %s", pytd.Print(ret_type))
    else:
      result = None
    if result is None:
      log.debug("Creating unknown return")
      result = self.vm.convert.create_new_unknown(
          node, action="pytd_call")
    for i, arg in enumerate(args.posargs):
      if isinstance(view[arg].data, Unknown):
        for sig, _, _ in signatures:
          if (len(sig.param_types) > i and
              isinstance(sig.param_types[i], TypeParameter)):
            # Change this parameter from unknown to unsolvable to prevent the
            # unknown from being solved to a type in another signature. For
            # instance, with the following definitions:
            #  def f(x: T) -> T
            #  def f(x: int) -> T
            # the type of x should be Any, not int.
            view[arg] = arg.AddBinding(self.vm.convert.unsolvable, [], node)
            break
    if self._has_mutable:
      # TODO(kramm): We only need to whack the type params that appear in
      # a mutable parameter.
      mutations = self._get_mutation_to_unknown(
          node, (view[p].data for p in chain(args.posargs,
                                             args.namedargs.values())))
    else:
      mutations = []
    self.vm.trace_call(node, func, tuple(sig[0] for sig in signatures),
                       [view[arg] for arg in args.posargs],
                       {name: view[arg]
                        for name, arg in args.namedargs.items()},
                       result)
    return node, result, mutations

  def _yield_matching_signatures(self, node, args, view):
    """Try, in order, all pytd signatures, yielding matches."""
    error = None
    matched = False
    for sig in self.signatures:
      try:
        arg_dict, subst = sig.match_args(node, args, view)
      except FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        matched = True
        yield sig, arg_dict, subst
    if not matched:
      raise error  # pylint: disable=raising-bad-type


class TypeNew(PyTDFunction):
  """Implements type.__new__."""

  def call(self, node, func, args):
    if len(args.posargs) == 4:
      # Try to construct a more specific return type. If we can't, we'll fall
      # back to the result of PyTDFunction.call.
      try:
        self._match_args(node, args)
      except FailedFunctionCall:
        pass
      else:
        cls, name_var, bases_var, class_dict_var = args.posargs
        try:
          bases = list(get_atomic_python_constant(bases_var))
          if not bases:
            bases = [self.vm.convert.object_type]
          variable = self.vm.make_class(
              node, name_var, bases, class_dict_var, cls)
        except ConversionError:
          pass
        else:
          return node, variable
    return super(TypeNew, self).call(node, func, args)


class Class(object):
  """Mix-in to mark all class-like values."""

  __metaclass__ = MixinMeta
  overloads = ("get_special_attribute",)

  def __new__(cls, *args, **kwds):
    """Prevent direct instantiation."""
    assert cls is not Class, "Cannot instantiate Class"
    return object.__new__(cls, *args, **kwds)

  def init_mixin(self, metaclass):
    """Mix-in equivalent of __init__."""
    if metaclass is None:
      self.cls = self._get_inherited_metaclass()
    else:
      # TODO(rechen): Check that the metaclass is a (non-strict) subclass of the
      # metaclasses of the base classes.
      self.cls = metaclass

  def _get_inherited_metaclass(self):
    for base in self.mro[1:]:
      if isinstance(base, Class) and base.cls is not None:
        return base.cls
    return None

  def _call_new_and_init(self, node, value, args):
    """Call __new__ if it has been overridden on the given value."""
    node, new = self.vm.attribute_handler.get_attribute(
        node, value.data, "__new__", value)
    if new is None:
      return node, None
    if len(new.bindings) == 1:
      f = new.bindings[0].data
      if isinstance(f, StaticMethod):
        f = f.method
      if isinstance(f, AMBIGUOUS_OR_EMPTY) or f is self.vm.convert.object_new:
        # Instead of calling object.__new__, our abstract classes directly
        # create instances of themselves.
        return node, None
    cls = value.AssignToNewVariable(node)
    new_args = args.replace(posargs=(cls,) + args.posargs)
    node, variable = self.vm.call_function(node, new, new_args)
    for val in variable.bindings:
      # TODO(rechen): If val.data is a class, _call_init mistakenly calls
      # val.data's __init__ method rather than that of val.data.cls. See
      # testClasses.testTypeInit for a case in which skipping this __init__
      # call is problematic.
      if (not isinstance(val.data, Class) and val.data.cls and
          self in val.data.cls.data):
        node = self._call_init(node, val, args)
    return node, variable

  def _call_init(self, node, value, args):
    node, init = self.vm.attribute_handler.get_attribute(
        node, value.data, "__init__", value)
    # TODO(pludemann): Verify that this follows MRO:
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      node, ret = self.vm.call_function(node, init, args)
      log.debug("%s.__init__(...) returned %r", self.name, ret)
    return node

  def get_special_attribute(self, node, name, valself):
    """Fetch a special attribute."""
    if name == "__getitem__" and valself is None:
      if self.cls:
        # This class has a custom metaclass; check if it defines __getitem__.
        _, attr = self.vm.attribute_handler.get_instance_attribute(
            node, self, name, self.to_variable(node).bindings[0])
        if attr:
          return attr
      # Treat this class as a parameterized container in an annotation. We do
      # not need to worry about the class not being a container: in that case,
      # AnnotationContainer's param length check reports an appropriate error.
      container = AnnotationContainer(self.name, self.vm, self)
      return container.get_special_attribute(node, name, valself)
    return Class.super(self.get_special_attribute)(node, name, valself)


class ParameterizedClass(AtomicAbstractValue, Class):
  """A class that contains additional parameters. E.g. a container.

  Attributes:
    cls: A PyTDClass representing the base type.
    type_parameters: An iterable of AtomicAbstractValue, one for each type
        parameter.
  """

  def __init__(self, base_cls, type_parameters, vm):
    # A ParameterizedClass is created by converting a pytd.GenericType, whose
    # base type is restricted to NamedType and ClassType.
    assert isinstance(base_cls, Class)
    super(ParameterizedClass, self).__init__(base_cls.name, vm)
    self.base_cls = base_cls
    self.module = base_cls.module
    self.type_parameters = type_parameters
    self.mro = (self,) + self.base_cls.mro[1:]
    self.official_name = self.base_cls.official_name
    self.template = self.base_cls.template
    Class.init_mixin(self, base_cls.cls)

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (self.base_cls,
                                                     self.type_parameters)

  @property
  def formal(self):
    # We can't compute self.formal in __init__ because doing so would force
    # evaluation of our type parameters during initialization, possibly
    # leading to an infinite loop.
    return any(t.formal for t in self.type_parameters.values())

  def instantiate(self, node, container=None):
    if self.full_name == "__builtin__.type":
      instance = self.type_parameters[T]
      if instance.formal:
        # This can happen for, say, Type[T], where T is a type parameter. See
        # test_typevar's testTypeParameterType for an example.
        instance = self.vm.convert.unsolvable
      return instance.to_variable(node)
    else:
      return super(ParameterizedClass, self).instantiate(node, container)

  def get_class(self):
    return self.base_cls.get_class()


class TupleClass(ParameterizedClass, HasSlots):
  """The class of a heterogeneous tuple.

  The type_parameters attribute stores the types of the individual tuple
  elements under their indices and the overall element type under "T". So for
    Tuple[str, int]
  type_parameters is
    {0: str, 1: int, T: str or int}.
  Note that we can't store the individual types as a PythonConstant as we do
  for Tuple, since we can't evaluate type parameters during initialization.
  """

  def __init__(self, base_cls, type_parameters, vm):
    super(TupleClass, self).__init__(base_cls, type_parameters, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    # We subtract one to account for "T".
    self.tuple_length = len(self.type_parameters) - 1
    self._instance = None

  def __repr__(self):
    return "TupleClass(%s)" % self.type_parameters

  def instantiate(self, node, container=None):
    if self._instance:
      return self._instance.to_variable(node)
    content = tuple(
        self.type_parameters[i].instantiate(self.vm.root_cfg_node, container)
        for i in range(self.tuple_length))
    return Tuple(content, self.vm).to_variable(node)

  def _instantiate_index(self, node, index):
    if self._instance:
      return self._instance.pyval[index]
    else:
      index %= self.tuple_length  # fixes negative indices
      return self.type_parameters[index].instantiate(node)

  def register_instance(self, instance):
    # A TupleClass can never have more than one registered instance because the
    # only direct instances of TupleClass are Tuple objects, which create their
    # own class upon instantiation. We store the instance in order to track
    # changes in the types of the elements (see TupleTest.testMutableItem).
    assert not self._instance
    self._instance = instance

  def getitem_slot(self, node, index_var):
    """Implementation of tuple.__getitem__."""
    try:
      index = self.vm.convert.value_to_constant(
          get_atomic_value(index_var), int)
    except ConversionError:
      pass
    else:
      if -self.tuple_length <= index and index < self.tuple_length:
        # TODO(rechen): Should index out of bounds be a pytype error?
        return node, self._instantiate_index(node, index)
    return self.call_pytd(
        node, "__getitem__", self.instantiate(node), index_var)

  def get_special_attribute(self, node, name, valself):
    if valself and name in self._slots:
      return HasSlots.get_special_attribute(self, node, name, valself)
    return super(TupleClass, self).get_special_attribute(node, name, valself)


class Callable(ParameterizedClass, HasSlots):
  """A Callable with a list of argument types.

  The type_parameters attribute stores the types of the individual arguments
  under their indices, the overall argument type under "ARGS", and the return
  type under "RET". So for
    Callable[[int, bool], str]
  type_parameters is
    {0: int, 1: bool, ARGS: int or bool, RET: str}
  When there are no args (Callable[[], ...]), ARGS contains abstract.Nothing.
  """

  def __init__(self, base_cls, type_parameters, vm):
    super(Callable, self).__init__(base_cls, type_parameters, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__call__", self.call_slot)
    # We subtract two to account for "ARGS" and "RET".
    self.num_args = len(self.type_parameters) - 2

  def __repr__(self):
    return "Callable(%s)" % self.type_parameters

  def call_slot(self, node, *args, **kwargs):
    """Implementation of Callable.__call__."""
    if kwargs:
      raise WrongKeywordArgs(function.Signature.from_callable(self),
                             FunctionArgs(posargs=args, namedargs=kwargs),
                             self.vm, kwargs.keys())
    if len(args) != self.num_args:
      raise WrongArgCount(function.Signature.from_callable(self),
                          FunctionArgs(posargs=args), self.vm)
    formal_args = [(function.argname(i), self.type_parameters[i])
                   for i in range(self.num_args)]
    substs = [{}]
    bad_param = None
    for view in get_views(args, node):
      arg_dict = {function.argname(i): view[args[i]]
                  for i in range(self.num_args)}
      subst, bad_param = self.vm.matcher.compute_subst(
          node, formal_args, arg_dict, view)
      if subst is not None:
        substs = [subst]
        break
    else:
      if bad_param:
        raise WrongArgTypes(
            function.Signature.from_callable(self), FunctionArgs(posargs=args),
            self.vm, bad_param=bad_param)
    ret = self.vm.annotations_util.sub_one_annotation(
        node, self.type_parameters[RET], substs)
    return node, ret.instantiate(node)

  def get_special_attribute(self, node, name, valself):
    if valself and name in self._slots:
      return HasSlots.get_special_attribute(self, node, name, valself)
    return super(Callable, self).get_special_attribute(node, name, valself)


class PyTDClass(SimpleAbstractValue, Class):
  """An abstract wrapper for PyTD class objects.

  These are the abstract values for class objects that are described in PyTD.

  Attributes:
    cls: A pytd.Class
    mro: Method resolution order. An iterable of AtomicAbstractValue.
  """
  is_lazy = True  # uses _convert_member

  def __init__(self, name, pytd_cls, vm):
    super(PyTDClass, self).__init__(name, vm)
    mm = {}
    for val in pytd_cls.constants + pytd_cls.methods:
      mm[val.name] = val
    self._member_map = mm
    if pytd_cls.metaclass is None:
      metaclass = None
    else:
      metaclass = self.vm.convert.constant_to_var(
          pytd_cls.metaclass, subst={}, node=self.vm.root_cfg_node)
    self.pytd_cls = pytd_cls
    self.mro = mro.compute_mro(self)
    self.official_name = self.name
    self.template = self.pytd_cls.template
    Class.init_mixin(self, metaclass)

  def bases(self):
    convert = self.vm.convert
    return [convert.constant_to_var(parent, subst={},
                                    node=self.vm.root_cfg_node)
            for parent in self.pytd_cls.parents]

  def load_lazy_attribute(self, name):
    try:
      super(PyTDClass, self).load_lazy_attribute(name)
    except self.vm.convert.TypeParameterError as e:
      self.vm.errorlog.type_param_error(
          self.vm.frames, self, name, e.type_param_name)
      self.members[name] = self.vm.convert.unsolvable.to_variable(
          self.vm.root_cfg_node)

  def _convert_member(self, _, pyval, subst=None, node=None):
    """Convert a member as a variable. For lazy lookup."""
    subst = subst or {}
    node = node or self.vm.root_cfg_node
    if isinstance(pyval, pytd.Constant):
      return self.vm.convert.constant_to_var(
          AsInstance(pyval.type), subst, node)
    elif isinstance(pyval, pytd.Function):
      c = self.vm.convert.constant_to_value(pyval, subst=subst, node=node)
      c.parent = self
      return c.to_variable(self.vm.root_cfg_node)
    else:
      raise AssertionError("Invalid class member %s", pytd.Print(pyval))

  def call(self, node, func, args):
    node, results = self._call_new_and_init(node, func, args)
    if results is None:
      value = Instance(self.vm.convert.constant_to_var(self.pytd_cls), self.vm)
      for type_param in self.template:
        if type_param.name not in value.type_parameters:
          value.type_parameters[type_param.name] = self.vm.program.NewVariable()
      results = self.vm.program.NewVariable()
      retval = results.AddBinding(value, [func], node)
      node = self._call_init(node, retval, args)
    return node, results

  def instantiate(self, node, container=None):
    return self.vm.convert.constant_to_var(AsInstance(self.pytd_cls), {}, node)

  def __repr__(self):
    return "PyTDClass(%s)" % self.name

  def convert_as_instance_attribute(self, node, name, instance):
    try:
      c = self.pytd_cls.Lookup(name)
    except KeyError:
      return None
    if isinstance(c, pytd.Constant):
      try:
        self._convert_member(name, c)
      except self.vm.convert.TypeParameterError:
        # Constant c cannot be converted without type parameter substitutions,
        # so it must be an instance attribute.
        subst = {
            itm.name: TypeParameterInstance(
                self.vm.convert.constant_to_value(itm.type_param, {}, node),
                instance, self.vm).to_variable(node)
            for itm in self.template}
        return self._convert_member(name, c, subst, node)


class Super(PyTDClass):
  """The super() function. Calling it will create a SuperInstance."""

  # Minimal signature, only used for constructing exceptions.
  _SIGNATURE = function.Signature(
      "super", ("cls", "self"), None, set(), None, {}, {}, {})

  def __init__(self, vm):
    super(Super, self).__init__(
        "super", vm.lookup_builtin("__builtin__.super"), vm)
    self.module = "__builtin__"

  def call(self, node, _, args):
    result = self.vm.program.NewVariable()
    if len(args.posargs) == 1:
      # TODO(kramm): Add a test for this
      for cls in args.posargs[0].bindings:
        result.AddBinding(
            SuperInstance(cls.data, None, self.vm), [cls], node)
    elif len(args.posargs) == 2:
      for cls in args.posargs[0].bindings:
        if not isinstance(cls.data, (Class, AMBIGUOUS_OR_EMPTY)):
          bad = BadParam(name="cls", expected=self.vm.convert.type_type.data[0])
          raise WrongArgTypes(self._SIGNATURE, args, self.vm, bad_param=bad)
        for obj in args.posargs[1].bindings:
          result.AddBinding(
              SuperInstance(cls.data, obj.data, self.vm), [cls, obj], node)
    else:
      raise WrongArgCount(self._SIGNATURE, args, self.vm)
    return node, result


class InterpreterClass(SimpleAbstractValue, Class):
  """An abstract wrapper for user-defined class objects.

  These are the abstract value for class objects that are implemented in the
  program.
  """

  def __init__(self, name, bases, members, cls, vm):
    assert isinstance(name, str)
    assert isinstance(bases, list)
    assert isinstance(members, dict)
    super(InterpreterClass, self).__init__(name, vm)
    self._bases = bases
    self.mro = mro.compute_mro(self)
    Class.init_mixin(self, cls)
    self.members = utils.MonitorDict(members)
    self.instances = set()  # filled through register_instance
    self._instance_cache = {}
    log.info("Created class: %r", self)

  def register_instance(self, instance):
    self.instances.add(instance)

  def bases(self):
    return self._bases

  def metaclass(self, node):
    if self.cls and self.cls is not self._get_inherited_metaclass():
      return self.vm.convert.merge_classes(node, [self])
    else:
      return None

  def _new_instance(self):
    # We allow only one "instance" per code location, regardless of call stack.
    key = self.vm.frame.current_opcode
    if key not in self._instance_cache:
      cls = self.vm.program.NewVariable()
      cls.AddBinding(self, [], self.vm.root_cfg_node)
      self._instance_cache[key] = Instance(cls, self.vm)
    return self._instance_cache[key]

  def call(self, node, value, args):
    node, variable = self._call_new_and_init(node, value, args)
    if variable is None:
      value = self._new_instance()
      variable = self.vm.program.NewVariable()
      val = variable.AddBinding(value, [], node)
      node = self._call_init(node, val, args)
    return node, variable

  def __repr__(self):
    return "InterpreterClass(%s)" % self.name

  def update_official_name(self, name):
    assert isinstance(name, str)
    if (self.official_name is None or
        name == self.name or
        (self.official_name != self.name and name < self.official_name)):
      # The lexical comparison is to ensure that, in the case of multiple calls
      # to this method, the official name does not depend on the call order.
      self.official_name = name


class NativeFunction(Function):
  """An abstract value representing a native function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    func: An object with a __call__ method.
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, func, vm):
    super(NativeFunction, self).__init__(name, vm)
    self.func = func
    self.bound_class = lambda callself, callcls, underlying: self

  def argcount(self):
    return self.func.func_code.co_argcount

  def call(self, node, _, args):
    args = args.simplify(node)
    posargs = [u.AssignToNewVariable(node) for u in args.posargs]
    namedargs = {k: u.AssignToNewVariable(node)
                 for k, u in args.namedargs.items()}
    try:
      inspect.getcallargs(self.func, node, *posargs, **namedargs)
    except ValueError:
      # Happens for, e.g.,
      #   def f((x, y)): pass
      #   f((42,))
      raise NotImplementedError("Wrong number of values to unpack")
    except TypeError as e:
      # The possible errors here are:
      #   (1) wrong arg count
      #   (2) duplicate keyword
      #   (3) unexpected keyword
      # The way we constructed namedargs rules out (2).
      if "keyword" in e.message:
        # Happens for, e.g.,
        #   def f(*args): pass
        #   f(x=42)
        raise NotImplementedError("Unexpected keyword")
      # The function was passed the wrong number of arguments. The signature is
      # ([self, ]node, ...). The length of "..." tells us how many variables
      # are expected.
      expected_argcount = len(inspect.getargspec(self.func).args) - 1
      if inspect.ismethod(self.func) and self.func.__self__ is not None:
        expected_argcount -= 1
      actual_argcount = len(posargs) + len(namedargs)
      if (actual_argcount > expected_argcount or
          (not args.starargs and not args.starstarargs)):
        # If we have too many arguments, or starargs and starstarargs are both
        # empty, then we can be certain of a WrongArgCount error.
        argnames = tuple("_" + str(i) for i in range(expected_argcount))
        sig = function.Signature(
            self.name, argnames, None, set(), None, {}, {}, {})
        raise WrongArgCount(sig, args, self.vm)
      assert actual_argcount < expected_argcount
      # Assume that starargs or starstarargs fills in the missing arguments.
      # Instead of guessing where these arguments should go, overwrite all of
      # the arguments with a list of unsolvables of the correct length, which
      # is guaranteed to give us a correct (but imprecise) analysis.
      posargs = [self.vm.convert.create_new_unsolvable(node)
                 for _ in range(expected_argcount)]
      namedargs = {}
    return self.func(node, *posargs, **namedargs)

  def get_positional_names(self):
    code = self.func.func_code
    return list(code.co_varnames[:code.co_argcount])


class InterpreterFunction(Function):
  """An abstract value representing a user-defined function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    code: A code object.
    closure: Tuple of cells (typegraph.Variable) containing the free variables
      this closure binds to.
    vm: TypegraphVirtualMachine instance.
  """

  _function_cache = {}

  @staticmethod
  def make_function(name, code, f_locals, f_globals, defaults, kw_defaults,
                    closure, annotations, late_annotations, vm):
    """Get an InterpreterFunction.

    Things like anonymous functions and generator expressions are created
    every time the corresponding code executes. Caching them makes it easier
    to detect when the environment hasn't changed and a function call can be
    optimized away.

    Arguments:
      name: Function name.
      code: A code object.
      f_locals: The locals used for name resolution.
      f_globals: The globals used for name resolution.
      defaults: Default arguments.
      kw_defaults: Default arguments for kwonly parameters.
      closure: The free variables this closure binds to.
      annotations: Function annotations. Dict of name -> AtomicAbstractValue.
      late_annotations: Late-evaled annotations. Dict of name -> str.
      vm: VirtualMachine instance.

    Returns:
      An InterpreterFunction.
    """
    annotations = annotations or {}
    late_annotations = late_annotations or {}
    key = (name, code,
           InterpreterFunction._hash_all(
               (f_globals.members, set(code.co_names)),
               (f_locals.members,
                set(f_locals.members) - set(code.co_varnames)),
               ({key: vm.program.NewVariable([value], [], vm.root_cfg_node)
                 for key, value in annotations.items()}, None),
               (dict(enumerate(defaults)), None),
               (dict(enumerate(closure or ())), None)))
    if key not in InterpreterFunction._function_cache:
      InterpreterFunction._function_cache[key] = InterpreterFunction(
          name, code, f_locals, f_globals, defaults, kw_defaults,
          closure, annotations, late_annotations, vm)
    return InterpreterFunction._function_cache[key]

  @staticmethod
  def get_arg_count(code):
    """Return the arg count given a code object."""
    count = code.co_argcount + max(code.co_kwonlyargcount, 0)
    if code.co_flags & loadmarshal.CodeType.CO_VARARGS:
      count += 1
    if code.co_flags & loadmarshal.CodeType.CO_VARKEYWORDS:
      count += 1
    return count

  def __init__(self, name, code, f_locals, f_globals, defaults, kw_defaults,
               closure, annotations, late_annotations, vm):
    super(InterpreterFunction, self).__init__(name, vm)
    log.debug("Creating InterpreterFunction %r for %r", name, code.co_name)
    self.bound_class = BoundInterpreterFunction
    self.doc = code.co_consts[0] if code.co_consts else None
    self.code = code
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.defaults = tuple(defaults)
    self.kw_defaults = kw_defaults
    self.closure = closure
    self._call_cache = {}
    self._call_records = []
    self.nonstararg_count = self.code.co_argcount
    if self.code.co_kwonlyargcount >= 0:  # This is usually -1 or 0 (fast call)
      self.nonstararg_count += self.code.co_kwonlyargcount
    self.signature = self._build_signature(annotations, late_annotations)
    self.last_frame = None  # for BuildClass
    self._store_call_records = False

  @contextlib.contextmanager
  def record_calls(self):
    """Turn on recording of function calls. Used by infer.py."""
    old = self._store_call_records
    self._store_call_records = True
    yield
    self._store_call_records = old

  def _build_signature(self, annotations, late_annotations):
    """Build a function.Signature object representing this function."""
    vararg_name = None
    kwarg_name = None
    kwonly = set(self.code.co_varnames[
        self.code.co_argcount:self.nonstararg_count])
    arg_pos = self.nonstararg_count
    if self.has_varargs():
      vararg_name = self.code.co_varnames[arg_pos]
      arg_pos += 1
    if self.has_kwargs():
      kwarg_name = self.code.co_varnames[arg_pos]
      arg_pos += 1
    defaults = dict(zip(
        self.get_positional_names()[-len(self.defaults):], self.defaults))
    defaults.update(self.kw_defaults)
    return function.Signature(
        self.name,
        list(self.code.co_varnames[:self.nonstararg_count]),
        vararg_name,
        kwonly,
        kwarg_name,
        defaults,
        annotations,
        late_annotations)

  # TODO(kramm): support retrieving the following attributes:
  # 'func_{code, name, defaults, globals, locals, dict, closure},
  # '__name__', '__dict__', '__doc__', '_vm', '_func'

  def get_first_opcode(self):
    return self.code.co_code[0]

  def is_closure(self):
    return self.closure is not None

  def argcount(self):
    return self.code.co_argcount

  def _map_args(self, node, args):
    """Map call args to function args.

    This emulates how Python would map arguments of function calls. It takes
    care of keyword parameters, default parameters, and *args and **kwargs.

    Args:
      node: The current CFG node.
      args: The arguments.

    Returns:
      A dictionary, mapping strings (parameter names) to typegraph.Variable.

    Raises:
      FailedFunctionCall: If the caller supplied incorrect arguments.
    """
    # Originate a new variable for each argument and call.
    posargs = [u.AssignToNewVariable(node)
               for u in args.posargs]
    kws = {k: u.AssignToNewVariable(node)
           for k, u in args.namedargs.items()}
    if (self.vm.python_version[0] == 2 and
        self.code.co_name in ["<setcomp>", "<dictcomp>", "<genexpr>"]):
      # This code is from github.com/nedbat/byterun. Apparently, Py2 doesn't
      # know how to inspect set comprehensions, dict comprehensions, or
      # generator expressions properly. See http://bugs.python.org/issue19611.
      # Byterun says: "They are always functions of one argument, so just do the
      # right thing."
      assert len(posargs) == 1, "Surprising comprehension!"
      return {".0": posargs[0]}
    param_names = self.get_positional_names()
    num_defaults = len(self.defaults)
    callargs = dict(zip(param_names[-num_defaults:], self.defaults))
    callargs.update(self.kw_defaults)
    positional = dict(zip(param_names, posargs))
    for key in positional:
      if key in kws:
        raise DuplicateKeyword(self.signature, args, self.vm, key)
    extra_kws = set(kws).difference(param_names + self.get_kwonly_names())
    if extra_kws and not self.has_kwargs():
      raise WrongKeywordArgs(self.signature, args, self.vm, extra_kws)
    callargs.update(positional)
    callargs.update(kws)
    for key, kwonly in self.get_nondefault_params():
      if key not in callargs:
        if args.starstarargs or (args.starargs and not kwonly):
          # We assume that because we have *args or **kwargs, we can use these
          # to fill in any parameters we might be missing.
          callargs[key] = self.vm.convert.create_new_unsolvable(node)
        else:
          raise MissingParameter(self.signature, args, self.vm, key)
    arg_pos = self.nonstararg_count
    if self.has_varargs():
      vararg_name = self.code.co_varnames[arg_pos]
      extraneous = posargs[self.code.co_argcount:]
      if args.starargs:
        if extraneous:
          log.warning("Not adding extra params to *%s", vararg_name)
        callargs[vararg_name] = args.starargs.AssignToNewVariable(node)
      else:
        callargs[vararg_name] = self.vm.convert.build_tuple(node, extraneous)
      arg_pos += 1
    elif len(posargs) > self.code.co_argcount:
      raise WrongArgCount(self.signature, args, self.vm)
    if self.has_kwargs():
      kwvararg_name = self.code.co_varnames[arg_pos]
      # Build a **kwargs dictionary out of the extraneous parameters
      if args.starstarargs:
        # TODO(kramm): modify type parameters to account for namedargs
        callargs[kwvararg_name] = args.starstarargs.AssignToNewVariable(node)
      else:
        k = Dict(self.vm)
        k.update(node, args.namedargs, omit=param_names)
        callargs[kwvararg_name] = k.to_variable(node)
      arg_pos += 1
    return callargs

  @staticmethod
  def _hash(vardict, names):
    """Hash a dictionary.

    This contains the keys and the full hashes of the data in the values.

    Arguments:
      vardict: A dictionary mapping str to Variable.
      names: If this is non-None, the snapshot will include only those
        dictionary entries whose keys appear in names.

    Returns:
      A hash of the dictionary.
    """
    if names is not None:
      vardict = {name: vardict[name] for name in names.intersection(vardict)}
    m = hashlib.md5()
    for name, var in sorted(vardict.items()):
      m.update(str(name))
      for value in var.bindings:
        m.update(value.data.get_fullhash())
    return m.digest()

  @staticmethod
  def _hash_all(*hash_args):
    """Convenience method for hashing a sequence of dicts."""
    return hashlib.md5("".join(InterpreterFunction._hash(*args)
                               for args in hash_args)).digest()

  def _match_args(self, node, args):
    if not self.signature.has_param_annotations:
      return
    return super(InterpreterFunction, self)._match_args(node, args)

  def _match_view(self, node, args, view):
    arg_dict = {}
    formal_args = []
    for name, arg, formal in self.signature.iter_args(args):
      arg_dict[name] = view[arg]
      if formal is not None:
        if name == self.signature.varargs_name:
          # The annotation is Tuple[<varargs type>], but the passed arg can be
          # any iterable of <varargs type>.
          formal = ParameterizedClass(self.vm.convert.name_to_value(
              "typing.Iterable"), formal.type_parameters, self.vm)
        elif name == self.signature.kwargs_name:
          # The annotation is Dict[str, <kwargs type>], but the passed arg can
          # be any mapping from str to <kwargs type>.
          formal = ParameterizedClass(self.vm.convert.name_to_value(
              "typing.Mapping"), formal.type_parameters, self.vm)
        formal_args.append((name, formal))
    subst, bad_arg = self.vm.matcher.compute_subst(
        node, formal_args, arg_dict, view)
    if subst is None:
      raise WrongArgTypes(self.signature, args, self.vm, bad_param=bad_arg)
    return subst

  def call(self, node, _, args, new_locals=None):
    args = args.simplify(node)
    if self.vm.is_at_maximum_depth() and self.name != "__init__":
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      if self.vm.callself_stack:
        for b in self.vm.callself_stack[-1].bindings:
          b.data.maybe_missing_members = True
      return (node,
              self.vm.convert.create_new_unsolvable(node))
    substs = self._match_args(node, args)
    callargs = self._map_args(node, args)
    annotations = self.vm.annotations_util.sub_annotations(
        node, self.signature.annotations, substs)
    if annotations:
      for name in callargs:
        if name in annotations:
          node, _, callargs[name] = self.vm.init_class(
              node, annotations[name])
    # Might throw vm.RecursionException:
    frame = self.vm.make_frame(node, self.code, callargs,
                               self.f_globals, self.f_locals, self.closure,
                               new_locals=new_locals)
    if self.signature.has_return_annotation:
      frame.allowed_returns = annotations["return"]
    if self.vm.options.skip_repeat_calls:
      # TODO(tsudol): Hashing frame.f_locals.members should be the same as in
      # make_function above, but doing so causes infer to pollute the output
      # with type declarations from __builtin__. See test_python3.py:95 and
      # :104. Investigate why and change the hashing here if possible.
      callkey = self._hash_all(
          (callargs, None),
          (frame.f_globals.members, set(self.code.co_names)),
          (frame.f_locals.members, set(self.code.co_varnames)))
    else:
      # Make the callkey the number of times this function has been called so
      # that no call has the same key as a previous one.
      callkey = len(self._call_cache)
    if callkey in self._call_cache:
      _, old_ret, old_remaining_depth = self._call_cache[callkey]
      # Optimization: This function has already been called, with the same
      # environment and arguments, so recycle the old return value and don't
      # record this call. We pretend that this return value originated at the
      # current node to make sure we don't miss any possible types.
      # We would want to skip this optimization and reanalyze the call
      # if the all the possible types of the return value was unsolvable
      # and we can transverse the function deeper.
      if (all(x == self.vm.convert.unsolvable for x in old_ret.data) and
          self.vm.remaining_depth() > old_remaining_depth):
        log.info("Reanalyzing %r because all of its call record's bindings are "
                 "Unsolvable; remaining_depth = %d,"
                 "record remaining_depth = %d",
                 self.name, self.vm.remaining_depth(), old_remaining_depth)
      else:
        ret = self.vm.program.NewVariable(old_ret.data, [], node)
        if self._store_call_records:
          # Even if the call is cached, we might not have been recording it.
          self._call_records.append((callargs, ret, node))
        return node, ret
    if self.code.co_flags & loadmarshal.CodeType.CO_GENERATOR:
      generator = Generator(frame, self.vm)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for futher matching.
      node2, _ = generator.run_until_yield(node)
      node_after_call, ret = node2, generator.to_variable(node2)
    else:
      node_after_call, ret = self.vm.run_frame(frame, node)
    self._call_cache[callkey] = (callargs, ret, self.vm.remaining_depth())
    if self._store_call_records or self.vm.store_all_calls:
      self._call_records.append((callargs, ret, node_after_call))
    self.last_frame = frame
    return node_after_call, ret

  def get_call_combinations(self, node):
    """Get this function's call records."""
    all_combinations = []
    signature_data = set()
    for callargs, ret, node_after_call in self._call_records:
      try:
        combinations = utils.variable_product_dict(callargs)
      except utils.TooComplexError:
        combination = {name: self.vm.convert.unsolvable.to_variable(
            node_after_call).bindings[0] for name in callargs}
        combinations = [combination]
        ret = self.vm.convert.unsolvable.to_variable(node_after_call)
      for combination in combinations:
        for return_value in ret.bindings:
          values = combination.values() + [return_value]
          data = tuple(v.data for v in values)
          if data in signature_data:
            # This combination yields a signature we already know is possible
            continue
          if node_after_call.HasCombination(values):
            signature_data.add(data)
            all_combinations.append(
                (node_after_call, combination, return_value))
    if not all_combinations:
      # Fallback: Generate a PyTD signature only from the definition of the
      # method, not the way it's being used.
      param = (
          self.vm.convert.primitive_class_instances[object].to_variable(node))
      params = collections.defaultdict(lambda: param.bindings[0])
      ret = self.vm.convert.create_new_unsolvable(node).bindings[0]
      all_combinations.append((node, params, ret))
    return all_combinations

  def get_positional_names(self):
    return list(self.code.co_varnames[:self.code.co_argcount])

  def get_nondefault_params(self):
    for i in range(self.nonstararg_count):
      yield self.code.co_varnames[i], i >= self.code.co_argcount

  def get_kwonly_names(self):
    return list(
        self.code.co_varnames[self.code.co_argcount:self.nonstararg_count])

  def get_parameters(self):
    default_pos = self.code.co_argcount - len(self.defaults)
    i = 0
    for name in self.get_positional_names():
      yield name, False, i >= default_pos
      i += 1
    for name in self.get_kwonly_names():
      yield name, True, name in self.kw_defaults
      i += 1

  def has_varargs(self):
    return bool(self.code.co_flags & loadmarshal.CodeType.CO_VARARGS)

  def has_kwargs(self):
    return bool(self.code.co_flags & loadmarshal.CodeType.CO_VARKEYWORDS)


class BoundFunction(AtomicAbstractValue):
  """An function type which has had an argument bound into it."""

  def __init__(self, callself, callcls, underlying):
    super(BoundFunction, self).__init__(underlying.name, underlying.vm)
    self._callself = callself
    self._callcls = callcls
    self.underlying = underlying
    self.is_attribute_of_class = False

  def argcount(self):
    return self.underlying.argcount() - 1  # account for self

  @property
  def signature(self):
    return self.underlying.signature.drop_first_parameter()

  def call(self, node, func, args):
    if self.name == "__init__":
      self.vm.callself_stack.append(self._callself)
    try:
      return self.underlying.call(
          node, func, args.replace(posargs=(self._callself,) + args.posargs))
    except InvalidParameters as e:
      if self._callself and self._callself.bindings:
        e.name = "%s.%s" % (self._callself.data[0].name, e.name)
      raise
    finally:
      if self.name == "__init__":
        self.vm.callself_stack.pop()

  def get_positional_names(self):
    return self.underlying.get_positional_names()

  def has_varargs(self):
    return self.underlying.has_varargs()

  def has_kwargs(self):
    return self.underlying.has_kwargs()

  def get_class(self):
    return self.underlying.get_class()

  def __repr__(self):
    if self._callself and self._callself.bindings:
      callself = self._callself.data[0].name
    else:
      callself = "<class>"
    return callself + "." + repr(self.underlying)


class BoundInterpreterFunction(BoundFunction):
  """The method flavor of InterpreterFunction."""

  @contextlib.contextmanager
  def record_calls(self):
    with self.underlying.record_calls():
      yield

  def get_first_opcode(self):
    return self.underlying.code.co_code[0]


class BoundPyTDFunction(BoundFunction):
  pass


class Generator(Instance):
  """A representation of instances of generators.

  (I.e., the return type of coroutines).
  """

  def __init__(self, generator_frame, vm):
    super(Generator, self).__init__(vm.convert.generator_type, vm)
    self.generator_frame = generator_frame
    self.runs = 0

  def get_special_attribute(self, node, name, valself):
    if name == "__iter__":
      f = NativeFunction(name, self.__iter__, self.vm)
      return f.to_variable(node)
    elif name in ["next", "__next__"]:
      return self.to_variable(node)
    elif name == "throw":
      # We don't model exceptions in a way that would allow us to induce one
      # inside a coroutine. So just return ourself, mapping the call of
      # throw() to a next() (which won't be executed).
      return self.to_variable(node)
    else:
      return super(Generator, self).get_special_attribute(node, name, valself)

  def __iter__(self, node):  # pylint: disable=non-iterator-returned,unexpected-special-method-signature
    return node, self.to_variable(node)

  def run_until_yield(self, node):
    if self.runs == 0:  # Optimization: We only run the coroutine once.
      node, _ = self.vm.resume_frame(node, self.generator_frame)
      contained_type = self.generator_frame.yield_variable
      self.type_parameters[T] = contained_type
      self.runs += 1
    return node, self.type_parameters[T]

  def call(self, node, func, args):
    """Call this generator or (more common) its "next" attribute."""
    del func, args
    return self.run_until_yield(node)


class Iterator(Instance, HasSlots):
  """A representation of instances of iterators."""

  def __init__(self, vm, return_var):
    super(Iterator, self).__init__(vm.convert.iterator_type, vm)
    HasSlots.init_mixin(self)
    self.set_slot("next", self.next_slot)
    self.init_type_parameters(T)
    # TODO(dbaum): Should we set type_parameters[self.TYPE_PARAM] to something
    # based on return_var?
    self._return_var = return_var

  def next_slot(self, node):
    return node, self._return_var


# TODO(rechen): Merge this class with Empty.
class Nothing(AtomicAbstractValue):
  """The VM representation of Nothing values.

  These are fake values that never exist at runtime, but they appear if you, for
  example, extract a value from an empty list.
  """

  formal = True

  def __init__(self, vm):
    super(Nothing, self).__init__("nothing", vm)

  def call(self, node, func, args):
    raise AssertionError("Can't call empty object ('nothing')")

  def instantiate(self, node, container=None):
    return self.vm.convert.empty.to_variable(node)


class Module(Instance):
  """Represents an (imported) module."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, name, member_map):
    super(Module, self).__init__(vm.convert.module_type, vm)
    self.name = name
    self._member_map = member_map

  def _convert_member(self, name, ty):
    """Called to convert the items in _member_map to cfg.Variable."""
    var = self.vm.convert.constant_to_var(ty)
    for value in var.data:
      # Only do this if this class isn't already part of a module.
      # (This happens if e.g. foo.py does "from bar import x" and we then
      #  do "from foo import x".)
      if not value.module:
        value.module = self.name
    self.vm.trace_module_member(self, name, var)
    return var

  def has_getattr(self):
    """Does this module have a module-level __getattr__?

    We allow __getattr__ on the module level to specify that this module doesn't
    have any contents. The typical syntax is
      def __getattr__(name) -> Any
    .
    See https://www.python.org/dev/peps/pep-0484/#stub-files

    Returns:
      True if we have __getattr__.
    """
    f = self._member_map.get("__getattr__")
    if f:
      if isinstance(f, pytd.Function):
        if len(f.signatures) != 1:
          log.warning("overloaded module-level __getattr__ (in %s)", self.name)
        elif f.signatures[0].return_type != pytd.AnythingType():
          log.warning("module-level __getattr__ doesn't return Any (in %s)",
                      self.name)
        return True
      else:
        log.warning("__getattr__ in %s is not a function", self.name)
    return False

  def get_submodule(self, node, name):
    full_name = self.name + "." + name
    mod = self.vm.import_module(full_name, full_name, 0)  # 0: absolute import
    if mod is not None:
      return mod.to_variable(node)
    elif self.has_getattr():
      return self.vm.convert.create_new_unsolvable(node)
    else:
      log.warning("Couldn't find attribute / module %r", full_name)
      return None

  def items(self):
    return [(name, self._convert_member(name, ty))
            for name, ty in self._member_map.items()]


class BuildClass(AtomicAbstractValue):
  """Representation of the Python 3 __build_class__ object."""

  def __init__(self, vm):
    super(BuildClass, self).__init__("__build_class__", vm)

  def call(self, node, _, args):
    funcvar, name = args.posargs[0:2]
    if len(funcvar.bindings) != 1:
      raise ConversionError("Invalid ambiguous argument to __build_class__")
    func, = funcvar.data
    if not isinstance(func, InterpreterFunction):
      raise ConversionError("Invalid argument to __build_class__")
    bases = args.posargs[2:]
    node, _ = func.call(node, funcvar.bindings[0],
                        args.replace(posargs=(), namedargs={}),
                        new_locals=True)
    return node, self.vm.make_class(
        node, name, list(bases),
        func.last_frame.f_locals.to_variable(node), None)


class Unsolvable(AtomicAbstractValue):
  """Representation of value we know nothing about.

  Unlike "Unknowns", we don't treat these as solveable. We just put them
  where values are needed, but make no effort to later try to map them
  to named types. This helps conserve memory where creating and solving
  hundreds of unknowns would yield us little to no information.

  This is typically a singleton. Since unsolvables are indistinguishable, we
  only need one.
  """
  IGNORED_ATTRIBUTES = ["__get__", "__set__", "__getattribute__"]

  # Since an unsolvable gets generated e.g. for every unresolved import, we
  # can have multiple circular Unsolvables in a class' MRO. Treat those special.
  SINGLETON = True

  def __init__(self, vm):
    super(Unsolvable, self).__init__("unsolveable", vm)
    self.mro = self.default_mro()

  def get_special_attribute(self, node, name, _):
    if name in self.IGNORED_ATTRIBUTES:
      return None
    else:
      return self.to_variable(node)

  def call(self, node, func, args):
    del func, args
    # return ourself.
    return node, self.to_variable(node)

  def to_variable(self, node):
    return self.vm.program.NewVariable([self], source_set=[], where=node)

  def get_class(self):
    # return ourself.
    return self.to_variable(self.vm.root_cfg_node)

  def instantiate(self, node, container=None):
    # return ourself.
    return self.to_variable(node)


class Unknown(AtomicAbstractValue):
  """Representation of unknown values.

  These are e.g. the return values of certain functions (e.g. eval()). They
  "adapt": E.g. they'll respond to get_attribute requests by creating that
  attribute.

  Attributes:
    members: Attributes that were written or read so far. Mapping of str to
      typegraph.Variable.
    owner: typegraph.Binding that contains this instance as data.
  """

  _current_id = 0

  # For simplicity, Unknown doesn't emulate descriptors:
  IGNORED_ATTRIBUTES = ["__get__", "__set__", "__getattribute__"]

  def __init__(self, vm):
    name = "~unknown%d" % Unknown._current_id
    super(Unknown, self).__init__(name, vm)
    self.members = utils.MonitorDict()
    self.owner = None
    Unknown._current_id += 1
    self.class_name = self.name
    self._calls = []
    self.mro = self.default_mro()
    log.info("Creating %s", self.class_name)

  def get_fullhash(self):
    # Unknown needs its own implementation of get_fullhash to ensure equivalent
    # Unknowns produce the same hash. "Equivalent" in this case means "has the
    # same members," so member names are used in the hash instead of id().
    m = hashlib.md5()
    for name in self.members:
      m.update(name)
    return m.digest()

  def get_children_maps(self):
    return (self.members,)

  @staticmethod
  def _to_pytd(node, v):
    if isinstance(v, typegraph.Variable):
      return pytd_utils.JoinTypes(Unknown._to_pytd(node, t) for t in v.data)
    elif isinstance(v, Unknown):
      # Do this directly, and use NamedType, in case there's a circular
      # dependency among the Unknown instances.
      return pytd.NamedType(v.class_name)
    else:
      return v.to_type(node)

  @staticmethod
  def _make_params(node, args):
    """Convert a list of types/variables to pytd parameters."""
    return tuple(pytd.Parameter("_%d" % (i + 1), Unknown._to_pytd(node, p),
                                kwonly=False, optional=False,
                                mutated_type=None)
                 for i, p in enumerate(args))

  def get_special_attribute(self, node, name, valself):
    del node, valself
    if name in self.IGNORED_ATTRIBUTES:
      return None
    if name in self.members:
      return self.members[name]
    new = self.vm.convert.create_new_unknown(
        self.vm.root_cfg_node,
        action="getattr_" + self.name + ":" + name)
    # We store this at the root node, even though we only just created this.
    # From the analyzing point of view, we don't know when the "real" version
    # of this attribute (the one that's not an unknown) gets created, hence
    # we assume it's there since the program start.  If something overwrites it
    # in some later CFG node, that's fine, we'll then work only with the new
    # value, which is more accurate than the "fictional" value we create here.
    self.vm.attribute_handler.set_attribute(
        self.vm.root_cfg_node, self, name, new)
    return new

  def call(self, node, _, args):
    ret = self.vm.convert.create_new_unknown(
        node, source=self.owner, action="call:" + self.name)
    self._calls.append((args.posargs, args.namedargs, ret))
    return node, ret

  def to_variable(self, node):
    v = self.vm.program.NewVariable()
    val = v.AddBinding(self, source_set=[], where=node)
    self.owner = val
    self.vm.trace_unknown(self.class_name, v)
    return v

  def to_structural_def(self, node, class_name):
    """Convert this Unknown to a pytd.Class."""
    self_param = (pytd.Parameter("self", pytd.NamedType("__builtin__.object"),
                                 False, False, None),)
    # TODO(kramm): Record these.
    starargs = None
    starstarargs = None
    calls = tuple(pytd_utils.OrderedSet(
        pytd.Signature(self_param + self._make_params(node, args),
                       starargs,
                       starstarargs,
                       return_type=Unknown._to_pytd(node, ret),
                       exceptions=(),
                       template=())
        for args, _, ret in self._calls))
    if calls:
      methods = (pytd.Function("__call__", calls, pytd.METHOD),)
    else:
      methods = ()
    # TODO(rechen): Should we convert self.cls to a metaclass here as well?
    return pytd.Class(
        name=class_name,
        metaclass=None,
        parents=(pytd.NamedType("__builtin__.object"),),
        methods=methods,
        constants=tuple(pytd.Constant(name, Unknown._to_pytd(node, c))
                        for name, c in self.members.items()),
        template=())

  def get_class(self):
    # We treat instances of an Unknown as the same as the class.
    return self.to_variable(self.vm.root_cfg_node)

  def instantiate(self, node, container=None):
    return self.to_variable(node)


AMBIGUOUS_OR_EMPTY = (Unknown, Unsolvable, Empty)
