"""The abstract values used by vm.py."""

# Because pytype takes too long:
# pytype: skip-file

# Because of false positives:
# pylint: disable=unpacking-non-sequence
# pylint: disable=abstract-method

import collections
import contextlib
import hashlib
import inspect
import itertools
import logging

from pytype import compat
from pytype import datatypes
from pytype import function
from pytype import utils
from pytype.pyc import loadmarshal
from pytype.pyc import opcodes
from pytype.pytd import mro
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

import six

log = logging.getLogger(__name__)
chain = itertools.chain  # pylint: disable=invalid-name
WrapsDict = pytd_utils.WrapsDict  # pylint: disable=invalid-name


# Type parameter names matching the ones in __builtin__.pytd and typing.pytd.
T = "_T"
K = "_K"
V = "_V"
ARGS = "_ARGS"
RET = "_RET"


DYNAMIC_ATTRIBUTE_MARKERS = [
    "HAS_DYNAMIC_ATTRIBUTES",
    "_HAS_DYNAMIC_ATTRIBUTES",
    "has_dynamic_attributes",
    "_has_dynamic_attributes",
]


class ConversionError(ValueError):
  pass


class GenericTypeError(Exception):
  """The error for user-defined generic types."""

  def __init__(self, annot, error):
    super(GenericTypeError, self).__init__(annot, error)
    self.annot = annot
    self.error = error


class AsInstance(object):
  """Wrapper, used for marking things that we want to convert to an instance."""

  def __init__(self, cls):
    self.cls = cls


class AsReturnValue(AsInstance):
  """Specially mark return values, to handle NoReturn properly."""


# For lazy evaluation of ParameterizedClass.formal_type_parameters
LazyFormalTypeParameters = collections.namedtuple(
    "LazyFormalTypeParameters", ("template", "parameters", "subst"))


_NONE = object()  # sentinel for get_atomic_value


def get_atomic_value(variable, constant_type=None, default=_NONE):
  """Get the atomic value stored in this variable."""
  if len(variable.bindings) == 1:
    v, = variable.bindings
    if isinstance(v.data, constant_type or object):
      return v.data  # success
  if default is not _NONE:
    # If a default is specified, we return it instead of failing.
    return default
  # Determine an appropriate failure message.
  if not variable.bindings:
    raise ConversionError("Cannot get atomic value from empty variable.")
  bindings = variable.bindings
  name = bindings[0].data.vm.convert.constant_name(constant_type)
  raise ConversionError(
      "Cannot get atomic value %s from variable. %s %s"
      % (name, variable, [b.data for b in bindings]))


def get_atomic_python_constant(variable, constant_type=None):
  """Get the concrete atomic Python value stored in this variable.

  This is used for things that are stored in cfg.Variable, but we
  need the actual data in order to proceed. E.g. function / class definitions.

  Args:
    variable: A cfg.Variable. It can only have one possible value.
    constant_type: Optionally, the required type of the constant.
  Returns:
    A Python constant. (Typically, a string, a tuple, or a code object.)
  Raises:
    ConversionError: If the value in this Variable is purely abstract, i.e.
      doesn't store a Python value, or if it has more than one possible value.
  """
  atomic = get_atomic_value(variable)
  return atomic.vm.convert.value_to_constant(atomic, constant_type)


def merge_values(values, vm):
  """Merge a collection of values into a single one."""
  if not values:
    return vm.convert.empty
  elif len(values) == 1:
    return next(iter(values))
  else:
    return Union(values, vm)


def get_views(variables, node, filter_strict=False):
  """Get all possible views of the given variables at a particular node.

  This function can be used either as a regular generator or in an optimized way
  to yield only functionally unique views:
    views = get_views(...)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      ...
    The caller should set `skip_future` to True when it is safe to skip
    equivalent future views and False otherwise.

  Args:
    variables: The variables.
    node: The node.
    filter_strict: If True, emit a view only when node.HasCombination is
      satisfied; else, use the faster node.CanHaveCombination.

  Yields:
    A datatypes.AcessTrackingDict mapping variables to bindings.
  """
  try:
    combinations = cfg_utils.deep_variable_product(variables)
  except cfg_utils.TooComplexError:
    combinations = ((var.AddBinding(node.program.default_data, [], node)
                     for var in variables),)
  seen = []  # the accessed subsets of previously seen views
  for combination in combinations:
    view = {value.variable: value for value in combination}
    if any(subset <= six.viewitems(view) for subset in seen):
      # Optimization: This view can be skipped because it matches the accessed
      # subset of a previous one.
      log.info("Skipping view (already seen): %r", view)
      continue
    combination = list(view.values())
    check = node.HasCombination if filter_strict else node.CanHaveCombination
    if not check(combination):
      log.info("Skipping combination (unreachable): %r", combination)
      continue
    view = datatypes.AccessTrackingDict(view)
    skip_future = yield view
    if skip_future:
      # Skip future views matching this accessed subset.
      seen.append(six.viewitems(view.accessed_subset))


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


def func_name_is_class_init(name):
  """Return True if |name| is that of a class' __init__ method."""
  # Python 3's MAKE_FUNCTION byte code takes an explicit fully qualified
  # function name as an argument and that is used for the function name.
  # On the other hand, Python 2's MAKE_FUNCTION does not take any name
  # argument so we pick the name from the code object. This name is not
  # fully qualified. Hence, constructor names in Python 3 are fully
  # qualified ending in '.__init__', and constructor names in Python 2
  # are all '__init__'. So, we identify a constructor by matching its
  # name with one of these patterns.
  return name == "__init__" or name.endswith(".__init__")


def has_type_parameters(node, val, seen=None):
  """Checks if the given object contains any TypeParameters.

  Args:
    node: The current CFG node.
    val: The object to check for TypeParameters. Will likely be a
      SimpleAbstractValue or a cfg.Variable with SimpleAbstractValues bindings.
    seen: Optional. A set of already-visited objects, to avoid infinite loops.

  Returns:
    True if the object contains any TypeParameters, or False otherwise.
  """
  if seen is None:
    seen = set()
  if val in seen:
    return False
  seen.add(val)
  if isinstance(val, cfg.Variable):
    return any((has_type_parameters(node, d, seen) for d in val.data))
  elif isinstance(val, TypeParameter):
    return True
  elif isinstance(val, (ParameterizedClass, Union)):
    return val.formal
  elif isinstance(val, SimpleAbstractValue):
    return any((has_type_parameters(node, tp, seen)
                for tp in val.instance_type_parameters.values()))
  else:
    return False


def equivalent_to(binding, cls):
  """Whether binding.data is equivalent to cls, modulo parameterization."""
  return (isinstance(binding.data, Class) and
          binding.data.full_name == cls.full_name)


def _apply_mutations(node, get_mutations):
  """Apply mutations yielded from a get_mutations function."""
  log.info("Applying mutations")
  num_mutations = 0
  for obj, name, value in get_mutations():
    if not num_mutations:
      # mutations warrant creating a new CFG node
      node = node.ConnectNew(node.name)
    num_mutations += 1
    obj.merge_instance_type_parameter(node, name, value)
  log.info("Applied %d mutations", num_mutations)
  return node


def _get_template(val):
  """Get the value's class template."""
  if isinstance(val, Class):
    res = {t.full_name for t in val.template}
    if isinstance(val, ParameterizedClass):
      res.update(_get_template(val.base_cls))
    elif isinstance(val, (PyTDClass, InterpreterClass)):
      for base in val.bases():
        base = _get_class(base, default=val.vm.convert.unsolvable)
        res.update(_get_template(base))
    return res
  elif isinstance(val, AtomicAbstractValue):
    return _get_template(val.cls)
  else:
    return set()


def _get_mro_bases(bases):
  """Get bases for MRO computation."""
  mro_bases = []
  has_user_generic = False
  for base_var in bases:
    if not base_var.data:
      continue
    # A base class is a Variable. If it has multiple options, we would
    # technically get different MROs. But since ambiguous base classes are rare
    # enough, we instead just pick one arbitrary option per base class.
    base = _get_class(base_var)
    mro_bases.append(base)
    # check if it contains user-defined generic types
    if (isinstance(base, ParameterizedClass)
        and base.full_name != "typing.Generic"):
      has_user_generic = True
  # if user-defined generic type exists, we won't add `typing.Generic` to
  # the final result list
  if has_user_generic:
    return [b for b in mro_bases if b.full_name != "typing.Generic"]
  else:
    return mro_bases


def parse_formal_type_parameters(base, prefix, formal_type_parameters):
  """Parse type parameters from base class.

  Args:
    base: base class.
    prefix: the full name of subclass of base class.
    formal_type_parameters: the mapping of type parameter name to its type

  Raises:
    GenericTypeError: If the lazy types of type parameter don't match
  """
  if isinstance(base, ParameterizedClass):
    if base.full_name == "typing.Generic":
      return
    if isinstance(base.base_cls, (InterpreterClass, PyTDClass)):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(
          base.base_cls.all_formal_type_parameters)
    params = base.get_formal_type_parameters()
    for name, param in params.items():
      if isinstance(param, TypeParameter):
        # We have type parameter renaming, e.g.,
        #  class List(Generic[T]): pass
        #  class Foo(List[U]): pass
        if prefix:
          formal_type_parameters.add_alias(name, prefix + "." + param.name)
      else:
        # We have either a non-formal parameter, e.g.,
        # class Foo(List[int]), or a non-1:1 parameter mapping, e.g.,
        # class Foo(List[K or V]). Initialize the corresponding instance
        # parameter appropriately.
        if name not in formal_type_parameters:
          formal_type_parameters[name] = param
        else:
          # Two unrelated containers happen to use the same type
          # parameter but with different types.
          pre_type = formal_type_parameters[name]
          cur_type = param
          # pre_type is parent of cur_type
          if pre_type in cur_type.mro:
            formal_type_parameters[name] = param
          # they don't have inheritance relationship
          elif not pre_type or cur_type not in pre_type.mro:
            raise GenericTypeError(base,
                                   "Conflicting value for TypeVar %s" % name)
  else:
    if isinstance(base, (InterpreterClass, PyTDClass)):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(base.all_formal_type_parameters)
    if base.template:
      # handle unbound type parameters
      for item in base.template:
        if isinstance(item, TypeParameter):
          # This type parameter will be set as `ANY`.
          formal_type_parameters[base.full_type_name(item.name)] = None


def _get_class(cls_var, default=None):
  """Get class from a class variable."""
  if not cls_var.data:
    return default
  # If it has multiple options, we pick one arbitrary option.
  return min(cls_var.data, key=lambda cls: cls.full_name)


class AtomicAbstractValue(utils.VirtualMachineWeakrefMixin):
  """A single abstract value such as a type or function signature.

  This is the base class of the things that appear in Variables. It represents
  an atomic object that the abstract interpreter works over just as variables
  represent sets of parallel options.

  Conceptually abstract values represent sets of possible concrete values in
  compact form. For instance, an abstract value with .__class__ = int represents
  all ints.
  """

  CAN_BE_ABSTRACT = False  # True for functions and properties.

  formal = False  # is this type non-instantiable?

  def __init__(self, name, vm):
    """Basic initializer for all AtomicAbstractValues."""
    super(AtomicAbstractValue, self).__init__(vm)
    assert hasattr(vm, "program"), type(self)
    self.cls = None
    self.name = name
    self.mro = self.compute_mro()
    self.module = None
    self.official_name = None
    self.late_annotations = {}
    self.slots = None  # writable attributes (or None if everything is writable)
    self._template = None  # template for current class
    # names in the templates of the current class and its base classes
    self._all_template_names = None
    self._instance = None

  @property
  def all_template_names(self):
    if self._all_template_names is None:
      self._all_template_names = _get_template(self)
    return self._all_template_names

  @property
  def template(self):
    if self._template is None:
      # Won't recompute if `_compute_template` throws exception
      self._template = ()
      self._template = self._compute_template()
    return self._template

  def _compute_template(self):
    return ()

  @property
  def full_name(self):
    return (self.module + "." if self.module else "") + self.name

  def full_type_name(self, name):
    """Compute complete type parameter name with scope."""
    if isinstance(self, Instance):
      template, all_template_names = (self.cls.template,
                                      self.cls.all_template_names)
    else:
      template, all_template_names = self.template, self.all_template_names
    # The type is in current `class`
    for t in template:
      if t.name == name:
        return self.full_name + "." + name
      elif t.full_name == name:
        return t.full_name
    # The type is instantiated in `base class`
    for t in all_template_names:
      if t.split(".")[-1] == name or t == name:
        return t
    return name

  def __repr__(self):
    return self.name

  def compute_mro(self):
    # default for objects with no MRO
    return []

  def default_mro(self):
    # default for objects with unknown MRO
    return [self, self.vm.convert.object_type]

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
      m.update(compat.bytestring(data_id))
      for mapping in data.get_children_maps():
        m.update(compat.bytestring(mapping.changestamp))
        stack.extend(mapping.data)
    return m.digest()

  def get_children_maps(self):
    """Get this value's dictionaries of children.

    Returns:
      A sequence of dictionaries from names to child values.
    """
    return ()

  def get_instance_type_parameter(self, name, node=None):
    """Get a cfg.Variable of the instance's values for the type parameter.

    Treating self as an abstract.Instance, gets the variable of its values for
    the given type parameter. For the real implementation, see
    SimpleAbstractValue.get_instance_type_parameter.

    Args:
      name: The name of the type parameter.
      node: Optionally, the current CFG node.
    Returns:
      A Variable which may be empty.
    """
    del name
    if node is None:
      node = self.vm.root_cfg_node
    return self.vm.convert.create_new_unsolvable(node)

  def get_formal_type_parameter(self, t):
    """Get the class's type for the type parameter.

    Treating self as an abstract.Class, gets its formal type for the given
    type parameter. For the real implementation, see
    ParameterizedClass.get_formal_type_parameter.

    Args:
      t: The name of the type parameter.
    Returns:
      A formal type.
    """
    del t
    return self.vm.convert.unsolvable

  def property_get(self, callself, is_class=False):
    """Bind this value to the given self or cls.

    This function is similar to __get__ except at the abstract level. This does
    not trigger any code execution inside the VM. See __get__ for more details.

    Args:
      callself: The Variable that should be passed as self or cls when the call
        is made. We only need one of self or cls, so having them share a
        parameter prevents accidentally passing in both.
      is_class: Whether callself is self or cls. Should be cls only when we
        want to directly pass in a class to bind a class method to, rather than
        passing in an instance and calling get_class().

    Returns:
      Another abstract value that should be returned in place of this one. The
      default implementation returns self, so this can always be called safely.
    """
    del callself, is_class
    return self

  def get_special_attribute(self, unused_node, name, unused_valself):
    """Fetch a special attribute (e.g., __get__, __iter__)."""
    if name == "__class__":
      return self.get_class().to_variable(self.vm.root_cfg_node)
    return None

  def get_own_new(self, node, value):
    """Get this value's __new__ method, if it isn't object.__new__."""
    del value  # Unused, only classes have methods.
    return node, None

  def call(self, node, func, args, alias_map=None):
    """Call this abstract value with the given arguments.

    The posargs and namedargs arguments may be modified by this function.

    Args:
      node: The CFGNode calling this function
      func: The cfg.Binding containing this function.
      args: Arguments for the call.
      alias_map: A datatypes.UnionFind, which stores all the type renaming
        information, mapping of type parameter name to its representative.
    Returns:
      A tuple (cfg.Node, cfg.Variable). The CFGNode corresponds
      to the function's "return" statement(s).
    Raises:
      FailedFunctionCall

    Make the call as required by this specific kind of atomic value, and make
    sure to annotate the results correctly with the origins (val and also other
    values appearing in the arguments).
    """
    raise NotImplementedError(self.__class__.__name__)

  def argcount(self, node):
    """Returns the minimum number of arguments needed for a call."""
    raise NotImplementedError(self.__class__.__name__)

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
    return Instance(self, self.vm).to_variable(node)

  def to_variable(self, node):
    """Build a variable out of this abstract value.

    Args:
      node: The current CFG node.
    Returns:
      A cfg.Variable.
    Raises:
      ValueError: If origins is an empty sequence. This is to prevent you from
        creating variables that have no origin and hence can never be used.
    """
    v = self.vm.program.NewVariable()
    v.AddBinding(self, source_set=[], where=node)
    return v

  def to_binding(self, node):
    binding, = self.to_variable(node).bindings
    return binding

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
    return []

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
  convert.Converter._function_to_def and analyze.CallTracer.pytd_for_types.
  """

  def __init__(self, vm):
    super(Empty, self).__init__("empty", vm)

  def get_special_attribute(self, node, name, valself):
    del name, valself
    return self.to_variable(node)

  def call(self, node, func, args, alias_map=None):
    del func, args
    return node, self.to_variable(node)

  def get_class(self):
    return self

  def instantiate(self, node, container=None):
    return self.to_variable(node)


class Deleted(Empty):
  """Assigned to variables that have del called on them."""

  def __init__(self, vm):
    super(Deleted, self).__init__(vm)
    self.name = "deleted"


class MixinMeta(type):
  """Metaclass for mix-ins."""

  def __init__(cls, name, superclasses, *args, **kwargs):
    super(MixinMeta, cls).__init__(name, superclasses, *args, **kwargs)
    for sup in superclasses:
      if hasattr(sup, "overloads"):
        for method in sup.overloads:
          if method not in cls.__dict__:
            setattr(cls, method, getattr(sup, method))
            # Record the fact that we have set a method on the class, to do
            # superclass lookups.
            if "__mixin_overloads__" in cls.__dict__:
              cls.__mixin_overloads__["method"] = sup
            else:
              setattr(cls, "__mixin_overloads__", {method: sup})

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
      if ("__mixin_overloads__" in supercls.__dict__ and
          supercls.__mixin_overloads__.get(method.__name__) is cls):
        method_cls = supercls
        break
    return getattr(super(method_cls, method.__self__), method.__name__)


@six.add_metaclass(MixinMeta)
class PythonConstant(object):
  """A mix-in for storing actual Python constants, not just their types.

  This is used for things that are stored in cfg.Variable, but where we
  may need the actual data in order to proceed later. E.g. function / class
  definitions, tuples. Also, potentially: Small integers, strings (E.g. "w",
  "r" etc.).
  """

  overloads = ("__repr__", "compatible_with",)

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
    return "<%s %r>" % (self.name, self.str_of_constant(str))

  def compatible_with(self, logical_value):
    return bool(self.pyval) == logical_value


class TypeParameter(AtomicAbstractValue):
  """Parameter of a type."""

  formal = True

  def __init__(self, name, vm, constraints=(), bound=None,
               covariant=False, contravariant=False, module=None):
    super(TypeParameter, self).__init__(name, vm)
    self.constraints = constraints
    self.bound = bound
    self.covariant = covariant
    self.contravariant = contravariant
    self.module = module

  def is_generic(self):
    return not self.constraints and not self.bound

  def copy(self):
    return TypeParameter(self.name, self.vm, self.constraints, self.bound,
                         self.covariant, self.contravariant, self.module)

  def with_module(self, module):
    res = self.copy()
    res.module = module
    return res

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return (self.name == other.name and
              self.constraints == other.constraints and
              self.bound == other.bound and
              self.covariant == other.covariant and
              self.contravariant == other.contravariant and
              self.module == other.module)
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash((self.name, self.constraints, self.bound, self.covariant,
                 self.contravariant))

  def __repr__(self):
    return "TypeParameter(%r, constraints=%r, bound=%r, module=%r)" % (
        self.name, self.constraints, self.bound, self.module)

  def instantiate(self, node, container=None):
    var = self.vm.program.NewVariable()
    if container and (not isinstance(container, SimpleAbstractValue) or
                      self.full_name in container.all_template_names):
      instance = TypeParameterInstance(self, container, self.vm)
      return instance.to_variable(node)
    else:
      for c in self.constraints:
        var.PasteVariable(c.instantiate(node, container))
      if self.bound:
        var.PasteVariable(self.bound.instantiate(node, container))
    if not var.bindings:
      var.AddBinding(self.vm.convert.unsolvable, [], node)
    return var

  def update_official_name(self, name):
    if self.name != name:
      message = "TypeVar(%r) must be stored as %r, not %r" % (
          self.name, self.name, name)
      self.vm.errorlog.invalid_typevar(self.vm.frames, message)

  def get_class(self):
    return self


class TypeParameterInstance(AtomicAbstractValue):
  """An instance of a type parameter."""

  def __init__(self, param, instance, vm):
    super(TypeParameterInstance, self).__init__(param.name, vm)
    self.param = param
    self.instance = instance
    self.module = param.module

  def get_class(self):
    return self.param

  def call(self, node, func, args, alias_map=None):
    var = self.instance.get_instance_type_parameter(self.name)
    if var.bindings:
      return self.vm.call_function(node, var, args)
    else:
      return node, self.vm.convert.empty.to_variable(self.vm.root_cfg_node)

  def __repr__(self):
    return "TypeParameterInstance(%r)" % self.name

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.param == other.param and self.instance == other.instance
    return NotImplemented

  def __hash__(self):
    return hash((self.param, self.instance))


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
    self.members = datatypes.MonitorDict()
    # Lazily loaded to handle recursive types.
    # See Instance._load_instance_type_parameters().
    self._instance_type_parameters = datatypes.AliasingMonitorDict()
    self.maybe_missing_members = False
    # The latter caches the result of get_type_key. This is a recursive function
    # that has the potential to generate too many calls for large definitions.
    self._cached_type_key = (
        (self.members.changestamp, self._instance_type_parameters.changestamp),
        None)

  @property
  def instance_type_parameters(self):
    return self._instance_type_parameters

  def has_instance_type_parameter(self, name):
    """Check if the key is in `instance_type_parameters`."""
    name = self.full_type_name(name)
    return name in self.instance_type_parameters

  def get_children_maps(self):
    return (self.instance_type_parameters, self.members)

  def get_instance_type_parameter(self, name, node=None):
    name = self.full_type_name(name)
    param = self.instance_type_parameters.get(name)
    if not param:
      log.info("Creating new empty type param %s", name)
      if node is None:
        node = self.vm.root_cfg_node
      param = self.vm.program.NewVariable([], [], node)
      self.instance_type_parameters[name] = param
    return param

  def merge_instance_type_parameter(self, node, name, value):
    """Set the value of a type parameter.

    This will always add to the type parameter unlike set_attribute which will
    replace value from the same basic block. This is because type parameters may
    be affected by a side effect so we need to collect all the information
    regardless of multiple assignments in one basic block.

    Args:
      node: Optionally, the current CFG node.
      name: The name of the type parameter.
      value: The value that is being used for this type parameter as a Variable.
    """
    name = self.full_type_name(name)
    log.info("Modifying type param %s", name)
    if name in self.instance_type_parameters:
      self.instance_type_parameters[name].PasteVariable(value, node)
    else:
      self.instance_type_parameters[name] = value

  def load_lazy_attribute(self, name):
    """Load the named attribute into self.members."""
    if name not in self.members and name in self._member_map:
      variable = self._convert_member(name, self._member_map[name])
      assert isinstance(variable, cfg.Variable)
      self.members[name] = variable

  def call(self, node, _, args, alias_map=None):
    node, var = self.vm.attribute_handler.get_attribute(
        node, self, "__call__", self.to_binding(node))
    if var is not None and var.bindings:
      return self.vm.call_function(node, var, args)
    else:
      raise NotCallable(self)

  def argcount(self, node):
    node, var = self.vm.attribute_handler.get_attribute(
        node, self, "__call__", self.to_binding(node))
    if var and var.bindings:
      return min(v.argcount(node) for v in var.data)
    else:
      # It doesn't matter what we return here, since any attempt to call this
      # value will lead to a not-callable error anyways.
      return 0

  def __repr__(self):
    cls = " [%r]" % self.cls if self.cls else ""
    return "<%s%s>" % (self.name, cls)

  def get_class(self):
    # See Py_TYPE() in Include/object.h
    if self.cls:
      return self.cls
    elif isinstance(self, (AnnotationClass, Class)):
      return self.vm.convert.type_type

  def set_class(self, node, var):
    """Set the __class__ of an instance, for code that does "x.__class__ = y."""
    # Simplification: Setting __class__ is done rarely, and supporting this
    # action would complicate pytype considerably by forcing us to track the
    # class in a variable, so we instead fall back to Any.
    try:
      new_cls = get_atomic_value(var)
    except ConversionError:
      self.cls = self.vm.convert.unsolvable
    else:
      if self.cls and self.cls != new_cls:
        self.cls = self.vm.convert.unsolvable
      else:
        self.cls = new_cls
        new_cls.register_instance(self)
    return node

  def get_type_key(self, seen=None):
    cached_changestamps, saved_key = self._cached_type_key
    if saved_key and cached_changestamps == (
        self.members.changestamp,
        self.instance_type_parameters.changestamp):
      return saved_key
    if not seen:
      seen = set()
    seen.add(self)
    key = set()
    if self.cls:
      key.add(self.cls)
    for name, var in self.instance_type_parameters.items():
      subkey = frozenset(value.data.get_default_type_key() if value.data in seen
                         else value.data.get_type_key(seen)
                         for value in var.bindings)
      key.add((name, subkey))
    if key:
      type_key = frozenset(key)
    else:
      type_key = super(SimpleAbstractValue, self).get_type_key()
    self._cached_type_key = (
        (self.members.changestamp, self.instance_type_parameters.changestamp),
        type_key)
    return type_key

  def _unique_parameters(self):
    parameters = super(SimpleAbstractValue, self)._unique_parameters()
    parameters.extend(self.instance_type_parameters.values())
    return parameters


class Instance(SimpleAbstractValue):
  """An instance of some object."""

  # Fully qualified names of types that are parameterized containers.
  _CONTAINER_NAMES = set([
      "__builtin__.list", "__builtin__.set", "__builtin__.frozenset"])

  def __init__(self, cls, vm):
    super(Instance, self).__init__(cls.name, vm)
    self.cls = cls
    self._instance_type_parameters_loaded = False
    if isinstance(cls, (InterpreterClass, PyTDClass)) and cls.is_dynamic:
      self.maybe_missing_members = True
    cls.register_instance(self)

  def _load_instance_type_parameters(self):
    if self._instance_type_parameters_loaded:
      return
    all_formal_type_parameters = datatypes.AliasingMonitorDict()
    parse_formal_type_parameters(self.cls, None, all_formal_type_parameters)
    self._instance_type_parameters.uf = all_formal_type_parameters.uf
    for name, param in all_formal_type_parameters.items():
      if param is None:
        value = self.vm.program.NewVariable()
        log.info("Initializing type param %s: %r", name, value)
        self._instance_type_parameters[name] = value
      else:
        self._instance_type_parameters[name] = param.instantiate(
            self.vm.root_cfg_node, self)
    # We purposely set this flag at the very end so that accidentally accessing
    # instance_type_parameters during loading will trigger an obvious crash due
    # to infinite recursion, rather than silently returning an incomplete dict.
    self._instance_type_parameters_loaded = True

  def compatible_with(self, logical_value):  # pylint: disable=unused-argument
    # Containers with unset parameters and NoneType instances cannot match True.
    name = self.full_name
    if logical_value and name in Instance._CONTAINER_NAMES:
      return (self.has_instance_type_parameter(T) and
              bool(self.get_instance_type_parameter(T).bindings))
    elif name == "__builtin__.NoneType":
      return not logical_value
    return True

  @property
  def full_name(self):
    return self.get_class().full_name

  @property
  def instance_type_parameters(self):
    self._load_instance_type_parameters()
    return self._instance_type_parameters


@six.add_metaclass(MixinMeta)
class HasSlots(object):
  """Mix-in for overriding slots with custom methods.

  This makes it easier to emulate built-in classes like dict which need special
  handling of some magic methods (__setitem__ etc.)
  """

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
        self.to_binding(self.vm.root_cfg_node))
    self._super[name] = attr
    f = self.make_native_function(name, method)
    self._slots[name] = f.to_variable(self.vm.root_cfg_node)

  def call_pytd(self, node, name, *args):
    """Call the (original) pytd version of a method we overwrote."""
    return self.vm.call_function(node, self._super[name], FunctionArgs(args),
                                 fallback_to_unsolvable=False)

  def get_special_attribute(self, node, name, valself):
    if name in self._slots:
      attr = self.vm.program.NewVariable()
      additional_sources = {valself} if valself else None
      attr.PasteVariable(self._slots[name], node, additional_sources)
      return attr
    return HasSlots.super(self.get_special_attribute)(node, name, valself)


class List(Instance, HasSlots, PythonConstant):
  """Representation of Python 'list' objects."""

  def __init__(self, content, vm):
    super(List, self).__init__(vm.convert.list_type, vm)
    self._instance_cache = {}
    PythonConstant.init_mixin(self, content)
    HasSlots.init_mixin(self)
    combined_content = vm.convert.build_content(content)
    self.merge_instance_type_parameter(None, T, combined_content)
    self.could_contain_anything = False
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__getslice__", self.getslice_slot)

  def str_of_constant(self, printer):
    return "[%s]" % ", ".join(" or ".join(printer(v) for v in val.data)
                              for val in self.pyval)

  def __repr__(self):
    if self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return PythonConstant.__repr__(self)

  def merge_instance_type_parameter(self, node, name, value):
    self.could_contain_anything = True
    super(List, self).merge_instance_type_parameter(node, name, value)

  def compatible_with(self, logical_value):
    return (self.could_contain_anything or
            PythonConstant.compatible_with(self, logical_value))

  def getitem_slot(self, node, index_var):
    """Implements __getitem__ for List.

    Arguments:
      node: The current CFG node.
      index_var: The Variable containing the index value, the i in lst[i].

    Returns:
      Tuple of (node, return_variable). node may be the same as the argument.
      return_variable is a Variable with bindings of the possible return values.
    """
    results = []
    unresolved = False
    node, ret = self.call_pytd(node, "__getitem__", index_var)
    if not self.could_contain_anything:
      for val in index_var.bindings:
        try:
          index = self.vm.convert.value_to_constant(val.data, int)
        except ConversionError:
          unresolved = True
        else:
          self_len = len(self.pyval)
          if -self_len <= index < self_len:
            results.append(self.pyval[index])
          else:
            unresolved = True
    if unresolved or self.could_contain_anything:
      results.append(ret)
    return node, self.vm.join_variables(node, results)

  def _get_index(self, data):
    """Helper function for getslice_slot that extracts int or None from data.

    If data is an Instance of int, None is returned. This may happen when
    vm.py:get_slice replaces an argument with an Instance of int.

    Args:
      data: The object to extract from. Usually an AbstractOrConcreteValue or an
        Instance.

    Returns:
      The value (an int or None) of the index.

    Raises:
      ConversionError: If the data could not be converted to an int or None.
    """
    if isinstance(data, AbstractOrConcreteValue):
      return self.vm.convert.value_to_constant(data, (int, type(None)))
    elif isinstance(data, Instance):
      if data.cls != self.vm.convert.int_type:
        raise ConversionError()
      else:
        return None
    else:
      raise ConversionError()

  def getslice_slot(self, node, start_var, end_var):
    """Implements __getslice__ for List.

    Arguments:
      node: The current CFG node.
      start_var: A Variable containing the i in lst[i:j].
      end_var: A Variable containing the j in lst[i:j].

    Returns:
      Tuple of (node, return_variable). node may be the same as the argument.
      return_variable is a Variable with bindings of the possible return values.
    """
    # call_pytd will typecheck start_var and end_var.
    node, ret = self.call_pytd(node, "__getslice__", start_var, end_var)
    results = []
    unresolved = False
    if not self.could_contain_anything:
      for start_val, end_val in cfg_utils.variable_product([start_var,
                                                            end_var]):
        try:
          start = self._get_index(start_val.data)
          end = self._get_index(end_val.data)
        except ConversionError:
          unresolved = True
        else:
          results.append(List(self.pyval[start:end], self.vm).to_variable(node))
    if unresolved or self.could_contain_anything:
      results.append(ret)
    return node, self.vm.join_variables(node, results)


class Tuple(Instance, PythonConstant):
  """Representation of Python 'tuple' objects."""

  def __init__(self, content, vm):
    combined_content = vm.convert.build_content(content)
    class_params = {name: vm.convert.merge_classes(vm.root_cfg_node,
                                                   instance_param.data)
                    for name, instance_param in
                    tuple(enumerate(content)) + ((T, combined_content),)}
    cls = TupleClass(vm.convert.tuple_type, class_params, vm)
    super(Tuple, self).__init__(cls, vm)
    self.merge_instance_type_parameter(None, T, combined_content)
    PythonConstant.init_mixin(self, content)
    self.tuple_length = len(self.pyval)
    self._hash = None  # memoized due to expensive computation

  def str_of_constant(self, printer):
    content = ", ".join(" or ".join(printer(v) for v in val.data)
                        for val in self.pyval)
    if self.tuple_length == 1:
      content += ","
    return "(%s)" % content

  def _unique_parameters(self):
    parameters = super(Tuple, self)._unique_parameters()
    parameters.extend(self.pyval)
    return parameters

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return (self.tuple_length == other.tuple_length and
              all(e.data == other_e.data
                  for e, other_e in zip(self.pyval, other.pyval)))
    return NotImplemented

  def __hash__(self):
    if self._hash is None:
      # Descending into pyval would trigger infinite recursion in the case of a
      # tuple containing itself, so we approximate the inner values with their
      # full names.
      self._hash = hash((self.tuple_length,) +
                        tuple(tuple(v.full_name for v in e.data)
                              for e in self.pyval))
    return self._hash


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
    self.set_slot("pop", self.pop_slot)
    self.set_slot("setdefault", self.setdefault_slot)
    self.set_slot("update", self.update_slot)
    self.could_contain_anything = False
    # Use OrderedDict instead of dict, so that it can be compatible with
    # where needs ordered dict.
    # For example: f_locals["__annotations__"]
    PythonConstant.init_mixin(self, collections.OrderedDict())

  def str_of_constant(self, printer):
    return str({name: " or ".join(printer(v) for v in value.data)
                for name, value in self.pyval.items()})

  def __repr__(self):
    if not hasattr(self, "could_contain_anything"):
      return "Dict (not fully initialized)"
    elif self.could_contain_anything:
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
    self.merge_instance_type_parameter(
        node, K, self.vm.convert.build_string(node, name))
    self.merge_instance_type_parameter(node, V, value_var)
    if name in self.pyval:
      self.pyval[name].PasteVariable(value_var, node)
    else:
      self.pyval[name] = value_var
    return node

  def setitem(self, node, name_var, value_var):
    assert isinstance(name_var, cfg.Variable)
    assert isinstance(value_var, cfg.Variable)
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
    # Hack to allow storing types with parameters in a dict (needed for
    # python3.6 function annotation support). A dict assigned to a visible
    # variable will be inferred as Dict[key_type, Any], but the pyval will
    # contain the data we need for annotations.
    if any(has_type_parameters(node, x) for x in value_var.data):
      value_var = self.vm.convert.unsolvable.to_variable(node)
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

  def pop_slot(self, node, key_var, default_var=None):
    try:
      str_key = get_atomic_python_constant(key_var, str)
    except ConversionError:
      self.could_contain_anything = True
    if self.could_contain_anything:
      if default_var:
        return self.call_pytd(node, "pop", key_var, default_var)
      else:
        return self.call_pytd(node, "pop", key_var)
    if default_var:
      return node, self.pyval.pop(str_key, default_var)
    else:
      try:
        return node, self.pyval.pop(str_key)
      except KeyError:
        raise DictKeyMissing(str_key)

  def update_slot(self, node, *args, **kwargs):
    posargs_handled = False
    if len(args) == 1:
      arg_data = args[0].data
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
        k = other_dict.get_instance_type_parameter(K, node)
        v = other_dict.get_instance_type_parameter(V, node)
        self.merge_instance_type_parameter(node, K, k)
        self.merge_instance_type_parameter(node, V, v)
        self.could_contain_anything |= other_dict.could_contain_anything
    else:
      assert isinstance(other_dict, AtomicAbstractValue)
      if (isinstance(other_dict, Instance) and
          other_dict.full_name == "__builtin__.dict"):
        k = other_dict.get_instance_type_parameter(K, node)
        v = other_dict.get_instance_type_parameter(V, node)
      else:
        k = v = self.vm.convert.create_new_unsolvable(node)
      self.merge_instance_type_parameter(node, K, k)
      self.merge_instance_type_parameter(node, V, v)
      self.could_contain_anything = True

  def compatible_with(self, logical_value):
    if self.could_contain_anything:
      # Always compatible with False.  Compatible with True only if type
      # parameters have been established (meaning that the dict can be
      # non-empty).
      return (not logical_value or
              bool(self.get_instance_type_parameter(K).bindings))
    else:
      return PythonConstant.compatible_with(self, logical_value)


class AnnotationClass(SimpleAbstractValue, HasSlots):
  """Base class of annotations that can be parameterized."""

  def __init__(self, name, vm):
    super(AnnotationClass, self).__init__(name, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)

  @staticmethod
  def _maybe_extract_tuple(t):
    """Returns a tuple of Variables."""
    values = t.data
    if len(values) > 1:
      return (t,)
    v, = values
    if not isinstance(v, Tuple):
      return (t,)
    return v.pyval

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = self._maybe_extract_tuple(slice_var)
    inner, ellipses = self._build_inner(slice_content)
    value = self._build_value(node, tuple(inner), ellipses)
    return node, value.to_variable(node)

  def _build_inner(self, slice_content):
    """Build the list of parameters.

    Args:
      slice_content: The iterable of variables to extract parameters from.

    Returns:
      A tuple of a list of parameters and a set of indices at which an ellipsis
        was replaced with Any.
    """
    inner = []
    ellipses = set()
    for var in slice_content:
      if len(var.bindings) > 1:
        self.vm.errorlog.ambiguous_annotation(self.vm.frames, var.data)
        inner.append(self.vm.convert.unsolvable)
      else:
        val = var.bindings[0].data
        if val is self.vm.convert.ellipsis:
          # Ellipses are allowed only in special cases, so turn them into Any
          # but record the indices so we can check if they're legal.
          ellipses.add(len(inner))
          inner.append(self.vm.convert.unsolvable)
        else:
          inner.append(val)
    return inner, ellipses

  def _build_value(self, node, inner, ellipses):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return "AnnotationClass(%s)" % self.name


class AnnotationContainer(AnnotationClass):
  """Implementation of X[...] for annotations."""

  def __init__(self, name, vm, base_cls):
    super(AnnotationContainer, self).__init__(name, vm)
    self.base_cls = base_cls

  def _get_value_info(self, inner, ellipses, allowed_ellipses=frozenset()):
    """Get information about the container's inner values.

    Args:
      inner: The list of parameters from _build_inner().
      ellipses: The set of ellipsis indices from _build_inner().
      allowed_ellipses: Optionally, a set of indices at which ellipses are
        allowed. If omitted, ellipses are assumed to be never allowed.

    Returns:
      A tuple of the template, the parameters, and the container class.
    """
    template = tuple(t.name for t in self.base_cls.template)
    self.vm.errorlog.invalid_ellipses(
        self.vm.frames, ellipses - allowed_ellipses, self.name)
    if len(inner) - 1 in ellipses:
      # Even if an ellipsis is not allowed at this position, strip it off so
      # that we report only one error for something like 'List[int, ...]'
      inner = inner[:-1]
    return template, inner, ParameterizedClass

  def _build_value(self, node, inner, ellipses):
    template, inner, abstract_class = self._get_value_info(inner, ellipses)
    if len(inner) > len(template):
      if not template:
        self.vm.errorlog.not_indexable(self.vm.frames, self.base_cls.name,
                                       generic_warning=True)
      else:
        error = "Expected %d parameter(s), got %d" % (len(template), len(inner))
        self.vm.errorlog.invalid_annotation(self.vm.frames, self, error)
    else:
      if len(inner) == 1:
        val, = inner
        # It's a common mistake to index tuple, not tuple().
        # We only check the "int" case, since string literals are allowed for
        # late annotations.
        # TODO(kramm): Instead of blacklisting only int, this should use
        # annotations_util.py to look up legal types.
        if isinstance(val, Instance) and val.cls == self.vm.convert.int_type:
          # Don't report this error again.
          inner = (self.vm.convert.unsolvable,)
          self.vm.errorlog.not_indexable(self.vm.frames, self.name)
    params = {name: inner[i] if i < len(inner) else self.vm.convert.unsolvable
              for i, name in enumerate(template)}

    # For user-defined generic types, check if its type parameter matches
    # its corresponding concrete type
    if isinstance(self.base_cls, InterpreterClass) and self.base_cls.template:
      for formal in self.base_cls.template:
        if (isinstance(formal, TypeParameter) and not formal.is_generic() and
            isinstance(params[formal.name], TypeParameter)):
          if formal.name != params[formal.name].name:
            self.vm.errorlog.not_supported_yet(
                self.vm.frames,
                "Renaming TypeVar `%s` with constraints or bound" % formal.name)
        else:
          root_node = self.vm.root_cfg_node
          actual = params[formal.name].instantiate(root_node)
          bad = self.vm.matcher.bad_matches(actual, formal, root_node)
          if bad:
            with self.vm.convert.pytd_convert.produce_detailed_output():
              combined = pytd_utils.JoinTypes(
                  view[actual].data.to_type(root_node, view=view)
                  for view in bad)
              formal = self.vm.annotations_util.sub_one_annotation(
                  root_node, formal, [{}])
              self.vm.errorlog.bad_concrete_type(
                  self.vm.frames, combined, formal.get_instance_type(root_node))
              return self.vm.convert.unsolvable

    try:
      return abstract_class(self.base_cls, params, self.vm)
    except GenericTypeError as e:
      self.vm.errorlog.invalid_annotation(self.vm.frames, e.annot, e.error)
      return self.vm.convert.unsolvable


class AbstractOrConcreteValue(Instance, PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, cls, vm):
    super(AbstractOrConcreteValue, self).__init__(cls, vm)
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

  def _unique_parameters(self):
    return [o.to_variable(self.vm.root_cfg_node) for o in self.options]

  def instantiate(self, node, container=None):
    var = self.vm.program.NewVariable()
    for option in self.options:
      var.PasteVariable(option.instantiate(node, container), node)
    return var

  def get_class(self):
    classes = {o.get_class() for o in self.options}
    if len(classes) > 1:
      return self.vm.convert.unsolvable
    else:
      return classes.pop()

  def call(self, node, func, args, alias_map=None):
    var = self.vm.program.NewVariable(self.options, [], node)
    return self.vm.call_function(node, var, args)

  def get_formal_type_parameter(self, t):
    new_options = [option.get_formal_type_parameter(t)
                   for option in self.options]
    return Union(new_options, self.vm)


class FunctionArgs(collections.namedtuple("_", ["posargs", "namedargs",
                                                "starargs", "starstarargs"])):
  """Represents the parameters of a function call."""

  def __new__(cls, posargs, namedargs=None, starargs=None, starstarargs=None):
    """Create arguments for a function under analysis.

    Args:
      posargs: The positional arguments. A tuple of cfg.Variable.
      namedargs: The keyword arguments. A dictionary, mapping strings to
        cfg.Variable.
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
    if self.starstarargs:
      try:
        d = get_atomic_value(self.starstarargs, Dict)
      except ConversionError:
        return None
      if not d.could_contain_anything:
        return d
    return None

  def simplify(self, node, match_signature=None, vm=None):
    """Try to insert part of *args, **kwargs into posargs / namedargs."""
    # TODO(rechen): When we have type information about *args/**kwargs,
    # we need to check it before doing this simplification.
    posargs = self.posargs
    namedargs = self.namedargs
    starargs = self.starargs
    starstarargs = self.starstarargs
    starargs_as_tuple = self.starargs_as_tuple()
    if starargs_as_tuple is not None:
      if match_signature and vm:
        # As we have the function signature we will attempt to adjust the
        # starargs into the missing posargs.
        missing_posarg_count = len(match_signature.param_names) - len(posargs)
        starargs_list = list(starargs_as_tuple)
        for _ in range(missing_posarg_count):
          if starargs_list:
            posargs += (starargs_list.pop(0),)
          else:
            break
        starargs = vm.convert.tuple_to_value(starargs_list).to_variable(node)
      else:
        posargs += starargs_as_tuple
        starargs = None
    starstarargs_as_dict = self.starstarargs_as_dict()
    if starstarargs_as_dict is not None:
      # TODO(sivachandra): Similar to adjusting varargs in to missing positional
      # args, there might be a benefit in adjusting starstarargs in to named
      # args if function signature has matching param_names.
      if namedargs is None:
        namedargs = starstarargs_as_dict
      else:
        namedargs.update(node, starstarargs_as_dict)
      starstarargs = None
    return FunctionArgs(posargs, namedargs, starargs, starstarargs)

  def get_variables(self):
    variables = list(self.posargs) + list(self.namedargs.values())
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


class Function(SimpleAbstractValue):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    vm: TypegraphVirtualMachine instance.
  """

  CAN_BE_ABSTRACT = True

  def __init__(self, name, vm):
    super(Function, self).__init__(name, vm)
    self.cls = self.vm.convert.function_type
    self.is_attribute_of_class = False
    self.is_abstract = False
    self.members["func_name"] = self.vm.convert.build_string(
        self.vm.root_cfg_node, name)

  def property_get(self, callself, is_class=False):
    if self.name == "__new__" or not callself or is_class:
      return self
    self.is_attribute_of_class = True
    # We'd like to cache this, but we can't. "callself" contains Variables
    # that would be tied into a BoundFunction instance. However, those
    # Variables aren't necessarily visible from other parts of the CFG binding
    # this function. See test_duplicate_getproperty() in tests/test_flow.py.
    return self.bound_class(callself, self)

  def match_args(self, node, args, alias_map=None, match_all_views=False):
    """Check whether the given arguments can match the function signature."""
    assert all(a.bindings for a in args.posargs)
    error = None
    matched = []
    arg_variables = args.get_variables()
    views = get_views(arg_variables, node)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      log.debug("args in view: %r", [(a.bindings and view[a].data)
                                     for a in args.posargs])
      for arg in arg_variables:
        if has_type_parameters(node, view[arg].data):
          self.vm.errorlog.invalid_typevar(
              self.vm.frames, "cannot pass a TypeVar to a function")
          view[arg] = arg.AddBinding(self.vm.convert.unsolvable, [], node)
      try:
        match = self._match_view(node, args, view, alias_map)
      except FailedFunctionCall as e:
        # We could also pass "filter_strict=True" to get_views() above,
        # but it's cheaper to delay verification until the error case.
        if e > error and node.HasCombination(list(view.values())):
          # Add the name of the caller if possible.
          if hasattr(self, "parent"):
            e.name = "%s.%s" % (self.parent.name, e.name)
          error = e
          skip_future = True
        else:
          # This error was ignored, but future ones with the same accessed
          # subset may need to be recorded, so we can't skip them.
          skip_future = False
        if match_all_views:
          raise e
      else:
        matched.append(match)
        skip_future = True
    if not matched and error:
      raise error  # pylint: disable=raising-bad-type
    return matched

  def _match_view(self, node, args, view, alias_map):
    raise NotImplementedError(self.__class__.__name__)

  def __repr__(self):
    return self.full_name + "(...)"

  def _extract_defaults(self, defaults_var):
    """Extracts defaults from a Variable, used by set_function_defaults.

    Args:
      defaults_var: Variable containing potential default values.

    Returns:
      A tuple of default values, if one could be extracted, or None otherwise.
    """
    # Case 1: All given data are tuple constants. Use the longest one.
    if all(isinstance(d, Tuple) for d in defaults_var.data):
      return max((d.pyval for d in defaults_var.data), key=len)
    else:
      # Case 2: Data are entirely Tuple Instances, Unknown or Unsolvable. Make
      # all parameters except self/cls optional.
      # Case 3: Data is anything else. Same as Case 2, but emit a warning.
      if not (all(isinstance(d, (Instance, Unknown, Unsolvable))
                  for d in defaults_var.data) and
              all(d.full_name == "__builtin__.tuple"
                  for d in defaults_var.data if isinstance(d, Instance))):
        self.vm.errorlog.bad_function_defaults(self.vm.frames, self.name)
      # The ambiguous case is handled by the subclass.
      return None

  def set_function_defaults(self, defaults_var):
    raise NotImplementedError(self.__class__.__name__)


class Mutation(collections.namedtuple("_", ["instance", "name", "value"])):

  def __eq__(self, other):
    return (self.instance == other.instance and
            self.name == other.name and
            frozenset(self.value.data) == frozenset(other.value.data))

  def __hash__(self):
    return hash((self.instance, self.name, frozenset(self.value.data)))


class PyTDSignature(utils.VirtualMachineWeakrefMixin):
  """A PyTD function type (signature).

  This represents instances of functions with specific arguments and return
  type.
  """

  def __init__(self, name, pytd_sig, vm):
    super(PyTDSignature, self).__init__(vm)
    self.name = name
    self.pytd_sig = pytd_sig
    self.param_types = [
        self.vm.convert.constant_to_value(
            p.type, subst=datatypes.AliasingDict(), node=self.vm.root_cfg_node)
        for p in self.pytd_sig.params]
    self.signature = function.Signature.from_pytd(vm, name, pytd_sig)

  def _map_args(self, args, view):
    """Map the passed arguments to a name->binding dictionary.

    Args:
      args: The passed arguments.
      view: A variable->binding dictionary.

    Returns:
      A tuple of:
        a list of formal arguments, each a (name, abstract value) pair;
        a name->binding dictionary of the passed arguments.

    Raises:
      InvalidParameters: If the passed arguments don't match this signature.
    """
    formal_args = [(p.name, self.signature.annotations[p.name])
                   for p in self.pytd_sig.params]
    arg_dict = {}

    # positional args
    for name, arg in zip(self.signature.param_names, args.posargs):
      arg_dict[name] = view[arg]
    num_expected_posargs = len(self.signature.param_names)
    if len(args.posargs) > num_expected_posargs and not self.pytd_sig.starargs:
      raise WrongArgCount(self.signature, args, self.vm)
    # Extra positional args are passed via the *args argument.
    varargs_type = self.signature.annotations.get(self.signature.varargs_name)
    if isinstance(varargs_type, ParameterizedClass):
      for (i, vararg) in enumerate(args.posargs[num_expected_posargs:]):
        name = function.argname(num_expected_posargs + i)
        arg_dict[name] = view[vararg]
        formal_args.append((name, varargs_type.get_formal_type_parameter(T)))

    # named args
    for name, arg in args.namedargs.items():
      if name in arg_dict:
        raise DuplicateKeyword(self.signature, args, self.vm, name)
      arg_dict[name] = view[arg]
    extra_kwargs = set(args.namedargs) - {p.name for p in self.pytd_sig.params}
    if extra_kwargs and not self.pytd_sig.starstarargs:
      raise WrongKeywordArgs(self.signature, args, self.vm, extra_kwargs)
    # Extra keyword args are passed via the **kwargs argument.
    kwargs_type = self.signature.annotations.get(self.signature.kwargs_name)
    if isinstance(kwargs_type, ParameterizedClass):
      # We sort the kwargs so that matching always happens in the same order.
      for name in sorted(extra_kwargs):
        formal_args.append((name, kwargs_type.get_formal_type_parameter(V)))

    # packed args
    packed_args = [("starargs", self.signature.varargs_name),
                   ("starstarargs", self.signature.kwargs_name)]
    for arg_type, name in packed_args:
      actual = getattr(args, arg_type)
      pytd_val = getattr(self.pytd_sig, arg_type)
      if actual and pytd_val:
        arg_dict[name] = view[actual]
        # The annotation is Tuple or Dict, but the passed arg only has to be
        # Iterable or Mapping.
        typ = self.vm.convert.widen_type(self.signature.annotations[name])
        formal_args.append((name, typ))

    return formal_args, arg_dict

  def _fill_in_missing_parameters(self, node, args, arg_dict):
    for p in self.pytd_sig.params:
      if p.name not in arg_dict:
        if (not p.optional and args.starargs is None and
            args.starstarargs is None):
          raise MissingParameter(self.signature, args, self.vm, p.name)
        # Assume the missing parameter is filled in by *args or **kwargs.
        # Unfortunately, we can't easily use *args or **kwargs to fill in
        # something more precise, since we need a Value, not a Variable.
        arg_dict[p.name] = self.vm.convert.unsolvable.to_binding(node)

  def substitute_formal_args(self, node, args, view, alias_map):
    """Substitute matching args into this signature. Used by PyTDFunction."""
    formal_args, arg_dict = self._map_args(args, view)
    self._fill_in_missing_parameters(node, args, arg_dict)
    subst, bad_arg = self.vm.matcher.compute_subst(
        node, formal_args, arg_dict, view, alias_map)
    if subst is None:
      if self.signature.has_param(bad_arg.name):
        signature = self.signature
      else:
        signature = self.signature.insert_varargs_and_kwargs(arg_dict)
      raise WrongArgTypes(signature, args, self.vm, bad_param=bad_arg)
    if log.isEnabledFor(logging.DEBUG):
      log.debug("Matched arguments against sig%s", pytd.Print(self.pytd_sig))
    for nr, p in enumerate(self.pytd_sig.params):
      log.info("param %d) %s: %s <=> %s", nr, p.name, p.type, arg_dict[p.name])
    for name, var in sorted(subst.items()):
      log.debug("Using %s=%r %r", name, var, var.data)

    return arg_dict, subst

  def call_with_args(self, node, func, arg_dict,
                     subst, ret_map, alias_map=None):
    """Call this signature. Used by PyTDFunction."""
    return_type = self.pytd_sig.return_type
    t = (return_type, subst)
    sources = [func] + list(arg_dict.values())
    if t not in ret_map:
      for param in pytd_utils.GetTypeParameters(return_type):
        if param.full_name in subst:
          # This value, which was instantiated by the matcher, will end up in
          # the return value. Since the matcher does not call __init__, we need
          # to do that now.
          node = self.vm.call_init(node, subst[param.full_name])
      try:
        ret_map[t] = self.vm.convert.constant_to_var(
            AsReturnValue(return_type), subst, node, source_sets=[sources])
      except self.vm.convert.TypeParameterError:
        # The return type contains a type parameter without a substitution.
        subst = subst.copy()
        visitor = visitors.CollectTypeParameters()
        return_type.Visit(visitor)

        for t in visitor.params:
          if t.full_name not in subst:
            subst[t.full_name] = self.vm.convert.empty.to_variable(node)
        ret_map[t] = self.vm.convert.constant_to_var(
            AsReturnValue(return_type), subst, node, source_sets=[sources])
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
        x = list[int or float]
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
            mutations.append(Mutation(arg, tparam.full_name, type_actual_val))
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

  def set_defaults(self, defaults):
    """Set signature's default arguments. Requires rebuilding PyTD signature.

    Args:
      defaults: An iterable of function argument defaults.

    Returns:
      Self with an updated signature.
    """
    defaults = list(defaults)
    params = []
    for param in reversed(self.pytd_sig.params):
      if defaults:
        defaults.pop()  # Discard the default. Unless we want to update type?
        params.append(pytd.Parameter(
            name=param.name,
            type=param.type,
            kwonly=param.kwonly,
            optional=True,
            mutated_type=param.mutated_type
        ))
      else:
        params.append(pytd.Parameter(
            name=param.name,
            type=param.type,
            kwonly=param.kwonly,
            optional=False,  # Reset any previously-set defaults
            mutated_type=param.mutated_type
        ))
    new_sig = pytd.Signature(
        params=tuple(reversed(params)),
        starargs=self.pytd_sig.starargs,
        starstarargs=self.pytd_sig.starstarargs,
        return_type=self.pytd_sig.return_type,
        exceptions=self.pytd_sig.exceptions,
        template=self.pytd_sig.template
    )
    # Now update self
    self.pytd_sig = new_sig
    self.param_types = [
        self.vm.convert.constant_to_value(
            p.type, subst=datatypes.AliasingDict(), node=self.vm.root_cfg_node)
        for p in self.pytd_sig.params]
    self.signature = function.Signature.from_pytd(self.vm, self.name,
                                                  self.pytd_sig)
    return self

  def __repr__(self):
    return pytd.Print(self.pytd_sig)


class ClassMethod(AtomicAbstractValue):
  """Implements @classmethod methods in pyi."""

  def __init__(self, name, method, callself, vm):
    super(ClassMethod, self).__init__(name, vm)
    self.method = method
    self.method.is_attribute_of_class = True
    # Rename to callcls to make clear that callself is the cls parameter.
    self._callcls = callself
    self.signatures = self.method.signatures

  def call(self, node, func, args, alias_map=None):
    return self.method.call(
        node, func, args.replace(posargs=(self._callcls,) + args.posargs))

  def get_class(self):
    return self.vm.convert.function_type

  def to_bound_function(self):
    return BoundPyTDFunction(self._callcls, self.method)


class StaticMethod(AtomicAbstractValue):
  """Implements @staticmethod methods in pyi."""

  def __init__(self, name, method, _, vm):
    super(StaticMethod, self).__init__(name, vm)
    self.method = method
    self.signatures = self.method.signatures

  def call(self, *args, **kwargs):
    return self.method.call(*args, **kwargs)

  def get_class(self):
    return self.vm.convert.function_type


class Property(AtomicAbstractValue):
  """Implements @property methods in pyi.

  If a getter's return type depends on the type of the class, it needs to be
  resolved as a function, not as a constant.
  """

  def __init__(self, name, method, callself, vm):
    super(Property, self).__init__(name, vm)
    self.method = method
    self._callself = callself
    self.signatures = self.method.signatures

  def call(self, node, func, args, alias_map=None):
    func = func or self.to_binding(node)
    args = args or FunctionArgs(posargs=(self._callself,))
    return self.method.call(node, func, args.replace(posargs=(self._callself,)))

  def get_class(self):
    return self.vm.convert.function_type


class PyTDFunction(Function):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  @staticmethod
  def get_constructor_args(name, vm, module, pyval=None, pyval_name=None):
    """Get args to PyTDFunction.__init__ for the specified function.

    Args:
      name: The function name.
      vm: The VM.
      module: The module that the function is in.
      pyval: Optionally, the pytd.Function object to use. Otherwise, it is
        fetched from the loader.
      pyval_name: Optionally, the name of the pytd.Function object to look up,
        if it is different from the function name.

    Returns:
      A tuple of the constructor args.
    """
    assert not pyval or not pyval_name  # there's never a reason to pass both
    function_name = module + "." + name
    if not pyval:
      pyval_name = module + "." + (pyval_name or name)
      if module not in ("__builtin__", "typing"):
        pyval = vm.loader.import_name(module).Lookup(pyval_name)
      else:
        pyval = vm.lookup_builtin(pyval_name)
    f = vm.convert.constant_to_value(pyval, {}, vm.root_cfg_node)
    return function_name, f.signatures, pyval.kind, vm

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

  def property_get(self, callself, is_class=False):
    if self.kind == pytd.STATICMETHOD:
      if is_class:
        # Binding the function to None rather than not binding it tells
        # output.py to infer the type as a Callable rather than reproducing the
        # signature, including the @staticmethod decorator, which is
        # undesirable for module-level aliases.
        callself = None
      return StaticMethod(self.name, self, callself, self.vm)
    elif self.kind == pytd.CLASSMETHOD:
      if not is_class:
        # callself is the instance, and we want to bind to its class.
        callself = get_atomic_value(
            callself, default=self.vm.convert.unsolvable
        ).get_class().to_variable(self.vm.root_cfg_node)
      return ClassMethod(self.name, self, callself, self.vm)
    elif self.kind == pytd.PROPERTY and not is_class:
      return Property(self.name, self, callself, self.vm)
    else:
      return super(PyTDFunction, self).property_get(callself, is_class)

  def argcount(self, _):
    return min(sig.signature.mandatory_param_count() for sig in self.signatures)

  def _log_args(self, arg_values_list, level=0, logged=None):
    """Log the argument values."""
    if log.isEnabledFor(logging.DEBUG):
      if logged is None:
        logged = set()
      for i, arg_values in enumerate(arg_values_list):
        arg_values = list(arg_values)
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

  def call(self, node, func, args, alias_map=None):
    # TODO(sivachandra): Refactor this method to pass the signature to
    # simplify.
    args = args.simplify(node)
    self._log_args(arg.bindings for arg in args.posargs)
    ret_map = {}
    retvar = self.vm.program.NewVariable()
    all_mutations = set()
    # The following line may raise FailedFunctionCall
    possible_calls = self.match_args(node, args, alias_map)
    for view, signatures in possible_calls:
      if len(signatures) > 1:
        ret = self._call_with_signatures(node, func, args, view, signatures)
      else:
        (sig, arg_dict, subst), = signatures
        ret = sig.call_with_args(
            node, func, arg_dict, subst, ret_map, alias_map)
      node, result, mutations = ret
      retvar.PasteVariable(result, node)
      all_mutations.update(mutations)

    node = _apply_mutations(node, all_mutations.__iter__)
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
            for name in v.instance_type_parameters]

  def _match_view(self, node, args, view, alias_map=None):
    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, if multiple
    # signatures are possible matches, we don't know which got called. Check
    # if this is the case.
    if (len(self.signatures) > 1 and
        any(isinstance(view[arg].data, AMBIGUOUS_OR_EMPTY)
            for arg in args.get_variables())):
      signatures = tuple(self._yield_matching_signatures(
          node, args, view, alias_map))
    else:
      # We take the first signature that matches, and ignore all after it.
      # This is because in the pytds for the standard library, the last
      # signature(s) is/are fallback(s) - e.g. list is defined by
      # def __init__(self: x: list)
      # def __init__(self, x: iterable)
      # def __init__(self, x: generator)
      # def __init__(self, x: object)
      # with the last signature only being used if none of the others match.
      sig = next(self._yield_matching_signatures(node, args, view, alias_map))
      signatures = (sig,)
    return (view, signatures)

  def _call_with_signatures(self, node, func, args, view, signatures):
    """Perform a function call that involves multiple signatures."""
    ret_type = self._combine_multiple_returns(signatures)
    if self.vm.options.protocols and isinstance(ret_type, pytd.AnythingType):
      # We can infer a more specific type.
      log.debug("Creating unknown return")
      result = self.vm.convert.create_new_unknown(
          node, action="pytd_call")
    else:
      log.debug("Unknown args. But return is %s", pytd.Print(ret_type))
      result = self.vm.convert.constant_to_var(
          AsReturnValue(ret_type), {}, node)
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

  def _combine_multiple_returns(self, signatures):
    """Combines multiple return types.

    Args:
      signatures: The candidate signatures.

    Returns:
      The combined return type.
    """
    options = []
    for sig, _, _ in signatures:
      t = sig.pytd_sig.return_type
      visitor = visitors.CollectTypeParameters()
      t.Visit(visitor)
      if visitor.params:
        replacement = {}
        for param_type in visitor.params:
          replacement[param_type] = pytd.AnythingType()
        replace_visitor = visitors.ReplaceTypeParameters(replacement)
        t = t.Visit(replace_visitor)
      options.append(t)
    if len(set(options)) == 1:
      return options[0]
    # Optimizing and then removing unions allows us to preserve as much
    # precision as possible while avoiding false positives.
    ret_type = optimize.Optimize(pytd_utils.JoinTypes(options))
    return ret_type.Visit(visitors.ReplaceUnionsWithAny())

  def _yield_matching_signatures(self, node, args, view, alias_map):
    """Try, in order, all pytd signatures, yielding matches."""
    error = None
    matched = False
    for sig in self.signatures:
      try:
        arg_dict, subst = sig.substitute_formal_args(
            node, args, view, alias_map)
      except FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        matched = True
        yield sig, arg_dict, subst
    if not matched:
      raise error  # pylint: disable=raising-bad-type

  def set_function_defaults(self, defaults_var):
    """Attempts to set default arguments for a function's signatures.

    If defaults_var is not an unambiguous tuple (i.e. one that can be processed
    by get_atomic_python_constant), every argument is made optional and a
    warning is issued. This function is used to emulate __defaults__.

    If this function is part of a class (or has a parent), that parent is
    updated so the change is stored.

    Args:
      defaults_var: a Variable with a single binding to a tuple of default
                    values.
    """
    defaults = self._extract_defaults(defaults_var)
    new_sigs = []
    for sig in self.signatures:
      if defaults:
        new_sigs.append(sig.set_defaults(defaults))
      else:
        d = sig.param_types
        # If we have a parent, we have a "self" or "cls" parameter. Do NOT make
        # that one optional!
        if hasattr(self, "parent"):
          d = d[1:]
        new_sigs.append(sig.set_defaults(d))
    self.signatures = new_sigs
    # Update our parent's AST too, if we have a parent.
    # 'parent' is set by PyTDClass._convert_member
    if hasattr(self, "parent"):
      self.parent._member_map[self.name] = self.generate_ast()  # pylint: disable=protected-access

  def generate_ast(self):
    return pytd.Function(
        name=self.name,
        signatures=tuple(s.pytd_sig for s in self.signatures),
        kind=self.kind,
        flags=pytd.Function.abstract_flag(self.is_abstract))


@six.add_metaclass(MixinMeta)
class Class(object):
  """Mix-in to mark all class-like values."""

  overloads = ("get_special_attribute", "get_own_new", "call", "compute_mro")

  def __new__(cls, *unused_args, **unused_kwds):
    """Prevent direct instantiation."""
    assert cls is not Class, "Cannot instantiate Class"
    return object.__new__(cls)

  def init_mixin(self, metaclass):
    """Mix-in equivalent of __init__."""
    if metaclass is None:
      self.cls = self._get_inherited_metaclass()
    else:
      # TODO(rechen): Check that the metaclass is a (non-strict) subclass of the
      # metaclasses of the base classes.
      self.cls = metaclass
    self._instance_cache = {}
    self._init_abstract_methods()
    self._all_formal_type_parameters = datatypes.AliasingMonitorDict()
    self._all_formal_type_parameters_loaded = False

  def bases(self):
    return []

  @property
  def all_formal_type_parameters(self):
    self._load_all_formal_type_parameters()
    return self._all_formal_type_parameters

  def _load_all_formal_type_parameters(self):
    """Load _all_formal_type_parameters."""
    if self._all_formal_type_parameters_loaded:
      return

    bases = [_get_class(base, default=self.vm.convert.unsolvable)
             for base in self.bases()]
    for base in bases:
      parse_formal_type_parameters(
          base, self.full_name, self._all_formal_type_parameters)

    self._all_formal_type_parameters_loaded = True

  def get_own_abstract_methods(self):
    """Get the abstract methods defined by this class."""
    raise NotImplementedError(self.__class__.__name__)

  def _init_abstract_methods(self):
    """Compute this class's abstract methods."""
    # For the algorithm to run, abstract_methods needs to be populated with the
    # abstract methods defined by this class. We'll overwrite the attribute
    # with the full set of abstract methods later.
    self.abstract_methods = self.get_own_abstract_methods()
    abstract_methods = set()
    for cls in reversed(self.mro):
      if not isinstance(cls, Class):
        continue
      # Remove methods implemented by this class.
      abstract_methods = {m for m in abstract_methods
                          if m not in cls or m in cls.abstract_methods}
      # Add abstract methods defined by this class.
      abstract_methods |= {m for m in cls.abstract_methods if m in cls}
    self.abstract_methods = abstract_methods

  @property
  def has_abstract_metaclass(self):
    return self.cls and "abc.ABCMeta" in (
        parent.full_name for parent in self.cls.mro)

  @property
  def is_abstract(self):
    return self.has_abstract_metaclass and bool(self.abstract_methods)

  def _get_inherited_metaclass(self):
    for base in self.mro[1:]:
      if isinstance(base, Class) and base.cls is not None:
        return base.cls
    return None

  def get_own_new(self, node, value):
    """Get this value's __new__ method, if it isn't object.__new__.

    Args:
      node: The current node.
      value: A cfg.Binding containing this value.

    Returns:
      A tuple of (1) a node and (2) either a cfg.Variable of the special
      __new__ method, or None.
    """
    node, new = self.vm.attribute_handler.get_attribute(
        node, value.data, "__new__")
    if new is None:
      return node, None
    if len(new.bindings) == 1:
      f = new.bindings[0].data
      if (isinstance(f, AMBIGUOUS_OR_EMPTY) or
          self.vm.convert.object_type.is_object_new(f)):
        # Instead of calling object.__new__, our abstract classes directly
        # create instances of themselves.
        return node, None
    return node, new

  def _call_new_and_init(self, node, value, args):
    """Call __new__ if it has been overridden on the given value."""
    node, new = self.get_own_new(node, value)
    if new is None:
      return node, None
    cls = value.AssignToNewVariable(node)
    new_args = args.replace(posargs=(cls,) + args.posargs)
    node, variable = self.vm.call_function(node, new, new_args)
    for val in variable.bindings:
      # TODO(rechen): If val.data is a class, _call_init mistakenly calls
      # val.data's __init__ method rather than that of val.data.cls. See
      # testClasses.testTypeInit for a case in which skipping this __init__
      # call is problematic.
      if not isinstance(val.data, Class) and self == val.data.cls:
        node = self._call_init(node, val, args)
    return node, variable

  def _call_init(self, node, value, args):
    node, init = self.vm.attribute_handler.get_attribute(
        node, value.data, "__init__", value)
    if init:
      log.debug("calling %s.__init__(...)", self.name)
      node, ret = self.vm.call_function(node, init, args)
      log.debug("%s.__init__(...) returned %r", self.name, ret)
    return node

  def _new_instance(self):
    # We allow only one "instance" per code location, regardless of call stack.
    key = self.vm.frame.current_opcode
    assert key
    if key not in self._instance_cache:
      self._instance_cache[key] = Instance(self, self.vm)
    return self._instance_cache[key]

  def call(self, node, value, args):
    if self.is_abstract:
      self.vm.errorlog.not_instantiable(self.vm.frames, self)
    node, variable = self._call_new_and_init(node, value, args)
    if variable is None:
      value = self._new_instance()
      variable = self.vm.program.NewVariable()
      val = variable.AddBinding(value, [], node)
      node = self._call_init(node, val, args)
    return node, variable

  def get_special_attribute(self, node, name, valself):
    """Fetch a special attribute."""
    if name == "__getitem__" and valself is None:
      # See vm._call_binop_on_bindings: valself == None is a special value that
      # indicates an annotation.
      if self.cls:
        # This class has a custom metaclass; check if it defines __getitem__.
        _, attr = self.vm.attribute_handler.get_attribute(
            node, self, name, self.to_binding(node))
        if attr:
          return attr
      # Treat this class as a parameterized container in an annotation. We do
      # not need to worry about the class not being a container: in that case,
      # AnnotationContainer's param length check reports an appropriate error.
      container = AnnotationContainer(self.name, self.vm, self)
      return container.get_special_attribute(node, name, valself)
    return Class.super(self.get_special_attribute)(node, name, valself)

  def has_dynamic_attributes(self):
    return any(a in self for a in DYNAMIC_ATTRIBUTE_MARKERS)

  def compute_is_dynamic(self):
    # This needs to be called after self.mro is set.
    return any(c.has_dynamic_attributes()
               for c in self.mro
               if isinstance(c, Class))

  def compute_mro(self):
    """Compute the class precedence list (mro) according to C3."""
    bases = _get_mro_bases(self.bases())
    bases = [[self]] + [list(base.mro) for base in bases] + [list(bases)]
    # If base classes are `ParameterizedClass`, we will use their `base_cls` to
    # calculate the MRO. Bacause of type parameter renaming, we can not compare
    # the `ParameterizedClass`s which contain the same `base_cls`.  See example:
    #   class A(Iterator[T]): ...
    #   class B(Iterator[U], A[V]): ...
    # The inheritance: [B], [Iterator, ...], [A, Iterator, ...], [Iterator, A]
    # So this has MRO order issue, but because the template names of
    # `ParameterizedClass` of `Iterator` are different, they will be treated as
    # different base classes and it will infer the MRO order is correct.
    # TODO(ahxun): fix this by solving the template rename problem
    base2cls = {}
    newbases = []
    for row in bases:
      baselist = []
      for base in row:
        if isinstance(base, ParameterizedClass):
          base2cls[base.base_cls] = base
          baselist.append(base.base_cls)
        else:
          base2cls[base] = base
          baselist.append(base)
      newbases.append(baselist)

    # calc MRO and replace them with original base classes
    return tuple(base2cls[base] for base in mro.MROMerge(newbases))


class ParameterizedClass(AtomicAbstractValue, Class):
  """A class that contains additional parameters. E.g. a container.

  Attributes:
    cls: A PyTDClass representing the base type.
    formal_type_parameters: An iterable of AtomicAbstractValue, one for each
        type parameter.
  """

  is_lazy = False

  def get_self_annot(self):
    """This is used to annotate the `self` in a class."""
    if not self.self_annot:
      formal_type_parameters = {}
      for item in self.base_cls.template:
        formal_type_parameters[item.name] = item
      self.self_annot = ParameterizedClass(
          self.base_cls, formal_type_parameters, self.vm)
    return self.self_annot

  def __init__(self, base_cls, formal_type_parameters, vm):
    # A ParameterizedClass is created by converting a pytd.GenericType, whose
    # base type is restricted to NamedType and ClassType.
    assert isinstance(base_cls, Class)
    self.base_cls = base_cls
    super(ParameterizedClass, self).__init__(base_cls.name, vm)
    self.module = base_cls.module
    # Lazily loaded to handle recursive types.
    # See the formal_type_parameters() property.
    self._formal_type_parameters = formal_type_parameters
    self._formal_type_parameters_loaded = False
    self._hash = None  # memoized due to expensive computation
    self.official_name = self.base_cls.official_name
    # Load immediately due to template in base_cls could change
    self._template = self.base_cls.template
    self.slots = self.base_cls.slots
    self.self_annot = None
    Class.init_mixin(self, base_cls.cls)
    self.type_param_check()

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (
        self.base_cls,
        self.formal_type_parameters)

  def type_param_check(self):
    """Throw exception for invalid type parameters."""
    # It will cause infinite recursion if `formal_type_parameters` is
    # `LazyTypeParameters`
    if not isinstance(self._formal_type_parameters, LazyFormalTypeParameters):
      tparams = datatypes.AliasingMonitorDict()
      parse_formal_type_parameters(self, None, tparams)

  def get_formal_type_parameters(self):
    return {self.full_type_name(k): v
            for k, v in self.formal_type_parameters.items()}

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.base_cls == other.base_cls and (
          self.formal_type_parameters == other.formal_type_parameters)
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    if self._hash is None:
      if isinstance(self._formal_type_parameters, LazyFormalTypeParameters):
        items = self._raw_formal_type_parameters()
      else:
        items = self.formal_type_parameters.items()
      self._hash = hash((self.base_cls, tuple(items)))
    return self._hash

  def __contains__(self, name):
    return name in self.base_cls

  def _raw_formal_type_parameters(self):
    assert isinstance(self._formal_type_parameters, LazyFormalTypeParameters)
    template, parameters, _ = self._formal_type_parameters
    for i, name in enumerate(template):
      # TODO(rechen): A missing parameter should be an error.
      yield name, parameters[i] if i < len(parameters) else None

  def get_own_abstract_methods(self):
    return self.base_cls.get_own_abstract_methods()

  @property
  def members(self):
    return self.base_cls.members

  @property
  def formal(self):
    # We can't compute self.formal in __init__ because doing so would force
    # evaluation of our type parameters during initialization, possibly
    # leading to an infinite loop.
    return any(t.formal for t in self.formal_type_parameters.values())

  @property
  def formal_type_parameters(self):
    self._load_formal_type_parameters()
    return self._formal_type_parameters

  def _load_formal_type_parameters(self):
    if self._formal_type_parameters_loaded:
      return
    if isinstance(self._formal_type_parameters, LazyFormalTypeParameters):
      formal_type_parameters = {}
      for name, param in self._raw_formal_type_parameters():
        if param is None:
          formal_type_parameters[name] = self.vm.convert.unsolvable
        else:
          formal_type_parameters[name] = self.vm.convert.constant_to_value(
              param, self._formal_type_parameters.subst, self.vm.root_cfg_node)
      self._formal_type_parameters = formal_type_parameters
    self._formal_type_parameters = (
        self.vm.annotations_util.convert_class_annotations(
            self._formal_type_parameters))
    self._formal_type_parameters_loaded = True

  def compute_mro(self):
    return (self,) + self.base_cls.mro[1:]

  def instantiate(self, node, container=None):
    if self.full_name == "__builtin__.type":
      instance = self.formal_type_parameters[T]
      if instance.formal:
        # This can happen for, say, Type[T], where T is a type parameter. See
        # test_typevar's testTypeParameterType for an example.
        instance = self.vm.convert.unsolvable
      return instance.to_variable(node)
    elif self.vm.frame and self.vm.frame.current_opcode:
      return self._new_instance().to_variable(node)
    else:
      return super(ParameterizedClass, self).instantiate(node, container)

  def get_class(self):
    return self.base_cls.get_class()

  def set_class(self, node, var):
    self.base_cls.set_class(node, var)

  def get_method(self, method_name):
    """Retrieve the method with the given name."""
    method = None
    for cls in self.base_cls.mro:
      if isinstance(cls, ParameterizedClass):
        cls = cls.base_cls
      if isinstance(cls, PyTDClass):
        try:
          method = cls.pytd_cls.Lookup(method_name)
        except KeyError:
          continue  # Method not found, proceed to next class in MRO.
        break  # Method found!
    assert method
    return self.vm.convert.constant_to_value(method)

  def _is_callable(self):
    return (not self.is_abstract
            and isinstance(self.base_cls, (InterpreterClass, PyTDClass))
            and self.module not in  ("__builtin__", "typing")
            and all(not isinstance(val, TypeParameter)
                    for val in self.formal_type_parameters.values()))

  def call(self, node, func, args, alias_map=None):
    if not self._is_callable():
      raise NotCallable(self)
    else:
      return Class.call(self, node, func, args)

  def get_formal_type_parameter(self, t):
    return self.formal_type_parameters.get(t, self.vm.convert.unsolvable)


class TupleClass(ParameterizedClass, HasSlots):
  """The class of a heterogeneous tuple.

  The formal_type_parameters attribute stores the types of the individual tuple
  elements under their indices and the overall element type under "T". So for
    Tuple[str, int]
  formal_type_parameters is
    {0: str, 1: int, T: str or int}.
  Note that we can't store the individual types as a PythonConstant as we do
  for Tuple, since we can't evaluate type parameters during initialization.
  """

  def __init__(self, base_cls, formal_type_parameters, vm):
    super(TupleClass, self).__init__(base_cls, formal_type_parameters, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    if isinstance(self._formal_type_parameters, LazyFormalTypeParameters):
      num_parameters = len(self._formal_type_parameters.template)
    else:
      num_parameters = len(self._formal_type_parameters)
    # We subtract one to account for "T".
    self.tuple_length = num_parameters - 1
    self._instance = None
    self.slots = ()  # tuples don't have any writable attributes

  def __repr__(self):
    return "TupleClass(%s)" % self.formal_type_parameters

  def compute_mro(self):
    # ParameterizedClass removes the base PyTDClass(tuple) from the mro; add it
    # back here so that isinstance(tuple) checks work.
    return (self,) + self.base_cls.mro

  def get_formal_type_parameters(self):
    return {self.full_type_name(T): self.formal_type_parameters[T]}

  def instantiate(self, node, container=None):
    if self._instance:
      return self._instance.to_variable(node)
    content = []
    for i in range(self.tuple_length):
      p = self.formal_type_parameters[i]
      if container is self.vm.annotations_util.DUMMY_CONTAINER or (
          container and isinstance(p, TypeParameter) and
          p.full_name in container.all_template_names):
        content.append(p.instantiate(self.vm.root_cfg_node, container))
      else:
        content.append(p.instantiate(self.vm.root_cfg_node))
    return Tuple(tuple(content), self.vm).to_variable(node)

  def _instantiate_index(self, node, index):
    if self._instance:
      return self._instance.pyval[index]
    else:
      index %= self.tuple_length  # fixes negative indices
      return self.formal_type_parameters[index].instantiate(node)

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
      if -self.tuple_length <= index < self.tuple_length:
        # Index out of bounds is not a pytype error because of the high
        # likelihood of false positives, e.g.,
        #   tup = []
        #   idx = 0
        #   if idx < len(tup):
        #     tup[idx]
        return node, self._instantiate_index(node, index)
    return self.call_pytd(
        node, "__getitem__", self.instantiate(node), index_var)

  def get_special_attribute(self, node, name, valself):
    if valself and not equivalent_to(valself, self) and name in self._slots:
      return HasSlots.get_special_attribute(self, node, name, valself)
    return super(TupleClass, self).get_special_attribute(node, name, valself)


class Callable(ParameterizedClass, HasSlots):
  """A Callable with a list of argument types.

  The formal_type_parameters attribute stores the types of the individual
  arguments under their indices, the overall argument type under "ARGS", and the
  return type under "RET". So for
    Callable[[int, bool], str]
  formal_type_parameters is
    {0: int, 1: bool, ARGS: int or bool, RET: str}
  When there are no args (Callable[[], ...]), ARGS contains abstract.Empty.
  """

  def __init__(self, base_cls, formal_type_parameters, vm):
    super(Callable, self).__init__(base_cls, formal_type_parameters, vm)
    HasSlots.init_mixin(self)
    self.set_slot("__call__", self.call_slot)
    # We subtract two to account for "ARGS" and "RET".
    self.num_args = len(self.formal_type_parameters) - 2

  def __repr__(self):
    return "Callable(%s)" % self.formal_type_parameters

  def get_formal_type_parameters(self):
    return {self.full_type_name(ARGS): self.formal_type_parameters[ARGS],
            self.full_type_name(RET): self.formal_type_parameters[RET]}

  def call_slot(self, node, *args, **kwargs):
    """Implementation of Callable.__call__."""
    if kwargs:
      raise WrongKeywordArgs(function.Signature.from_callable(self),
                             FunctionArgs(posargs=args, namedargs=kwargs),
                             self.vm, kwargs.keys())
    if len(args) != self.num_args:
      raise WrongArgCount(function.Signature.from_callable(self),
                          FunctionArgs(posargs=args), self.vm)
    formal_args = [(function.argname(i), self.formal_type_parameters[i])
                   for i in range(self.num_args)]
    substs = [datatypes.AliasingDict()]
    bad_param = None
    for view in get_views(args, node):
      arg_dict = {function.argname(i): view[args[i]]
                  for i in range(self.num_args)}
      subst, bad_param = self.vm.matcher.compute_subst(
          node, formal_args, arg_dict, view, None)
      if subst is not None:
        substs = [subst]
        break
    else:
      if bad_param:
        raise WrongArgTypes(
            function.Signature.from_callable(self), FunctionArgs(posargs=args),
            self.vm, bad_param=bad_param)
    ret = self.vm.annotations_util.sub_one_annotation(
        node, self.formal_type_parameters[RET], substs)
    node, retvar = self.vm.init_class(node, ret)
    return node, retvar

  def get_special_attribute(self, node, name, valself):
    if valself and not equivalent_to(valself, self) and name in self._slots:
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
    self.pytd_cls = pytd_cls
    super(PyTDClass, self).__init__(name, vm)
    mm = {}
    for val in pytd_cls.constants + pytd_cls.methods:
      mm[val.name] = val
    self._member_map = mm
    if pytd_cls.metaclass is None:
      metaclass = None
    else:
      metaclass = self.vm.convert.constant_to_value(
          pytd_cls.metaclass, subst=datatypes.AliasingDict(),
          node=self.vm.root_cfg_node)
    self.official_name = self.name
    # The `template` is usually a constant but in the case of
    # typing.Generic (only) it'll change every time when a new
    # `Generic` class is instantiated.
    self._template = None
    self.slots = pytd_cls.slots
    self.is_dynamic = self.compute_is_dynamic()
    Class.init_mixin(self, metaclass)

  def _compute_template(self):
    """Compute the template.

    This can not be computed in `PyTDClass.__init_` due to infinite recursion
    problem. E.g.:
      AT = TypeVar("AT", bound=A)
      class A(Sequence[AT]): ...
    When we try to construct `PyTDClass(A)`, it will instantiate the type
    parameter `AT` which bound is `A`, so it will try to generate a new
    `PyTDClass(A)`. This will cause the infinite recursion problem.

    Returns:
      type parameter list
    """
    return [self.vm.convert.constant_to_value(itm.type_param)
            for itm in self.pytd_cls.template]

  def get_own_abstract_methods(self):
    return {name for name, member in self._member_map.items()
            if isinstance(member, pytd.Function) and member.is_abstract}

  def bases(self):
    convert = self.vm.convert
    return [convert.constant_to_var(parent, subst=datatypes.AliasingDict(),
                                    node=self.vm.root_cfg_node)
            for parent in self.pytd_cls.parents]

  def load_lazy_attribute(self, name):
    try:
      super(PyTDClass, self).load_lazy_attribute(name)
    except self.vm.convert.TypeParameterError as e:
      self.vm.errorlog.unbound_type_param(
          self.vm.frames, self, name, e.type_param_name)
      self.members[name] = self.vm.convert.unsolvable.to_variable(
          self.vm.root_cfg_node)

  def _convert_member(self, _, pyval, subst=None, node=None):
    """Convert a member as a variable. For lazy lookup."""
    subst = subst or datatypes.AliasingDict()
    node = node or self.vm.root_cfg_node
    if isinstance(pyval, pytd.Constant):
      return self.vm.convert.constant_to_var(
          AsInstance(pyval.type), subst, node)
    elif isinstance(pyval, pytd.Function):
      c = self.vm.convert.constant_to_value(pyval, subst=subst, node=node)
      c.parent = self
      return c.to_variable(self.vm.root_cfg_node)
    else:
      raise AssertionError("Invalid class member %s" % pytd.Print(pyval))

  def call(self, node, func, args, alias_map=None):
    if self.is_abstract:
      self.vm.errorlog.not_instantiable(self.vm.frames, self)
    node, results = self._call_new_and_init(node, func, args)
    if results is None:
      value = Instance(
          self.vm.convert.constant_to_value(self.pytd_cls), self.vm)
      for type_param in self.template:
        name = type_param.full_name
        if name not in value.instance_type_parameters:
          value.instance_type_parameters[name] = self.vm.program.NewVariable()
      results = self.vm.program.NewVariable()
      retval = results.AddBinding(value, [func], node)
      node = self._call_init(node, retval, args)
    return node, results

  def instantiate(self, node, container=None):
    return self.vm.convert.constant_to_var(AsInstance(self.pytd_cls), {}, node)

  def __repr__(self):
    return "PyTDClass(%s)" % self.name

  def __contains__(self, name):
    return name in self._member_map

  def convert_as_instance_attribute(self, node, name, instance):
    """Convert `name` as an instance attribute."""
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
        subst = datatypes.AliasingDict()
        for itm in self.pytd_cls.template:
          subst[itm.full_name] = self.vm.convert.constant_to_value(
              itm.type_param, {}, node).instantiate(node, container=instance)
        return self._convert_member(name, c, subst, node)

  def generate_ast(self):
    """Generate this class's AST, including updated members."""
    return pytd.Class(
        name=self.name,
        metaclass=self.pytd_cls.metaclass,
        parents=self.pytd_cls.parents,
        methods=tuple(self._member_map[m.name] for m in self.pytd_cls.methods),
        constants=self.pytd_cls.constants,
        classes=self.pytd_cls.classes,
        slots=self.pytd_cls.slots,
        template=self.pytd_cls.template)


class InterpreterClass(SimpleAbstractValue, Class):
  """An abstract wrapper for user-defined class objects.

  These are the abstract value for class objects that are implemented in the
  program.
  """

  is_lazy = False

  def __init__(self, name, bases, members, cls, vm):
    assert isinstance(name, str)
    assert isinstance(bases, list)
    assert isinstance(members, dict)
    self._bases = bases
    super(InterpreterClass, self).__init__(name, vm)
    self.members = datatypes.MonitorDict(members)
    Class.init_mixin(self, cls)
    self.instances = set()  # filled through register_instance
    self.slots = self._convert_slots(members.get("__slots__"))
    self.is_dynamic = self.compute_is_dynamic()
    log.info("Created class: %r", self)
    self.type_param_check()

  def type_param_check(self):
    """Throw exception for invalid type parameters."""
    if self.template:
      # For function type parameters check
      for mbr in self.members.values():
        mbr = get_atomic_value(mbr, default=self.vm.convert.unsolvable)
        if isinstance(mbr, InterpreterFunction):
          mbr.signature.excluded_types.update(
              [t.name for t in self.template])
          mbr.signature.add_scope(self.full_name)
      # nested class can not use the same type parameter
      # in current generic class
      inner_cls_types = self.collect_inner_cls_types()
      for cls, item in inner_cls_types:
        nitem = item.with_module(self.full_name)
        if nitem in self.template:
          raise GenericTypeError(
              self, ("Generic class [%s] and its nested generic class [%s] "
                     "cannot use same type variable %s.")
              % (self.full_name, cls.full_name, item.name))

    self._load_all_formal_type_parameters()  # Throw exception if there is error
    for t in self.template:
      if t.full_name in self.all_formal_type_parameters:
        raise GenericTypeError(
            self, "Conflicting value for TypeVar %s" % t.full_name)

  def collect_inner_cls_types(self, max_depth=5):
    """Collect all the type parameters from nested classes."""
    templates = set()
    if max_depth > 0:
      for mbr in self.members.values():
        mbr = get_atomic_value(mbr, default=self.vm.convert.unsolvable)
        if isinstance(mbr, InterpreterClass) and mbr.template:
          templates.update([(mbr, item.with_module(None))
                            for item in mbr.template])
          templates.update(mbr.collect_inner_cls_types(max_depth - 1))
    return templates

  def get_inner_classes(self):
    """Return the list of top-level nested classes."""
    values = [
        get_atomic_value(mbr, default=self.vm.convert.unsolvable)
        for mbr in self.members.values()]
    return [x for x in values if isinstance(x, InterpreterClass)]

  def _compute_template(self):
    """Compute the precedence list of template parameters according to C3.

    1. For the base class list, if it contains `typing.Generic`, then all the
    type parameters should be provided. That means we don't need to parse extra
    base class and then we can get all the type parameters.
    2. If there is no `typing.Generic`, parse the precedence list according to
    C3 based on all the base classes.
    3. If `typing.Generic` exists, it must contain at least one type parameters.
    And there is at most one `typing.Generic` in the base classes. Report error
    if the check fails.

    Returns:
      parsed type parameters

    Raises:
      GenericTypeError: if the type annotation for generic type is incorrect
    """
    bases = [_get_class(base, default=self.vm.convert.unsolvable)
             for base in self.bases()]
    template = []

    # Compute the number of `typing.Generic` and collect the type parameters
    for base in bases:
      if base.full_name == "typing.Generic":
        if isinstance(base, PyTDClass):
          raise GenericTypeError(self, "Cannot inherit from plain Generic")
        if template:
          raise GenericTypeError(
              self, "Cannot inherit from Generic[...] multiple times")
        for item in base.template:
          val = base.formal_type_parameters.get(item.name)
          template.append(val.with_module(self.full_name))

    if template:
      # All type parameters in the base classes should appear in
      # `typing.Generic`
      for base in bases:
        if base.full_name != "typing.Generic":
          if isinstance(base, ParameterizedClass):
            for item in base.template:
              val = base.formal_type_parameters.get(item.name)
              if isinstance(val, TypeParameter):
                t = val.with_module(self.full_name)
                if t not in template:
                  raise GenericTypeError(
                      self, "Generic should contain all the type variables")
    else:
      # Compute template parameters according to C3
      seqs = []
      for base in bases:
        if isinstance(base, ParameterizedClass):
          seq = []
          for item in base.template:
            val = base.formal_type_parameters.get(item.name)
            if isinstance(val, TypeParameter):
              seq.append(val.with_module(self.full_name))
          seqs.append(seq)
      try:
        template.extend(mro.MergeSequences(seqs))
      except ValueError:
        raise GenericTypeError(
            self, "Illegal type parameter order in class %s" % self.name)

    return template

  def get_own_abstract_methods(self):
    return {name for name, var in self.members.items()
            if any(v.CAN_BE_ABSTRACT and v.is_abstract for v in var.data)}

  def _mangle(self, name):
    """Do name-mangling on an attribute name.

    See https://goo.gl/X85fHt.  Python automatically converts a name like
    "__foo" to "_ClassName__foo" in the bytecode. (But "forgets" to do so in
    other places, e.g. in the strings of __slots__.)

    Arguments:
      name: The name of an attribute of the current class. E.g. "__foo".

    Returns:
      The mangled name. E.g. "_MyClass__foo".
    """
    if name.startswith("__") and not name.endswith("__"):
      return "_" + self.name + name
    else:
      return name

  def _convert_slots(self, slots_var):
    """Convert __slots__ from a Variable to a tuple."""
    if slots_var is None:
      return None
    if len(slots_var.bindings) != 1:
      # Ambiguous slots
      return None  # Treat "unknown __slots__" and "no __slots__" the same.
    val = slots_var.data[0]
    if isinstance(val, PythonConstant):
      if isinstance(val.pyval, (list, tuple)):
        entries = val.pyval
      else:
        return None  # Happens e.g. __slots__ = {"foo", "bar"}. Not an error.
    else:
      return None  # Happens e.g. for __slots__ = dir(Foo)
    try:
      strings = [get_atomic_python_constant(v) for v in entries]
    except ConversionError:
      return None  # Happens e.g. for __slots__ = ["x" if b else "y"]
    for s in strings:
      # The identity check filters out compat.py subclasses.
      if s.__class__ is not str:
        if isinstance(s, six.text_type):
          name = s.encode("utf8", "ignore")
        else:
          name = str(s)
        self.vm.errorlog.bad_slots(self.vm.frames,
                                   "Invalid __slot__ entry: %r" % name)
        return None
    return tuple(self._mangle(compat.native_str(s)) for s in strings)

  def register_instance(self, instance):
    self.instances.add(instance)

  def bases(self):
    return self._bases

  def metaclass(self, node):
    if self.cls and self.cls is not self._get_inherited_metaclass():
      return self.vm.convert.merge_classes(node, [self])
    else:
      return None

  def instantiate(self, node, container=None):
    if self.vm.frame and self.vm.frame.current_opcode:
      return self._new_instance().to_variable(node)
    else:
      # When the analyze_x methods in CallTracer instantiate classes in
      # preparation for analysis, often there is no frame on the stack yet, or
      # the frame is a SimpleFrame with no opcode.
      return super(InterpreterClass, self).instantiate(node, container)

  def __repr__(self):
    return "InterpreterClass(%s)" % self.name

  def __contains__(self, name):
    return name in self.members

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
    self.bound_class = lambda callself, underlying: self

  def argcount(self, _):
    return self.func.func_code.co_argcount

  def call(self, node, _, args, alias_map=None):
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
      if "keyword" in utils.message(e):
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


class SignedFunction(Function):
  """An abstract base class for functions represented by function.Signature.

  Subclasses should define call(self, node, f, args) and set self.bound_class.
  """

  def __init__(self, signature, vm):
    super(SignedFunction, self).__init__(signature.name, vm)
    self.signature = signature

  @contextlib.contextmanager
  def set_self_annot(self, annot_class):
    """Set the annotation for `self` in a class."""
    self_name = self.signature.param_names[0]
    old_self = self.signature.annotations.get(self_name)
    self.signature.annotations[self_name] = annot_class
    try:
      yield
    finally:
      if old_self:
        self.signature.annotations[self_name] = old_self
      else:
        del self.signature.annotations[self_name]

  def argcount(self, _):
    return len(self.signature.param_names)

  def get_nondefault_params(self):
    return ((n, n in self.signature.kwonly_params)
            for n in self.signature.param_names
            if n not in self.signature.defaults)

  def _map_args(self, node, args):
    """Map call args to function args.

    This emulates how Python would map arguments of function calls. It takes
    care of keyword parameters, default parameters, and *args and **kwargs.

    Args:
      node: The current CFG node.
      args: The arguments.

    Returns:
      A dictionary, mapping strings (parameter names) to cfg.Variable.

    Raises:
      FailedFunctionCall: If the caller supplied incorrect arguments.
    """
    # Originate a new variable for each argument and call.
    posargs = [u.AssignToNewVariable(node)
               for u in args.posargs]
    kws = {k: u.AssignToNewVariable(node)
           for k, u in args.namedargs.items()}
    sig = self.signature
    callargs = {name: self.vm.program.NewVariable(default.data, [], node)
                for name, default in sig.defaults.items()}
    positional = dict(zip(sig.param_names, posargs))
    for key in positional:
      if key in kws:
        raise DuplicateKeyword(sig, args, self.vm, key)
    extra_kws = set(kws).difference(sig.param_names + sig.kwonly_params)
    if extra_kws and not sig.kwargs_name:
      raise WrongKeywordArgs(sig, args, self.vm, extra_kws)
    callargs.update(positional)
    callargs.update(kws)
    for key, kwonly in self.get_nondefault_params():
      if key not in callargs:
        if args.starstarargs or (args.starargs and not kwonly):
          # We assume that because we have *args or **kwargs, we can use these
          # to fill in any parameters we might be missing.
          callargs[key] = self.vm.convert.create_new_unsolvable(node)
        else:
          raise MissingParameter(sig, args, self.vm, key)
    for key in sig.kwonly_params:
      if key not in callargs:
        raise MissingParameter(sig, args, self.vm, key)
    if sig.varargs_name:
      varargs_name = sig.varargs_name
      extraneous = posargs[self.argcount(node):]
      if args.starargs:
        if extraneous:
          log.warning("Not adding extra params to *%s", varargs_name)
        callargs[varargs_name] = args.starargs.AssignToNewVariable(node)
      else:
        callargs[varargs_name] = self.vm.convert.build_tuple(node, extraneous)
    elif len(posargs) > self.argcount(node):
      raise WrongArgCount(sig, args, self.vm)
    if sig.kwargs_name:
      kwargs_name = sig.kwargs_name
      # Build a **kwargs dictionary out of the extraneous parameters
      if args.starstarargs:
        # TODO(kramm): modify type parameters to account for namedargs
        callargs[kwargs_name] = args.starstarargs.AssignToNewVariable(node)
      else:
        k = Dict(self.vm)
        k.update(node, args.namedargs, omit=sig.param_names)
        callargs[kwargs_name] = k.to_variable(node)
    return callargs

  def _match_view(self, node, args, view, alias_map=None):
    arg_dict = {}
    formal_args = []
    for name, arg, formal in self.signature.iter_args(args):
      arg_dict[name] = view[arg]
      if formal is not None:
        if name in (self.signature.varargs_name, self.signature.kwargs_name):
          # The annotation is Tuple or Dict, but the passed arg only has to be
          # Iterable or Mapping.
          formal = self.vm.convert.widen_type(formal)
        formal_args.append((name, formal))
    subst, bad_arg = self.vm.matcher.compute_subst(
        node, formal_args, arg_dict, view, alias_map)
    if subst is None:
      raise WrongArgTypes(self.signature, args, self.vm, bad_param=bad_arg)
    return subst

  def get_first_opcode(self):
    return None

  def set_function_defaults(self, defaults_var):
    """Attempts to set default arguments of a function.

    If defaults_var is not an unambiguous tuple (i.e. one that can be processed
    by get_atomic_python_constant), every argument is made optional and a
    warning is issued. This function is used to emulate __defaults__.

    Args:
      defaults_var: a Variable with a single binding to a tuple of default
                    values.
    """
    defaults = self._extract_defaults(defaults_var)
    if defaults is None:
      defaults = [self.vm.convert.unsolvable]*len(self.signature.param_names)
    defaults = dict(zip(self.signature.param_names[-len(defaults):], defaults))
    self.signature.defaults = defaults


class InterpreterFunction(SignedFunction):
  """An abstract value representing a user-defined function.

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    code: A code object.
    closure: Tuple of cells (cfg.Variable) containing the free variables
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
    if (loadmarshal.CodeType.has_generator(code.co_flags) and
        "return" in annotations):
      # Check Generator return type
      ret_type = annotations["return"]
      if not Generator.matches_type(ret_type):
        error = "Expected Generator, Iterable or Iterator"
        vm.errorlog.invalid_annotation(vm.frames, ret_type, error)
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
    if loadmarshal.CodeType.has_varargs(code.co_flags):
      count += 1
    if loadmarshal.CodeType.has_varkeywords(code.co_flags):
      count += 1
    return count

  def __init__(self, name, code, f_locals, f_globals, defaults, kw_defaults,
               closure, annotations, late_annotations, vm):
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
    signature = self._build_signature(name, annotations, late_annotations)
    super(InterpreterFunction, self).__init__(signature, vm)
    self.last_frame = None  # for BuildClass
    self._store_call_records = False
    if self.vm.PY3:
      self.is_class_builder = False  # Will be set by BuildClass.
    else:
      self.is_class_builder = self.code.has_opcode(opcodes.LOAD_LOCALS)

  @contextlib.contextmanager
  def record_calls(self):
    """Turn on recording of function calls. Used by analyze.py."""
    old = self._store_call_records
    self._store_call_records = True
    yield
    self._store_call_records = old

  def _build_signature(self, name, annotations, late_annotations):
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
        name,
        tuple(self.code.co_varnames[:self.code.co_argcount]),
        vararg_name,
        tuple(kwonly),
        kwarg_name,
        defaults,
        annotations,
        late_annotations)

  # TODO(kramm): support retrieving the following attributes:
  # 'func_{code, name, defaults, globals, locals, dict, closure},
  # '__name__', '__dict__', '__doc__', '_vm', '_func'

  def get_first_opcode(self):
    return self.code.co_code[0]

  def argcount(self, _):
    return self.code.co_argcount

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
      m.update(compat.bytestring(name))
      for value in var.bindings:
        m.update(value.data.get_fullhash())
    return m.digest()

  @staticmethod
  def _hash_all(*hash_args):
    """Convenience method for hashing a sequence of dicts."""
    return hashlib.md5(b"".join(
        InterpreterFunction._hash(*args)
        for args in hash_args)).digest()

  def match_args(self, node, args, alias_map):
    if not self.signature.has_param_annotations:
      return
    return super(InterpreterFunction, self).match_args(node, args, alias_map)

  def _inner_cls_check(self, last_frame):
    """Check if the function and its nested class use same type parameter."""
    # get all type parameters from function annotations
    all_type_parameters = []
    for annot in self.signature.annotations.values():
      params = self.vm.annotations_util.get_type_parameters(annot)
      all_type_parameters.extend(itm.with_module(None) for itm in params)

    if all_type_parameters:
      for key, value in last_frame.f_locals.pyval.items():
        value = get_atomic_value(value, default=self.vm.convert.unsolvable)
        if (not self.signature.has_param(key)  # skip the argument list
            and isinstance(value, InterpreterClass) and value.template):
          inner_cls_types = value.collect_inner_cls_types()
          inner_cls_types.update([(value, item.with_module(None))
                                  for item in value.template])
          for cls, item in inner_cls_types:
            if item in all_type_parameters:
              self.vm.errorlog.invalid_annotation(
                  self.vm.simple_stack(self.get_first_opcode()), item,
                  ("Function [%s] and its nested generic class [%s] can"
                   " not use the same type variable %s")
                  % (self.full_name, cls.full_name, item.name))

  def _mutations_generator(self, node, first_posarg, substs):
    def generator():
      """Yields mutations."""
      if not self.is_attribute_of_class or not first_posarg or not substs:
        return
      try:
        inst = get_atomic_value(first_posarg, Instance)
      except ConversionError:
        return
      if inst.cls.template:
        for subst in substs:
          for k, v in subst.items():
            if k in inst.instance_type_parameters:
              value = inst.instance_type_parameters[k].AssignToNewVariable(node)
              value.PasteVariable(v, node)
              yield Mutation(inst, k, value)
    # Optimization: return a generator to avoid iterating over the mutations an
    # extra time.
    return generator

  def call(self, node, func, args, new_locals=None, alias_map=None):
    if self.vm.is_at_maximum_depth() and not func_name_is_class_init(self.name):
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      if self.vm.callself_stack:
        for b in self.vm.callself_stack[-1].bindings:
          b.data.maybe_missing_members = True
      return (node,
              self.vm.convert.create_new_unsolvable(node))
    args = args.simplify(node, self.signature, self.vm)
    substs = self.match_args(node, args, alias_map)
    first_posarg = args.posargs[0] if args.posargs else None
    callargs = self._map_args(node, args)
    # Keep type parameters without substitutions, as they may be needed for
    # type-checking down the road.
    annotations = self.vm.annotations_util.sub_annotations(
        node, self.signature.annotations, substs, instantiate_unbound=False)
    if annotations:
      for name in callargs:
        if (name in annotations and (not self.is_attribute_of_class or
                                     self.argcount(node) == 0 or
                                     name != self.signature.param_names[0])):
          extra_key = (self.get_first_opcode(), name)
          node, callargs[name] = self.vm.init_class(
              node, annotations[name], extra_key=extra_key)
    # Might throw vm.RecursionException:
    frame = self.vm.make_frame(
        node, self.code, callargs, self.f_globals, self.f_locals, self.closure,
        new_locals=new_locals, func=func, first_posarg=first_posarg)
    if self.signature.param_names:
      self_var = callargs.get(self.signature.param_names[0])
      caller_is_abstract = self_var and all(
          isinstance(v.cls, Class) and v.cls.is_abstract
          for v in self_var.data if v.cls)
    else:
      caller_is_abstract = False
    check_return = not (caller_is_abstract and self.is_abstract)
    if self.signature.has_return_annotation or not check_return:
      frame.allowed_returns = annotations.get(
          "return", self.vm.convert.unsolvable)
      frame.check_return = check_return
    if self.vm.options.skip_repeat_calls:
      callkey = self._hash_all(
          (callargs, None),
          (frame.f_globals.members, set(self.code.co_names)),
          (frame.f_locals.members,
           set(frame.f_locals.members) - set(self.code.co_varnames)))
    else:
      # Make the callkey the number of times this function has been called so
      # that no call has the same key as a previous one.
      callkey = len(self._call_cache)
    if callkey in self._call_cache:
      old_ret, old_remaining_depth = self._call_cache[callkey]
      # Optimization: This function has already been called, with the same
      # environment and arguments, so recycle the old return value.
      # We would want to skip this optimization and reanalyze the call if we can
      # traverse the function deeper.
      if self.vm.remaining_depth() > old_remaining_depth:
        # TODO(rechen): Reanalysis is necessary only if the VM was unable to
        # completely analyze the call with old_remaining_depth. For now, we can
        # get away with not checking for completion because of how severely
        # --quick constrains the maximum depth.
        log.info("Reanalyzing %r because we can traverse deeper; "
                 "remaining_depth = %d, old_remaining_depth = %d",
                 self.name, self.vm.remaining_depth(), old_remaining_depth)
      else:
        ret = old_ret.AssignToNewVariable(node)
        if self._store_call_records:
          # Even if the call is cached, we might not have been recording it.
          self._call_records.append((callargs, ret, node))
        return node, ret
    if loadmarshal.CodeType.has_generator(self.code.co_flags):
      generator = Generator(frame, self.vm)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for futher matching.
      node2, _ = generator.run_generator(node)
      node_after_call, ret = node2, generator.to_variable(node2)
    else:
      node_after_call, ret = self.vm.run_frame(frame, node)
    self._inner_cls_check(frame)
    mutations = self._mutations_generator(node_after_call, first_posarg, substs)
    node_after_call = _apply_mutations(node_after_call, mutations)
    self._call_cache[callkey] = ret, self.vm.remaining_depth()
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
        combinations = cfg_utils.variable_product_dict(callargs)
      except cfg_utils.TooComplexError:
        combination = {
            name: self.vm.convert.unsolvable.to_binding(node_after_call)
            for name in callargs}
        combinations = [combination]
        ret = self.vm.convert.unsolvable.to_variable(node_after_call)
      for combination in combinations:
        for return_value in ret.bindings:
          values = list(combination.values()) + [return_value]
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
      param_binding = self.vm.convert.unsolvable.to_binding(node)
      params = collections.defaultdict(lambda: param_binding)
      ret = self.vm.convert.unsolvable.to_binding(node)
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
    return loadmarshal.CodeType.has_varargs(self.code.co_flags)

  def has_kwargs(self):
    return loadmarshal.CodeType.has_varkeywords(self.code.co_flags)

  def property_get(self, callself, is_class=False):
    if func_name_is_class_init(self.name) and self.signature.param_names:
      self_name = self.signature.param_names[0]
      if self_name in self.signature.annotations:
        self.vm.errorlog.invalid_annotation(
            self.vm.simple_stack(self.get_first_opcode()),
            self.signature.annotations[self_name],
            details="Cannot annotate self argument of __init__", name=self_name)
        self.signature.del_annotation(self_name)
    return super(InterpreterFunction, self).property_get(callself, is_class)


class SimpleFunction(SignedFunction):
  """An abstract value representing a function with a particular signature.

  Unlike InterpreterFunction, a SimpleFunction has a set signature and does not
  record calls or try to infer types.
  """

  def __init__(self, name, param_names, varargs_name, kwonly_params,
               kwargs_name, defaults, annotations, late_annotations, vm):
    """Create a SimpleFunction.

    Args:
      name: Name of the function as a string
      param_names: Tuple of parameter names as strings.
      varargs_name: The "args" in "*args". String or None.
      kwonly_params: Tuple of keyword-only parameters as strings. These do NOT
        appear in param_names.
      kwargs_name: The "kwargs" in "**kwargs". String or None.
      defaults: Dictionary of string names to values of default arguments.
      annotations: Dictionary of string names to annotations (strings or types).
      late_annotations: Dictionary of string names to string types, used for
        forward references or as-yet-unknown types.
      vm: The virtual machine for this function.
    """
    annotations = dict(annotations)
    late_annotations = dict(late_annotations)
    # Every parameter must have an annotation. Defaults to unsolvable.
    for n in itertools.chain(param_names, [varargs_name, kwargs_name],
                             kwonly_params):
      if n and n not in annotations and n not in late_annotations:
        annotations[n] = vm.convert.unsolvable
    if not isinstance(defaults, dict):
      defaults = dict(zip(param_names[-len(defaults):], defaults))
    signature = function.Signature(name, param_names, varargs_name,
                                   kwonly_params, kwargs_name, defaults,
                                   annotations, late_annotations)
    super(SimpleFunction, self).__init__(signature, vm)
    self.bound_class = BoundFunction

  def call(self, node, _, args, alias_map=None):
    # We only simplify args for _map_args, because that simplifies checking.
    # This allows match_args to typecheck varargs and kwargs.
    # We discard the results from _map_args, because SimpleFunction only cares
    # that the arguments are acceptable.
    self._map_args(node, args.simplify(node))
    substs = self.match_args(node, args, alias_map)
    # Substitute type parameters in the signature's annotations.
    annotations = self.vm.annotations_util.sub_annotations(
        node, self.signature.annotations, substs, instantiate_unbound=False)
    if self.signature.has_return_annotation:
      ret_type = annotations["return"]
      ret = ret_type.instantiate(node)
    else:
      ret = self.vm.convert.none.to_variable(node)
    return node, ret


class BoundFunction(AtomicAbstractValue):
  """An function type which has had an argument bound into it."""

  def __init__(self, callself, underlying):
    super(BoundFunction, self).__init__(underlying.name, underlying.vm)
    self._callself = callself
    self.underlying = underlying
    self.is_attribute_of_class = False

    # If the function belongs to `ParameterizedClass`, we will annotate the
    # `self` when do argument matching
    self.replace_self_annot = None
    inst = get_atomic_value(
        self._callself, default=self.vm.convert.unsolvable)
    if isinstance(self.underlying, InterpreterFunction):
      if isinstance(inst.cls, ParameterizedClass):
        self.replace_self_annot = inst.cls.get_self_annot()
    if isinstance(inst, SimpleAbstractValue):
      self.alias_map = inst.instance_type_parameters.uf
    elif isinstance(inst, TypeParameterInstance):
      self.alias_map = inst.instance.instance_type_parameters.uf
    else:
      self.alias_map = None

  def argcount(self, node):
    return self.underlying.argcount(node) - 1  # account for self

  @property
  def signature(self):
    return self.underlying.signature.drop_first_parameter()

  def call(self, node, func, args, alias_map=None):
    if func_name_is_class_init(self.name):
      self.vm.callself_stack.append(self._callself)
    # The "self" parameter is automatically added to the list of arguments, but
    # only if the function actually takes any arguments.
    if self.argcount(node) >= 0:
      args = args.replace(posargs=(self._callself,) + args.posargs)
    try:
      if self.replace_self_annot:
        with self.underlying.set_self_annot(self.replace_self_annot):
          node, ret = self.underlying.call(node, func, args,
                                           alias_map=self.alias_map)
      else:
        node, ret = self.underlying.call(node, func, args,
                                         alias_map=self.alias_map)
    except InvalidParameters as e:
      if self._callself and self._callself.bindings:
        if "." in e.name:
          # match_args will try to prepend the parent's name to the error name.
          # Overwrite it with _callself instead, which may be more exact.
          _, _, e.name = e.name.partition(".")
        e.name = "%s.%s" % (self._callself.data[0].name, e.name)
      raise
    finally:
      if func_name_is_class_init(self.name):
        self.vm.callself_stack.pop()
    return node, ret

  def get_positional_names(self):
    return self.underlying.get_positional_names()

  def has_varargs(self):
    return self.underlying.has_varargs()

  def has_kwargs(self):
    return self.underlying.has_kwargs()

  def get_class(self):
    return self.underlying.get_class()

  @property
  def is_abstract(self):
    return self.underlying.is_abstract

  @is_abstract.setter
  def is_abstract(self, value):
    self.underlying.is_abstract = value

  def repr_names(self, callself_repr=None):
    """Names to use in the bound function's string representation.

    This function can return multiple names because there may be multiple
    bindings in callself.

    Args:
      callself_repr: Optionally, a repr function for callself.

    Returns:
      A non-empty iterable of string names.
    """
    callself_repr = callself_repr or (lambda v: v.name)
    if self._callself and self._callself.bindings:
      callself_names = [callself_repr(v) for v in self._callself.data]
    else:
      callself_names = ["<class>"]
    # We don't need to recursively call repr_names() because we replace the
    # parent name with the callself.
    underlying = self.underlying.name
    if underlying.count(".") > 0:
      underlying = underlying.split(".", 1)[-1]
    return [callself + "." + underlying for callself in callself_names]

  def __repr__(self):
    return self.repr_names()[0] + "(...)"


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

  SEND = "_T2"
  RET = "_V"

  @staticmethod
  def matches_type(type_obj):
    """Check if type_obj matches a Generator type."""
    if isinstance(type_obj, Union):
      return all(Generator.matches_type(sub_type)
                 for sub_type in type_obj.options)
    else:
      base_cls = type_obj
      if isinstance(type_obj, ParameterizedClass):
        base_cls = type_obj.base_cls
      return ((isinstance(base_cls, PyTDClass) and
               base_cls.name in ("generator", "Iterable", "Iterator")) or
              isinstance(base_cls, AMBIGUOUS_OR_EMPTY))

  def __init__(self, generator_frame, vm):
    super(Generator, self).__init__(vm.convert.generator_type, vm)
    self.generator_frame = generator_frame
    self.runs = 0

  def get_special_attribute(self, node, name, valself):
    if name == "__iter__":
      f = NativeFunction(name, self.__iter__, self.vm)
      return f.to_variable(node)
    elif name == self.vm.convert.next_attr:
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

  def run_generator(self, node):
    """Run the generator."""
    if self.runs == 0:  # Optimization: We only run the coroutine once.
      node, _ = self.vm.resume_frame(node, self.generator_frame)
      ret_type = self.generator_frame.allowed_returns
      if ret_type:
        # set type parameters according to annotated Generator return type
        for param_name in (T, self.SEND, self.RET):
          _, param_var = self.vm.init_class(
              node, ret_type.get_formal_type_parameter(param_name))
          self.merge_instance_type_parameter(node, param_name, param_var)
      else:
        # infer the type parameters based on the collected type information.
        self.merge_instance_type_parameter(
            node, T, self.generator_frame.yield_variable)
        # For SEND type, it can not be decided until the SEND function is called
        # later on. So set SEND type as ANY so that the type check will not fail
        # when the function is called afterwards.
        self.merge_instance_type_parameter(
            node, self.SEND, self.vm.convert.unsolvable.to_variable(node))
        self.merge_instance_type_parameter(
            node, self.RET, self.generator_frame.return_variable)
      self.runs += 1
    return node, self.get_instance_type_parameter(T)

  def call(self, node, func, args, alias_map=None):
    """Call this generator or (more common) its "next" attribute."""
    del func, args
    return self.run_generator(node)


class Iterator(Instance, HasSlots):
  """A representation of instances of iterators."""

  def __init__(self, vm, return_var):
    super(Iterator, self).__init__(vm.convert.iterator_type, vm)
    HasSlots.init_mixin(self)
    self.set_slot(self.vm.convert.next_attr, self.next_slot)
    # TODO(dbaum): Should we set instance_type_parameters[self.TYPE_PARAM] to
    # something based on return_var?
    self._return_var = return_var

  def next_slot(self, node):
    return node, self._return_var


class Module(Instance):
  """Represents an (imported) module."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm, name, member_map, ast):
    super(Module, self).__init__(vm.convert.module_type, vm)
    self.name = name
    self._member_map = member_map
    self.ast = ast

  def _convert_member(self, name, ty):
    """Called to convert the items in _member_map to cfg.Variable."""
    var = self.vm.convert.constant_to_var(ty)
    for value in var.data:
      # Only do this if this is a class which isn't already part of a module, or
      # is a module itself.
      # (This happens if e.g. foo.py does "from bar import x" and we then
      #  do "from foo import x".)
      if not value.module and not isinstance(value, Module):
        value.module = self.name
    self.vm.trace_module_member(self, name, var)
    return var

  @property
  def module(self):
    return None

  @module.setter
  def module(self, m):
    assert (m is None or m == self.ast.name), (m, self.ast.name)

  @property
  def full_name(self):
    return self.ast.name

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

  def get_fullhash(self):
    """Hash the set of member names."""
    m = hashlib.md5()
    m.update(compat.bytestring(self.full_name))
    for k in self._member_map:
      m.update(compat.bytestring(k))
    return m.digest()


class BuildClass(AtomicAbstractValue):
  """Representation of the Python 3 __build_class__ object."""

  CLOSURE_NAME = "__class__"

  def __init__(self, vm):
    super(BuildClass, self).__init__("__build_class__", vm)

  def call(self, node, _, args, alias_map=None):
    funcvar, name = args.posargs[0:2]
    kwargs = args.namedargs.pyval
    # TODO(mdemello): Check if there are any changes between python2 and
    # python3 in the final metaclass computation.
    # TODO(mdemello): Any remaining kwargs need to be passed to the metaclass.
    metaclass = kwargs.get("metaclass", None)
    if len(funcvar.bindings) != 1:
      raise ConversionError("Invalid ambiguous argument to __build_class__")
    func, = funcvar.data
    if not isinstance(func, InterpreterFunction):
      raise ConversionError("Invalid argument to __build_class__")
    func.is_class_builder = True
    bases = args.posargs[2:]

    node, _ = func.call(node, funcvar.bindings[0],
                        args.replace(posargs=(), namedargs={}),
                        new_locals=True)
    if func.last_frame:
      func.f_locals = func.last_frame.f_locals
      class_closure_var = func.last_frame.class_closure_var
    else:
      # We have hit 'maximum depth' before setting func.last_frame
      func.f_locals = self.vm.convert.unsolvable
      class_closure_var = None
    for base in bases:
      # If base class is NamedTuple, we will call its own make_class method to
      # make a class.
      base = _get_class(base, default=self.vm.convert.unsolvable)
      if isinstance(base, PyTDClass) and base.full_name == "typing.NamedTuple":
        # The subclass of NamedTuple will ignore all its base classes. This is
        # controled by a metaclass provided to NamedTuple.
        # See: https://github.com/python/typing/blob/master/src/typing.py#L2170
        return base.make_class(node, func.f_locals.to_variable(node))
    return node, self.vm.make_class(
        node, name, list(bases), func.f_locals.to_variable(node), metaclass,
        new_class_var=class_closure_var)


# TODO(rechen): Don't allow this class to be instantiated multiple times. It's
# useful to be able to do comparisons like `var.data == [convert.unsolvable]`,
# and those require Unsolvable to be a singleton.
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

  def compute_mro(self):
    return self.default_mro()

  def get_special_attribute(self, node, name, _):
    if name in self.IGNORED_ATTRIBUTES:
      return None
    else:
      return self.to_variable(node)

  def call(self, node, func, args, alias_map=None):
    del func, args
    # return ourself.
    return node, self.to_variable(node)

  def argcount(self, _):
    return 0

  def to_variable(self, node):
    return self.vm.program.NewVariable([self], source_set=[], where=node)

  def get_class(self):
    # return ourself.
    return self

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
      cfg.Variable.
    owner: cfg.Binding that contains this instance as data.
  """

  _current_id = 0

  # For simplicity, Unknown doesn't emulate descriptors:
  IGNORED_ATTRIBUTES = ["__get__", "__set__", "__getattribute__"]

  def __init__(self, vm):
    name = "~unknown%d" % Unknown._current_id
    super(Unknown, self).__init__(name, vm)
    self.members = datatypes.MonitorDict()
    self.owner = None
    Unknown._current_id += 1
    self.class_name = self.name
    self._calls = []
    log.info("Creating %s", self.class_name)

  def compute_mro(self):
    return self.default_mro()

  def get_fullhash(self):
    # Unknown needs its own implementation of get_fullhash to ensure equivalent
    # Unknowns produce the same hash. "Equivalent" in this case means "has the
    # same members," so member names are used in the hash instead of id().
    m = hashlib.md5()
    for name in self.members:
      m.update(compat.bytestring(name))
    return m.digest()

  def get_children_maps(self):
    return (self.members,)

  @staticmethod
  def _to_pytd(node, v):
    if isinstance(v, cfg.Variable):
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

  def call(self, node, _, args, alias_map=None):
    ret = self.vm.convert.create_new_unknown(
        node, source=self.owner, action="call:" + self.name)
    self._calls.append((args.posargs, args.namedargs, ret))
    return node, ret

  def argcount(self, _):
    return 0

  def to_variable(self, node):
    v = self.vm.program.NewVariable()
    val = v.AddBinding(self, source_set=[], where=node)
    self.owner = val
    self.vm.trace_unknown(self.class_name, val)
    return v

  def to_structural_def(self, node, class_name):
    """Convert this Unknown to a pytd.Class."""
    self_param = (pytd.Parameter("self", pytd.AnythingType(),
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
        classes=(),
        slots=None,
        template=())

  def get_class(self):
    # We treat instances of an Unknown as the same as the class.
    return self

  def instantiate(self, node, container=None):
    return self.to_variable(node)


AMBIGUOUS = (Unknown, Unsolvable)
AMBIGUOUS_OR_EMPTY = AMBIGUOUS + (Empty,)
