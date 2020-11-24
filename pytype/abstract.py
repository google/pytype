"""The abstract values used by vm.py.

This file contains AtomicAbstractValue and its subclasses. Mixins such as Class
are in mixin.py, and other abstract logic is in abstract_utils.py.
"""

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

from pytype import abstract_utils
from pytype import compat
from pytype import datatypes
from pytype import function
from pytype import mixin
from pytype import utils
from pytype.pyc import opcodes
from pytype.pytd import escape
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)


class AtomicAbstractValue(utils.VirtualMachineWeakrefMixin):
  """A single abstract value such as a type or function signature.

  This is the base class of the things that appear in Variables. It represents
  an atomic object that the abstract interpreter works over just as variables
  represent sets of parallel options.

  Conceptually abstract values represent sets of possible concrete values in
  compact form. For instance, an abstract value with .__class__ = int represents
  all ints.
  """

  formal = False  # is this type non-instantiable?

  def __init__(self, name, vm):
    """Basic initializer for all AtomicAbstractValues."""
    super().__init__(vm)
    assert hasattr(vm, "program"), type(self)
    self.cls = None
    self.name = name
    self.mro = self.compute_mro()
    self.module = None
    self.official_name = None
    self.slots = None  # writable attributes (or None if everything is writable)
    # true for functions and classes that have decorators applied to them.
    self.is_decorated = False
    # The template for the current class. It is usually a constant, lazily
    # loaded to accommodate recursive types, but in the case of typing.Generic
    # (only), it'll change every time when a new generic class is instantiated.
    self._template = None
    # names in the templates of the current class and its base classes
    self._all_template_names = None
    self._instance = None

    # The variable or function arg name with the type annotation that this
    # instance was created from. For example,
    #   x: str = "hello"
    # would create an instance of str with from_annotation = 'x'
    self.from_annotation = None

  @property
  def all_template_names(self):
    if self._all_template_names is None:
      self._all_template_names = abstract_utils.get_template(self)
    return self._all_template_names

  @property
  def template(self):
    if self._template is None:
      # Won't recompute if `compute_template` throws exception
      self._template = ()
      self._template = abstract_utils.compute_template(self)
    return self._template

  @property
  def full_name(self):
    return (self.module + "." if self.module else "") + self.name

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
    seen_data = set()
    stack = [self]
    while stack:
      data = stack.pop()
      data_hash = hash(data)
      if data_hash in seen_data:
        continue
      seen_data.add(data_hash)
      m.update(compat.bytestring(data_hash))
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
    return self.vm.new_unsolvable(node)

  def get_formal_type_parameter(self, t):
    """Get the class's type for the type parameter.

    Treating self as a mixin.Class, gets its formal type for the given
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
      function.FailedFunctionCall

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
    the formal definition of a class. See InterpreterClass and TupleClass.

    Args:
      instance: An instance of this class (as an AtomicAbstractValue)
    """

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
    """Create an instance of self.

    Note that this method does not call __init__, so the instance may be
    incomplete. If you need a complete instance, use self.vm.init_class instead.

    Args:
      node: The current node.
      container: Optionally, the value that contains self. (See TypeParameter.)

    Returns:
      The instance.
    """
    del container
    return self._to_instance().to_variable(node)

  def _to_instance(self):
    return Instance(self, self.vm)

  def to_annotation_container(self):
    return AnnotationContainer(self.name, self.vm, self)

  def to_variable(self, node):
    """Build a variable out of this abstract value.

    Args:
      node: The current CFG node.
    Returns:
      A cfg.Variable.
    """
    return self.vm.program.NewVariable([self], source_set=[], where=node)

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
    def _get_values(parameter):
      return {b.data.get_type_key(): b for b in parameter.bindings}.values()
    return [_get_values(parameter) for parameter in self._unique_parameters()]

  def init_subclass(self, node, cls):
    """Allow metaprogramming via __init_subclass__.

    We do not analyse __init_subclass__ methods in the code, but overlays that
    wish to replicate metaprogramming constructs using __init_subclass__ can
    define a class overriding this method, and vm.make_class will call
    Class.call_init_subclass(), which will invoke the init_subclass() method for
    all classes in the list of base classes.

    This is here rather than in mixin.Class because a class's list of bases can
    include abstract objects that do not derive from Class (e.g. Unknown and
    Unsolvable).

    Args:
      node: cfg node
      cls: the abstract.InterpreterClass that is being constructed with subclass
           as a base
    Returns:
      A possibly new cfg node
    """
    del cls
    return node

  def update_official_name(self, _):
    """Update the official name."""

  # The below methods allow code to do isinstance() checks on abstract values
  # without importing abstract.py, making it easier to avoid import cycles.

  def isinstance_AMBIGUOUS_OR_EMPTY(self):
    return isinstance(self, AMBIGUOUS_OR_EMPTY)

  def isinstance_AnnotationsDict(self):
    return isinstance(self, AnnotationsDict)

  def isinstance_BoundFunction(self):
    return isinstance(self, BoundFunction)

  def isinstance_Class(self):
    return isinstance(self, mixin.Class)

  def isinstance_ClassMethodInstance(self):
    return False  # overridden in special_builtins.ClassMethodInstance

  def isinstance_Instance(self):
    return isinstance(self, Instance)

  def isinstance_InterpreterClass(self):
    return isinstance(self, InterpreterClass)

  def isinstance_InterpreterFunction(self):
    return isinstance(self, InterpreterFunction)

  def isinstance_LiteralClass(self):
    return isinstance(self, LiteralClass)

  def isinstance_ParameterizedClass(self):
    return isinstance(self, ParameterizedClass)

  def isinstance_PropertyInstance(self):
    return False  # overridden in special_builtins.PropertyInstance

  def isinstance_PyTDClass(self):
    return isinstance(self, PyTDClass)

  def isinstance_PyTDFunction(self):
    return isinstance(self, PyTDFunction)

  def isinstance_SimpleAbstractValue(self):
    return isinstance(self, SimpleAbstractValue)

  def isinstance_StaticMethodInstance(self):
    return False  # overridden in special_builtins.StaticMethodInstance

  def isinstance_Tuple(self):
    return isinstance(self, Tuple)

  def isinstance_TypeParameter(self):
    return isinstance(self, TypeParameter)

  def isinstance_Union(self):
    return isinstance(self, Union)

  def isinstance_Unsolvable(self):
    return isinstance(self, Unsolvable)

  def is_late_annotation(self):
    return False


class Singleton(AtomicAbstractValue):
  """A Singleton class must only be instantiated once.

  This is essentially an ABC for Unsolvable, Empty, and others.
  """

  _instance = None

  def __new__(cls, *args, **kwargs):
    # If cls is a subclass of a subclass of Singleton, cls._instance will be
    # filled by its parent. cls needs to be given its own instance.
    if not cls._instance or type(cls._instance) != cls:  # pylint: disable=unidiomatic-typecheck
      log.debug("Singleton: Making new instance for %s", cls)
      cls._instance = super().__new__(cls)
    return cls._instance

  def get_special_attribute(self, node, name, valself):
    del name, valself
    return self.to_variable(node)

  def compute_mro(self):
    return self.default_mro()

  def call(self, node, func, args, alias_map=None):
    del func, args
    return node, self.to_variable(node)

  def get_class(self):
    return self

  def instantiate(self, node, container=None):
    return self.to_variable(node)


class Empty(Singleton):
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
    super().__init__("empty", vm)


class Deleted(Empty):
  """Assigned to variables that have del called on them."""

  def __init__(self, vm):
    super().__init__(vm)
    self.name = "deleted"


class TypeParameter(AtomicAbstractValue):
  """Parameter of a type."""

  formal = True

  def __init__(self, name, vm, constraints=(), bound=None,
               covariant=False, contravariant=False, module=None):
    super().__init__(name, vm)
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

  def call(self, node, func, args, alias_map=None):
    return node, self.instantiate(node)


class TypeParameterInstance(AtomicAbstractValue):
  """An instance of a type parameter."""

  def __init__(self, param, instance, vm):
    super().__init__(param.name, vm)
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

  Attributes:
    members: A name->value dictionary of the instance's attributes.
  """

  def __init__(self, name, vm):
    """Initialize a SimpleAbstractValue.

    Args:
      name: Name of this value. For debugging and error reporting.
      vm: The TypegraphVirtualMachine to use.
    """
    super().__init__(name, vm)
    self.members = datatypes.MonitorDict()
    # Lazily loaded to handle recursive types.
    # See Instance._load_instance_type_parameters().
    self._instance_type_parameters = datatypes.AliasingMonitorDict()
    # This attribute depends on self.cls, which isn't yet set to its true value.
    self._maybe_missing_members = None
    # The latter caches the result of get_type_key. This is a recursive function
    # that has the potential to generate too many calls for large definitions.
    self._cached_type_key = (
        (self.members.changestamp, self._instance_type_parameters.changestamp),
        None)

  @property
  def instance_type_parameters(self):
    return self._instance_type_parameters

  @property
  def maybe_missing_members(self):
    if self._maybe_missing_members is None:
      self._maybe_missing_members = isinstance(
          self.cls, (InterpreterClass, PyTDClass)) and self.cls.is_dynamic
    return self._maybe_missing_members

  @maybe_missing_members.setter
  def maybe_missing_members(self, v):
    self._maybe_missing_members = v

  def has_instance_type_parameter(self, name):
    """Check if the key is in `instance_type_parameters`."""
    name = abstract_utils.full_type_name(self, name)
    return name in self.instance_type_parameters

  def get_children_maps(self):
    return (self.instance_type_parameters, self.members)

  def get_instance_type_parameter(self, name, node=None):
    name = abstract_utils.full_type_name(self, name)
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
    name = abstract_utils.full_type_name(self, name)
    log.info("Modifying type param %s", name)
    if name in self.instance_type_parameters:
      self.instance_type_parameters[name].PasteVariable(value, node)
    else:
      self.instance_type_parameters[name] = value

  def call(self, node, _, args, alias_map=None):
    node, var = self.vm.attribute_handler.get_attribute(
        node, self, "__call__", self.to_binding(node))
    if var is not None and var.bindings:
      return self.vm.call_function(node, var, args)
    else:
      raise function.NotCallable(self)

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
    elif isinstance(self, InterpreterClass):
      return ParameterizedClass(
          self.vm.convert.type_type, {abstract_utils.T: self}, self.vm)
    elif isinstance(self, (AnnotationClass, mixin.Class)):
      return self.vm.convert.type_type

  def set_class(self, node, var):
    """Set the __class__ of an instance, for code that does "x.__class__ = y."""
    # Simplification: Setting __class__ is done rarely, and supporting this
    # action would complicate pytype considerably by forcing us to track the
    # class in a variable, so we instead fall back to Any.
    try:
      new_cls = abstract_utils.get_atomic_value(var)
    except abstract_utils.ConversionError:
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
      subkey = frozenset(
          value.data.get_default_type_key()  # pylint: disable=g-long-ternary
          if value.data in seen else value.data.get_type_key(seen)
          for value in var.bindings)
      key.add((name, subkey))
    if key:
      type_key = frozenset(key)
    else:
      type_key = super().get_type_key()
    self._cached_type_key = (
        (self.members.changestamp, self.instance_type_parameters.changestamp),
        type_key)
    return type_key

  def _unique_parameters(self):
    parameters = super()._unique_parameters()
    parameters.extend(self.instance_type_parameters.values())
    return parameters


class Instance(SimpleAbstractValue):
  """An instance of some object."""

  def __init__(self, cls, vm):
    super().__init__(cls.name, vm)
    self.cls = cls
    self._instance_type_parameters_loaded = False
    cls.register_instance(self)

  def _load_instance_type_parameters(self):
    if self._instance_type_parameters_loaded:
      return
    all_formal_type_parameters = datatypes.AliasingMonitorDict()
    abstract_utils.parse_formal_type_parameters(
        self.cls, None, all_formal_type_parameters)
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

  @property
  def full_name(self):
    return self.get_class().full_name

  @property
  def instance_type_parameters(self):
    self._load_instance_type_parameters()
    return self._instance_type_parameters


class List(Instance, mixin.HasSlots, mixin.PythonConstant):
  """Representation of Python 'list' objects."""

  def __init__(self, content, vm):
    super().__init__(vm.convert.list_type, vm)
    self._instance_cache = {}
    mixin.PythonConstant.init_mixin(self, content)
    mixin.HasSlots.init_mixin(self)
    combined_content = vm.convert.build_content(content)
    self.merge_instance_type_parameter(None, abstract_utils.T, combined_content)
    self.could_contain_anything = False
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__getslice__", self.getslice_slot)

  def str_of_constant(self, printer):
    return "[%s]" % ", ".join(" or ".join(abstract_utils.var_map(printer, val))
                              for val in self.pyval)

  def __repr__(self):
    if self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return mixin.PythonConstant.__repr__(self)

  def merge_instance_type_parameter(self, node, name, value):
    self.could_contain_anything = True
    super().merge_instance_type_parameter(node, name, value)

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
        except abstract_utils.ConversionError:
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
      abstract_utils.ConversionError: If the data could not be converted.
    """
    if isinstance(data, AbstractOrConcreteValue):
      return self.vm.convert.value_to_constant(data, (int, type(None)))
    elif isinstance(data, Instance):
      if data.cls != self.vm.convert.int_type:
        raise abstract_utils.ConversionError()
      else:
        return None
    else:
      raise abstract_utils.ConversionError()

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
        except abstract_utils.ConversionError:
          unresolved = True
        else:
          results.append(List(self.pyval[start:end], self.vm).to_variable(node))
    if unresolved or self.could_contain_anything:
      results.append(ret)
    return node, self.vm.join_variables(node, results)


class Tuple(Instance, mixin.PythonConstant):
  """Representation of Python 'tuple' objects."""

  def __init__(self, content, vm):
    combined_content = vm.convert.build_content(content)
    class_params = {
        name: vm.convert.merge_classes(instance_param.data)
        for name, instance_param in
        tuple(enumerate(content)) + ((abstract_utils.T, combined_content),)}
    cls = TupleClass(vm.convert.tuple_type, class_params, vm)
    super().__init__(cls, vm)
    self.merge_instance_type_parameter(None, abstract_utils.T, combined_content)
    mixin.PythonConstant.init_mixin(self, content)
    self.tuple_length = len(self.pyval)
    self._hash = None  # memoized due to expensive computation

  def str_of_constant(self, printer):
    content = ", ".join(" or ".join(abstract_utils.var_map(printer, val))
                        for val in self.pyval)
    if self.tuple_length == 1:
      content += ","
    return "(%s)" % content

  def _unique_parameters(self):
    parameters = super()._unique_parameters()
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
      approximate_hash = lambda var: tuple(v.full_name for v in var.data)
      self._hash = hash((self.tuple_length,) +
                        tuple(approximate_hash(e) for e in self.pyval))
    return self._hash


class Dict(Instance, mixin.HasSlots, mixin.PythonConstant,
           pytd_utils.WrapsDict("pyval")):
  """Representation of Python 'dict' objects.

  It works like __builtins__.dict, except that, for string keys, it keeps track
  of what got stored.
  """

  def __init__(self, vm):
    super().__init__(vm.convert.dict_type, vm)
    mixin.HasSlots.init_mixin(self)
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
    mixin.PythonConstant.init_mixin(self, collections.OrderedDict())

  def str_of_constant(self, printer):
    return str({name: " or ".join(abstract_utils.var_map(printer, value))
                for name, value in self.pyval.items()})

  def __repr__(self):
    if not hasattr(self, "could_contain_anything"):
      return "Dict (not fully initialized)"
    elif self.could_contain_anything:
      return Instance.__repr__(self)
    else:
      return mixin.PythonConstant.__repr__(self)

  def getitem_slot(self, node, name_var):
    """Implements the __getitem__ slot."""
    results = []
    unresolved = False
    if not self.could_contain_anything:
      for val in name_var.bindings:
        try:
          name = self.vm.convert.value_to_constant(val.data, str)
        except abstract_utils.ConversionError:
          unresolved = True
        else:
          try:
            results.append(self.pyval[name])
          except KeyError as e:
            unresolved = True
            raise function.DictKeyMissing(name) from e
    node, ret = self.call_pytd(node, "__getitem__", name_var)
    if unresolved or self.could_contain_anything:
      # We *do* know the overall type of the values through the "V" type
      # parameter, even if we don't know the exact type of self[name]. So let's
      # just use the (less accurate) value from pytd.
      results.append(ret)
    return node, self.vm.join_variables(node, results)

  def set_str_item(self, node, name, value_var):
    self.merge_instance_type_parameter(
        node, abstract_utils.K, self.vm.convert.build_string(node, name))
    self.merge_instance_type_parameter(node, abstract_utils.V, value_var)
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
      except abstract_utils.ConversionError:
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
    if any(abstract_utils.has_type_parameters(node, x) for x in value_var.data):
      value_var = self.vm.new_unsolvable(node)
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
        str_key = abstract_utils.get_atomic_python_constant(key_var, str)
      except abstract_utils.ConversionError:
        value = None
      else:
        value = str_key in self.pyval
    return node, self.vm.convert.build_bool(node, value)

  def pop_slot(self, node, key_var, default_var=None):
    try:
      str_key = abstract_utils.get_atomic_python_constant(key_var, str)
    except abstract_utils.ConversionError:
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
      except KeyError as e:
        raise function.DictKeyMissing(str_key) from e

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
        if key not in omit:
          self.set_str_item(node, key, value)
      if isinstance(other_dict, Dict):
        k = other_dict.get_instance_type_parameter(abstract_utils.K, node)
        v = other_dict.get_instance_type_parameter(abstract_utils.V, node)
        self.merge_instance_type_parameter(node, abstract_utils.K, k)
        self.merge_instance_type_parameter(node, abstract_utils.V, v)
        self.could_contain_anything |= other_dict.could_contain_anything
    else:
      assert isinstance(other_dict, AtomicAbstractValue)
      if (isinstance(other_dict, Instance) and
          other_dict.full_name == "__builtin__.dict"):
        k = other_dict.get_instance_type_parameter(abstract_utils.K, node)
        v = other_dict.get_instance_type_parameter(abstract_utils.V, node)
      else:
        k = v = self.vm.new_unsolvable(node)
      self.merge_instance_type_parameter(node, abstract_utils.K, k)
      self.merge_instance_type_parameter(node, abstract_utils.V, v)
      self.could_contain_anything = True


class AnnotationsDict(Dict):
  """__annotations__ dict."""

  def __init__(self, annotated_locals, vm):
    super().__init__(vm)
    self.annotated_locals = annotated_locals

  def get_type(self, node, name):
    if name not in self.annotated_locals:
      return None
    return self.annotated_locals[name].get_type(node, name)

  def get_annotations(self, node):
    for name, local in self.annotated_locals.items():
      typ = local.get_type(node, name)
      if typ:
        yield name, typ


class LateAnnotation:
  """A late annotation.

  A late annotation stores a string expression and a snapshot of the VM stack at
  the point where the annotation was introduced. Once the expression is
  resolved, the annotation pretends to be the resolved type; before that, it
  pretends to be an unsolvable. This effect is achieved by delegating attribute
  lookup with __getattribute__.

  Note that for late annotation x, `isinstance(x, ...)` and `x.__class__` will
  use the type that x is pretending to be; `type(x)` will reveal x's true type.
  Use `x.is_late_annotation()` to check whether x is a late annotation.
  """

  def __init__(self, expr, stack, vm):
    self.expr = expr
    self.stack = stack
    self.vm = vm
    self.resolved = False
    self._type = vm.convert.unsolvable  # the resolved type of `expr`
    self._unresolved_instances = set()
    # _attribute_names needs to be defined last!
    self._attribute_names = (
        set(LateAnnotation.__dict__) |
        set(super().__getattribute__("__dict__")))

  def __repr__(self):
    return "LateAnnotation(%r, resolved=%r)" % (
        self.expr, self._type if self.resolved else None)

  # __hash__ and __eq__ need to be explicitly defined for Python to use them in
  # set/dict comparisons.

  def __hash__(self):
    return hash(self._type) if self.resolved else hash(self.expr)

  def __eq__(self, other):
    return hash(self) == hash(other)

  def __getattribute__(self, name):
    if name == "_attribute_names" or name in self._attribute_names:
      return super().__getattribute__(name)
    return self._type.__getattribute__(name)

  def resolve(self, node, f_globals, f_locals):
    """Resolve the late annotation."""
    if self.resolved:
      return
    self.resolved = True
    var, errorlog = abstract_utils.eval_expr(
        self.vm, node, f_globals, f_locals, self.expr)
    if errorlog:
      self.vm.errorlog.copy_from(errorlog.errors, self.stack)
    self._type = self.vm.annotations_util.extract_annotation(
        node, var, None, self.stack)
    if self._type != self.vm.convert.unsolvable:
      # We may have tried to call __init__ on instances of this annotation.
      # Since the annotation was unresolved at the time, we need to call
      # __init__ again to define any instance attributes.
      for instance in self._unresolved_instances:
        self.vm.reinitialize_if_initialized(node, instance)
    log.info("Resolved late annotation %r to %r", self.expr, self._type)

  def to_variable(self, node):
    if self.resolved:
      return self._type.to_variable(node)
    else:
      return AtomicAbstractValue.to_variable(self, node)

  def instantiate(self, node, container=None):
    if self.resolved:
      return self._type.instantiate(node, container)
    else:
      instance = Instance(self, self.vm)
      self._unresolved_instances.add(instance)
      return instance.to_variable(node)

  def get_special_attribute(self, node, name, valself):
    if name == "__getitem__" and not self.resolved:
      container = AtomicAbstractValue.to_annotation_container(self)
      return container.get_special_attribute(node, name, valself)
    return self._type.get_special_attribute(node, name, valself)

  def is_late_annotation(self):
    return True


class AnnotationClass(SimpleAbstractValue, mixin.HasSlots):
  """Base class of annotations that can be parameterized."""

  def __init__(self, name, vm):
    super().__init__(name, vm)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = abstract_utils.maybe_extract_tuple(slice_var)
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
    super().__init__(name, vm)
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
    last_index = len(inner) - 1
    if last_index and last_index in ellipses and len(inner) > len(template):
      # Even if an ellipsis is not allowed at this position, strip it off so
      # that we report only one error for something like 'List[int, ...]'
      inner = inner[:-1]
    return template, inner, ParameterizedClass

  def _build_value(self, node, raw_inner, ellipses):
    if self.base_cls.is_late_annotation():
      # A parameterized LateAnnotation should be converted to another
      # LateAnnotation to delay evaluation until the first late annotation is
      # resolved. We don't want to create a ParameterizedClass immediately
      # because (1) ParameterizedClass expects its base_cls to be a mixin.Class,
      # and (2) we have to postpone error-checking anyway so we might as well
      # postpone the entire evaluation.
      printed_params = []
      for i, param in enumerate(raw_inner):
        if i in ellipses:
          printed_params.append("...")
        else:
          printed_params.append(pytd_utils.Print(param.get_instance_type(node)))
      expr = "%s[%s]" % (self.base_cls.expr, ", ".join(printed_params))
      annot = LateAnnotation(expr, self.base_cls.stack, self.vm)
      self.vm.late_annotations[self.base_cls.expr].append(annot)
      return annot
    template, inner, abstract_class = self._get_value_info(raw_inner, ellipses)
    if self.base_cls.full_name == "typing.Generic":
      # Generic is unique in that parameterizing it defines a new template;
      # usually, the parameterized class inherits the base class's template.
      template_params = [
          param.with_module(self.base_cls.full_name) for param in inner]
    else:
      template_params = None
    if len(inner) != len(template):
      if not template:
        self.vm.errorlog.not_indexable(self.vm.frames, self.base_cls.name,
                                       generic_warning=True)
      else:
        # Use the unprocessed values of `template` and `inner` so that the error
        # message matches what the user sees.
        name = "%s[%s]" % (
            self.full_name, ", ".join(t.name for t in self.base_cls.template))
        error = "Expected %d parameter(s), got %d" % (
            len(self.base_cls.template), len(raw_inner))
        self.vm.errorlog.invalid_annotation(self.vm.frames, None, error, name)
    else:
      if len(inner) == 1:
        val, = inner
        # It's a common mistake to index tuple, not tuple().
        # We only check the "int" case, since string literals are allowed for
        # late annotations.
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
            formal = self.vm.annotations_util.sub_one_annotation(
                root_node, formal, [{}])
            self.vm.errorlog.bad_concrete_type(
                self.vm.frames, root_node, formal, actual, bad)
            return self.vm.convert.unsolvable

    try:
      return abstract_class(self.base_cls, params, self.vm, template_params)
    except abstract_utils.GenericTypeError as e:
      self.vm.errorlog.invalid_annotation(self.vm.frames, e.annot, e.error)
      return self.vm.convert.unsolvable


class AbstractOrConcreteValue(Instance, mixin.PythonConstant):
  """Abstract value with a concrete fallback."""

  def __init__(self, pyval, cls, vm):
    super().__init__(cls, vm)
    mixin.PythonConstant.init_mixin(self, pyval)


class LazyConcreteDict(
    SimpleAbstractValue, mixin.PythonConstant, mixin.LazyMembers):
  """Dictionary with lazy values."""

  def __init__(self, name, member_map, vm):
    super().__init__(name, vm)
    mixin.PythonConstant.init_mixin(self, self.members)
    mixin.LazyMembers.init_mixin(self, member_map)

  def _convert_member(self, pyval):
    return self.vm.convert.constant_to_var(pyval)

  def is_empty(self):
    return not bool(self._member_map)


class Union(AtomicAbstractValue, mixin.NestedAnnotation, mixin.HasSlots):
  """A list of types. Used for parameter matching.

  Attributes:
    options: Iterable of instances of AtomicAbstractValue.
  """

  def __init__(self, options, vm):
    super().__init__("Union", vm)
    assert options
    self.options = list(options)
    # TODO(rechen): Don't allow a mix of formal and non-formal types
    self.formal = any(t.formal for t in self.options)
    mixin.NestedAnnotation.init_mixin(self)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)

  def __repr__(self):
    return "%s[%s]" % (self.name, ", ".join(repr(o) for o in self.options))

  def __eq__(self, other):
    if isinstance(other, type(self)):
      return self.options == other.options
    return NotImplemented

  def __ne__(self, other):
    return not self == other

  def __hash__(self):
    return hash(tuple(self.options))

  def _unique_parameters(self):
    return [o.to_variable(self.vm.root_cfg_node) for o in self.options]

  def _get_type_params(self):
    params = self.vm.annotations_util.get_type_parameters(self)
    params = [x.name for x in params]
    return utils.unique_list(params)

  def getitem_slot(self, node, slice_var):
    """Custom __getitem__ implementation."""
    slice_content = abstract_utils.maybe_extract_tuple(slice_var)
    params = self._get_type_params()
    # Check that we are instantiating all the unbound type parameters
    if len(params) != len(slice_content):
      details = ("Union has %d type parameters but was instantiated with %d" %
                 (len(params), len(slice_content)))
      self.vm.errorlog.invalid_annotation(
          self.vm.frames, self, details=details)
      return node, self.vm.new_unsolvable(node)
    concrete = [x.data[0].instantiate(node) for x in slice_content]
    substs = [dict(zip(params, concrete))]
    new = self.vm.annotations_util.sub_one_annotation(node, self, substs)
    return node, new.to_variable(node)

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

  def get_inner_types(self):
    return enumerate(self.options)

  def update_inner_type(self, key, typ):
    self.options[key] = typ

  def replace(self, inner_types):
    return self.__class__((v for _, v in sorted(inner_types)), self.vm)


class Function(SimpleAbstractValue):
  """Base class for function objects (NativeFunction, InterpreterFunction).

  Attributes:
    name: Function name. Might just be something like "<lambda>".
    vm: TypegraphVirtualMachine instance.
  """

  def __init__(self, name, vm):
    super().__init__(name, vm)
    self.cls = FunctionPyTDClass(self, vm)
    self.is_attribute_of_class = False
    self.is_classmethod = False
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

  def _get_cell_variable_name(self, var):
    """Get the python variable name of a pytype Variable."""
    f = self.vm.frame
    if not f:
      # Should not happen but does in some contrived test cases.
      return None
    for name, v in zip(f.f_code.co_freevars, f.cells):
      if v == var:
        return name
    return None

  def match_args(self, node, args, alias_map=None, match_all_views=False):
    """Check whether the given arguments can match the function signature."""
    for a in args.posargs:
      if not a.bindings:
        # The only way to get an unbound variable here is to reference a closure
        # cellvar before it is assigned to in the outer scope.
        name = self._get_cell_variable_name(a)
        assert name is not None, "Closure variable lookup failed."
        raise function.UndefinedParameterError(name)
    error = None
    matched = []
    arg_variables = args.get_variables()
    views = abstract_utils.get_views(arg_variables, node)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      log.debug("args in view: %r", [(a.bindings and view[a].data)
                                     for a in args.posargs])
      for arg in arg_variables:
        if abstract_utils.has_type_parameters(node, view[arg].data):
          self.vm.errorlog.invalid_typevar(
              self.vm.frames, "cannot pass a TypeVar to a function")
          view[arg] = arg.AddBinding(self.vm.convert.unsolvable, [], node)
      try:
        match = self._match_view(node, args, view, alias_map)
      except function.FailedFunctionCall as e:
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

  def set_function_defaults(self, node, defaults_var):
    raise NotImplementedError(self.__class__.__name__)


class ClassMethod(AtomicAbstractValue):
  """Implements @classmethod methods in pyi."""

  def __init__(self, name, method, callself, vm):
    super().__init__(name, vm)
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
    super().__init__(name, vm)
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
    super().__init__(name, vm)
    self.method = method
    self._callself = callself
    self.signatures = self.method.signatures

  def call(self, node, func, args, alias_map=None):
    func = func or self.to_binding(node)
    args = args or function.Args(posargs=(self._callself,))
    return self.method.call(node, func, args.replace(posargs=(self._callself,)))

  def get_class(self):
    return self.vm.convert.function_type


class PyTDFunction(Function):
  """A PyTD function (name + list of signatures).

  This represents (potentially overloaded) functions.
  """

  @classmethod
  def make(cls, name, vm, module, pyval=None, pyval_name=None):
    """Create a PyTDFunction.

    Args:
      name: The function name.
      vm: The VM.
      module: The module that the function is in.
      pyval: Optionally, the pytd.Function object to use. Otherwise, it is
        fetched from the loader.
      pyval_name: Optionally, the name of the pytd.Function object to look up,
        if it is different from the function name.

    Returns:
      A new PyTDFunction.
    """
    assert not pyval or not pyval_name  # there's never a reason to pass both
    if not pyval:
      pyval_name = module + "." + (pyval_name or name)
      if module not in ("__builtin__", "typing"):
        pyval = vm.loader.import_name(module).Lookup(pyval_name)
      else:
        pyval = vm.lookup_builtin(pyval_name)
    if (isinstance(pyval, pytd.Alias)
        and isinstance(pyval.type, pytd.FunctionType)):
      pyval = pyval.type.function
    f = vm.convert.constant_to_value(pyval, {}, vm.root_cfg_node)
    self = cls(name, f.signatures, pyval.kind, vm)
    self.module = module
    return self

  def __init__(self, name, signatures, kind, vm):
    super().__init__(name, vm)
    assert signatures
    self.kind = kind
    self.bound_class = BoundPyTDFunction
    self.signatures = signatures
    self._signature_cache = {}
    self._return_types = {sig.pytd_sig.return_type for sig in signatures}
    for sig in signatures:
      for param in sig.pytd_sig.params:
        if param.mutated_type is not None:
          self._has_mutable = True
          break
      else:
        self._has_mutable = False
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
        callself = abstract_utils.get_atomic_value(
            callself, default=self.vm.convert.unsolvable)
        if isinstance(callself, TypeParameterInstance):
          callself = abstract_utils.get_atomic_value(
              callself.instance.get_instance_type_parameter(callself.name),
              default=self.vm.convert.unsolvable)
        # callself is the instance, and we want to bind to its class.
        callself = callself.get_class().to_variable(self.vm.root_cfg_node)
      return ClassMethod(self.name, self, callself, self.vm)
    elif self.kind == pytd.PROPERTY and not is_class:
      return Property(self.name, self, callself, self.vm)
    else:
      return super().property_get(callself, is_class)

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
    # TODO(b/159052609): We should be passing function signatures to simplify.
    args = args.simplify(node, self.vm)
    self._log_args(arg.bindings for arg in args.posargs)
    ret_map = {}
    retvar = self.vm.program.NewVariable()
    all_mutations = set()
    # The following line may raise function.FailedFunctionCall
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

    # Don't check container types if the function has multiple bindings.
    # This is a hack to prevent false positives when we call a method on a
    # variable with multiple bindings, since we don't always filter rigorously
    # enough in get_views.
    # See tests/py3/test_annotations:test_list for an example that would break
    # if we removed the len(bindings) check.
    if all_mutations and self.vm.options.check_container_types and (
        len(func.variable.Bindings(node)) == 1):
      # Raise an error if:
      # - An annotation has a type param that is not ambigious or empty
      # - The mutation adds a type that is not ambiguous or empty
      def filter_contents(var):
        # reduces the work compatible_with has to do.
        return set(x for x in var.data
                   if not x.isinstance_AMBIGUOUS_OR_EMPTY())

      def compatible_with(existing, new):
        """Check whether a new type can be added to a container."""
        for data in existing:
          if self.vm.matcher.match_from_mro(new.cls, data.cls):
            return True
        return False

      filtered_mutations = []
      errors = collections.defaultdict(dict)

      for obj, name, values in all_mutations:
        if obj.from_annotation:
          params = obj.get_instance_type_parameter(name)
          ps = filter_contents(params)
          if ps:
            # We filter out mutations to parameters with type Any.
            filtered_mutations.append((obj, name, values))
            # check if the container type is being broadened.
            vs = filter_contents(values)
            new = [x for x in (vs - ps) if not compatible_with(ps, x)]
            if new:
              formal = name.split(".")[-1]
              errors[obj][formal] = (params, values, obj.from_annotation)
        else:
          filtered_mutations.append((obj, name, values))

      all_mutations = filtered_mutations

      for obj, errs in errors.items():
        names = {name for _, _, name in errs.values()}
        name = list(names)[0] if len(names) == 1 else None
        self.vm.errorlog.container_type_mismatch(
            self.vm.frames, obj, errs, name)

    node = abstract_utils.apply_mutations(node, all_mutations.__iter__)
    return node, retvar

  def _get_mutation_to_unknown(self, node, values):
    """Mutation for making all type parameters in a list of instances "unknown".

    This is used if we call a function that has mutable parameters and
    multiple signatures with unknown parameters.

    Args:
      node: The current CFG node.
      values: A list of instances of AtomicAbstractValue.

    Returns:
      A list of function.Mutation instances.
    """
    mutations = []
    for v in values:
      if isinstance(v, SimpleAbstractValue):
        for name in v.instance_type_parameters:
          mutations.append(
              function.Mutation(v, name, self.vm.convert.create_new_unknown(
                  node, action="type_param_" + name)))
    return mutations

  def _can_match_multiple(self, args, view):
    # If we're calling an overloaded pytd function with an unknown as a
    # parameter, we can't tell whether it matched or not. Hence, if multiple
    # signatures are possible matches, we don't know which got called. Check
    # if this is the case.
    if len(self.signatures) <= 1:
      return False
    if any(isinstance(view[arg].data, AMBIGUOUS_OR_EMPTY)
           for arg in args.get_variables()):
      return True
    for arg in (args.starargs, args.starstarargs):
      # An opaque *args or **kwargs behaves like an unknown.
      if arg and not isinstance(arg, mixin.PythonConstant):
        return True
    return False

  def _match_view(self, node, args, view, alias_map=None):
    if self._can_match_multiple(args, view):
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
      log.debug("Unknown args. But return is %s", pytd_utils.Print(ret_type))
      result = self.vm.convert.constant_to_var(
          abstract_utils.AsReturnValue(ret_type), {}, node)
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
      # TODO(b/159055015): We only need to whack the type params that appear in
      # a mutable parameter.
      mutations = self._get_mutation_to_unknown(
          node, (view[p].data for p in itertools.chain(
              args.posargs, args.namedargs.values())))
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
    # Once a constant has matched a literal type, it should no longer be able to
    # match non-literal types. For example, with:
    #   @overload
    #   def f(x: Literal['r']): ...
    #   @overload
    #   def f(x: str): ...
    # f('r') should match only the first signature.
    literal_matches = set()
    for sig in self.signatures:
      if any(not abstract_utils.is_literal(sig.signature.annotations.get(name))
             for name in literal_matches):
        continue
      try:
        arg_dict, subst = sig.substitute_formal_args(
            node, args, view, alias_map)
      except function.FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        matched = True
        for name, binding in arg_dict.items():
          if (isinstance(binding.data, mixin.PythonConstant) and
              abstract_utils.is_literal(sig.signature.annotations.get(name))):
            literal_matches.add(name)
        yield sig, arg_dict, subst
    if not matched:
      raise error  # pylint: disable=raising-bad-type

  def set_function_defaults(self, unused_node, defaults_var):
    """Attempts to set default arguments for a function's signatures.

    If defaults_var is not an unambiguous tuple (i.e. one that can be processed
    by abstract_utils.get_atomic_python_constant), every argument is made
    optional and a warning is issued. This function emulates __defaults__.

    If this function is part of a class (or has a parent), that parent is
    updated so the change is stored.

    Args:
      unused_node: the node that defaults are being set at. Not used here.
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


class ParameterizedClass(
    AtomicAbstractValue, mixin.Class, mixin.NestedAnnotation):
  """A class that contains additional parameters. E.g. a container.

  Attributes:
    cls: A PyTDClass representing the base type.
    formal_type_parameters: An iterable of AtomicAbstractValue, one for each
        type parameter.
  """

  def get_self_annot(self):
    """This is used to annotate the `self` in a class."""
    if not self.self_annot:
      formal_type_parameters = {}
      for item in self.base_cls.template:
        formal_type_parameters[item.name] = item
      self.self_annot = ParameterizedClass(
          self.base_cls, formal_type_parameters, self.vm)
    return self.self_annot

  def __init__(self, base_cls, formal_type_parameters, vm, template=None):
    # A ParameterizedClass is created by converting a pytd.GenericType, whose
    # base type is restricted to NamedType and ClassType.
    assert isinstance(base_cls, mixin.Class)
    self.base_cls = base_cls
    super().__init__(base_cls.name, vm)
    self.module = base_cls.module
    # Lazily loaded to handle recursive types.
    # See the formal_type_parameters() property.
    self._formal_type_parameters = formal_type_parameters
    self._formal_type_parameters_loaded = False
    self._hash = None  # memoized due to expensive computation
    self.official_name = self.base_cls.official_name
    if template is None:
      self._template = self.base_cls.template
    else:
      # The ability to create a new template different from the base class's is
      # needed for typing.Generic.
      self._template = template
    self.slots = self.base_cls.slots
    self.self_annot = None
    mixin.Class.init_mixin(self, base_cls.cls)
    mixin.NestedAnnotation.init_mixin(self)
    self.type_param_check()

  def __repr__(self):
    return "ParameterizedClass(cls=%r params=%s)" % (
        self.base_cls,
        self.formal_type_parameters)

  def type_param_check(self):
    """Throw exception for invalid type parameters."""
    # It will cause infinite recursion if `formal_type_parameters` is
    # `LazyFormalTypeParameters`
    if not isinstance(self._formal_type_parameters,
                      abstract_utils.LazyFormalTypeParameters):
      tparams = datatypes.AliasingMonitorDict()
      abstract_utils.parse_formal_type_parameters(self, None, tparams)

  def get_formal_type_parameters(self):
    return {abstract_utils.full_type_name(self, k): v
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
      if isinstance(self._formal_type_parameters,
                    abstract_utils.LazyFormalTypeParameters):
        items = tuple(self._raw_formal_type_parameters())
      else:
        # Use the names of the parameter values to approximate a hash, to avoid
        # infinite recursion on recursive type annotations.
        items = tuple((name, val.full_name)
                      for name, val in self.formal_type_parameters.items())
      self._hash = hash((self.base_cls, items))
    return self._hash

  def __contains__(self, name):
    return name in self.base_cls

  def _raw_formal_type_parameters(self):
    assert isinstance(self._formal_type_parameters,
                      abstract_utils.LazyFormalTypeParameters)
    template, parameters, _ = self._formal_type_parameters
    for i, name in enumerate(template):
      # TODO(rechen): A missing parameter should be an error.
      yield name, parameters[i] if i < len(parameters) else None

  def get_own_methods(self):
    return self.base_cls.get_own_methods()

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
    if isinstance(self._formal_type_parameters,
                  abstract_utils.LazyFormalTypeParameters):
      formal_type_parameters = {}
      for name, param in self._raw_formal_type_parameters():
        if param is None:
          formal_type_parameters[name] = self.vm.convert.unsolvable
        else:
          formal_type_parameters[name] = self.vm.convert.constant_to_value(
              param, self._formal_type_parameters.subst, self.vm.root_cfg_node)
      self._formal_type_parameters = formal_type_parameters
    # Hack: we'd like to evaluate annotations at the currently active node so
    # that imports, etc., are visible. The last created node is usually the
    # active one.
    self._formal_type_parameters = (
        self.vm.annotations_util.convert_class_annotations(
            self.vm.program.cfg_nodes[-1], self._formal_type_parameters))
    self._formal_type_parameters_loaded = True

  def compute_mro(self):
    return (self,) + self.base_cls.mro[1:]

  def instantiate(self, node, container=None):
    if self.full_name == "__builtin__.type":
      # deformalize removes TypeVars.
      # See py3.test_typevar.TypeVarTest.testTypeParameterType(Error).
      instance = self.vm.annotations_util.deformalize(
          self.formal_type_parameters[abstract_utils.T])
      return instance.to_variable(node)
    elif self.full_name == "typing.ClassVar":
      return self.formal_type_parameters[abstract_utils.T].instantiate(
          node, container)
    elif self.vm.frame and self.vm.frame.current_opcode:
      return self._new_instance().to_variable(node)
    else:
      return super().instantiate(node, container)

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
      raise function.NotCallable(self)
    else:
      return mixin.Class.call(self, node, func, args)

  def get_formal_type_parameter(self, t):
    return self.formal_type_parameters.get(t, self.vm.convert.unsolvable)

  def get_inner_types(self):
    return self.formal_type_parameters.items()

  def update_inner_type(self, key, typ):
    self.formal_type_parameters[key] = typ

  def replace(self, inner_types):
    inner_types = dict(inner_types)
    if isinstance(self, LiteralClass):
      if inner_types == self.formal_type_parameters:
        # If the type hasn't changed, we can return a copy of this class.
        return LiteralClass(self._instance, self.vm, self.template)
      # Otherwise, we can't create a LiteralClass because we don't have a
      # concrete value.
      typ = ParameterizedClass
    else:
      typ = self.__class__
    return typ(self.base_cls, inner_types, self.vm, self.template)


class TupleClass(ParameterizedClass, mixin.HasSlots):
  """The class of a heterogeneous tuple.

  The formal_type_parameters attribute stores the types of the individual tuple
  elements under their indices and the overall element type under "T". So for
    Tuple[str, int]
  formal_type_parameters is
    {0: str, 1: int, T: str or int}.
  Note that we can't store the individual types as a mixin.PythonConstant as we
  do for Tuple, since we can't evaluate type parameters during initialization.
  """

  def __init__(self, base_cls, formal_type_parameters, vm, template=None):
    super().__init__(base_cls, formal_type_parameters, vm, template)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    if isinstance(self._formal_type_parameters,
                  abstract_utils.LazyFormalTypeParameters):
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
    return {abstract_utils.full_type_name(self, abstract_utils.T):
            self.formal_type_parameters[abstract_utils.T]}

  def instantiate(self, node, container=None):
    if self._instance:
      return self._instance.to_variable(node)
    content = []
    for i in range(self.tuple_length):
      p = self.formal_type_parameters[i]
      if container is abstract_utils.DUMMY_CONTAINER or (
          isinstance(container, SimpleAbstractValue) and
          isinstance(p, TypeParameter) and
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
          abstract_utils.get_atomic_value(index_var), (int, slice))
    except abstract_utils.ConversionError:
      pass
    else:
      if isinstance(index, slice):
        if self._instance:
          slice_content = self._instance.pyval[index]
          return node, self.vm.convert.build_tuple(node, slice_content)
        else:
          # Constructing the tuple directly is faster than calling call_pytd.
          instance = Instance(self.vm.convert.tuple_type, self.vm)
          node, contained_type = self.vm.init_class(
              node, self.formal_type_parameters[abstract_utils.T])
          instance.merge_instance_type_parameter(
              node, abstract_utils.T, contained_type)
          return node, instance.to_variable(node)
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
    if (valself and not abstract_utils.equivalent_to(valself, self) and
        name in self._slots):
      return mixin.HasSlots.get_special_attribute(self, node, name, valself)
    return super().get_special_attribute(node, name, valself)


class CallableClass(ParameterizedClass, mixin.HasSlots):
  """A Callable with a list of argument types.

  The formal_type_parameters attribute stores the types of the individual
  arguments under their indices, the overall argument type under "ARGS", and the
  return type under "RET". So for
    CallableClass[[int, bool], str]
  formal_type_parameters is
    {0: int, 1: bool, ARGS: int or bool, RET: str}
  When there are no args (CallableClass[[], ...]), ARGS contains abstract.Empty.
  """

  def __init__(self, base_cls, formal_type_parameters, vm, template=None):
    super().__init__(base_cls, formal_type_parameters, vm, template)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__call__", self.call_slot)
    # We subtract two to account for "ARGS" and "RET".
    self.num_args = len(self.formal_type_parameters) - 2

  def __repr__(self):
    return "CallableClass(%s)" % self.formal_type_parameters

  def get_formal_type_parameters(self):
    return {
        abstract_utils.full_type_name(self, abstract_utils.ARGS): (
            self.formal_type_parameters[abstract_utils.ARGS]),
        abstract_utils.full_type_name(self, abstract_utils.RET): (
            self.formal_type_parameters[abstract_utils.RET])}

  def call_slot(self, node, *args, **kwargs):
    """Implementation of CallableClass.__call__."""
    if kwargs:
      raise function.WrongKeywordArgs(
          function.Signature.from_callable(self),
          function.Args(posargs=args, namedargs=kwargs), self.vm, kwargs.keys())
    if len(args) != self.num_args:
      raise function.WrongArgCount(function.Signature.from_callable(self),
                                   function.Args(posargs=args), self.vm)
    formal_args = [(function.argname(i), self.formal_type_parameters[i])
                   for i in range(self.num_args)]
    substs = [datatypes.AliasingDict()]
    bad_param = None
    for view in abstract_utils.get_views(args, node):
      arg_dict = {function.argname(i): view[args[i]]
                  for i in range(self.num_args)}
      subst, bad_param = self.vm.matcher.compute_subst(
          node, formal_args, arg_dict, view, None)
      if subst is not None:
        substs = [subst]
        break
    else:
      if bad_param:
        raise function.WrongArgTypes(
            function.Signature.from_callable(self), function.Args(posargs=args),
            self.vm, bad_param=bad_param)
    ret = self.vm.annotations_util.sub_one_annotation(
        node, self.formal_type_parameters[abstract_utils.RET], substs)
    node, retvar = self.vm.init_class(node, ret)
    return node, retvar

  def get_special_attribute(self, node, name, valself):
    if (valself and not abstract_utils.equivalent_to(valself, self) and
        name in self._slots):
      return mixin.HasSlots.get_special_attribute(self, node, name, valself)
    return super().get_special_attribute(node, name, valself)


class LiteralClass(ParameterizedClass):
  """The class of a typing.Literal."""

  def __init__(self, instance, vm, template=None):
    base_cls = vm.convert.name_to_value("typing.Literal")
    formal_type_parameters = {abstract_utils.T: instance.get_class()}
    super().__init__(base_cls, formal_type_parameters, vm, template)
    self._instance = instance

  def __repr__(self):
    return "LiteralClass(%s)" % self._instance

  def __eq__(self, other):
    if isinstance(other, LiteralClass):
      if self.value and other.value:
        return self.value.pyval == other.value.pyval
    return super().__eq__(other)

  def __hash__(self):
    return hash((super().__hash__(), self._instance))

  @property
  def value(self):
    if isinstance(self._instance, AbstractOrConcreteValue):
      return self._instance
    # TODO(b/123775699): Remove this workaround once we support literal enums.
    return None

  def instantiate(self, node, container=None):
    return self._instance.to_variable(node)


class PyTDClass(SimpleAbstractValue, mixin.Class, mixin.LazyMembers):
  """An abstract wrapper for PyTD class objects.

  These are the abstract values for class objects that are described in PyTD.

  Attributes:
    cls: A pytd.Class
    mro: Method resolution order. An iterable of AtomicAbstractValue.
  """

  def __init__(self, name, pytd_cls, vm):
    self.pytd_cls = pytd_cls
    super().__init__(name, vm)
    mm = {}
    for val in pytd_cls.constants + pytd_cls.methods:
      mm[val.name] = val
    for val in pytd_cls.classes:
      mm[val.name.rsplit(".", 1)[-1]] = val
    if pytd_cls.metaclass is None:
      metaclass = None
    else:
      metaclass = self.vm.convert.constant_to_value(
          pytd_cls.metaclass, subst=datatypes.AliasingDict(),
          node=self.vm.root_cfg_node)
    self.official_name = self.name
    self.slots = pytd_cls.slots
    mixin.LazyMembers.init_mixin(self, mm)
    self.is_dynamic = self.compute_is_dynamic()
    mixin.Class.init_mixin(self, metaclass)

  def get_own_methods(self):
    return {name for name, member in self._member_map.items()
            if isinstance(member, pytd.Function)}

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
      super().load_lazy_attribute(name)
    except self.vm.convert.TypeParameterError as e:
      self.vm.errorlog.unbound_type_param(
          self.vm.frames, self, name, e.type_param_name)
      self.members[name] = self.vm.new_unsolvable(
          self.vm.root_cfg_node)

  def _convert_member(self, pyval, subst=None):
    """Convert a member as a variable. For lazy lookup."""
    subst = subst or datatypes.AliasingDict()
    node = self.vm.root_cfg_node
    if isinstance(pyval, pytd.Constant):
      return self.vm.convert.constant_to_var(
          abstract_utils.AsInstance(pyval.type), subst, node)
    elif isinstance(pyval, pytd.Function):
      c = self.vm.convert.constant_to_value(pyval, subst=subst, node=node)
      c.parent = self
      return c.to_variable(node)
    elif isinstance(pyval, pytd.Class):
      return self.vm.convert.constant_to_var(pyval, subst=subst, node=node)
    else:
      raise AssertionError("Invalid class member %s" % pytd_utils.Print(pyval))

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
    return self.vm.convert.constant_to_var(
        abstract_utils.AsInstance(self.pytd_cls), {}, node)

  def __repr__(self):
    return "PyTDClass(%s)" % self.name

  def __contains__(self, name):
    return name in self._member_map

  def convert_as_instance_attribute(self, name, instance):
    """Convert `name` as an instance attribute.

    This method is used by attribute.py to lazily load attributes on instances
    of this PyTDClass. Calling this method directly should be avoided. Doing so
    will create multiple copies of the same attribute, leading to subtle bugs.

    Args:
      name: The attribute name.
      instance: An instance of this PyTDClass.

    Returns:
      The converted attribute.
    """
    try:
      c = self.pytd_cls.Lookup(name)
    except KeyError:
      return None
    if isinstance(c, pytd.Constant):
      try:
        self._convert_member(c)
      except self.vm.convert.TypeParameterError:
        # Constant c cannot be converted without type parameter substitutions,
        # so it must be an instance attribute.
        subst = datatypes.AliasingDict()
        for itm in self.pytd_cls.template:
          subst[itm.full_name] = self.vm.convert.constant_to_value(
              itm.type_param, {}).instantiate(
                  self.vm.root_cfg_node, container=instance)
        return self._convert_member(c, subst)

  def generate_ast(self):
    """Generate this class's AST, including updated members."""
    return pytd.Class(
        name=self.name,
        metaclass=self.pytd_cls.metaclass,
        parents=self.pytd_cls.parents,
        methods=tuple(self._member_map[m.name] for m in self.pytd_cls.methods),
        constants=self.pytd_cls.constants,
        classes=self.pytd_cls.classes,
        decorators=self.pytd_cls.decorators,
        slots=self.pytd_cls.slots,
        template=self.pytd_cls.template)


class FunctionPyTDClass(PyTDClass):
  """PyTDClass(Callable) subclass to support annotating higher-order functions.

  In InterpreterFunction calls, type parameter annotations are handled by
  getting the types of the parameters from the arguments and instantiating them
  in the return value. To handle a signature like (func: T) -> T, we need to
  save the value of `func`, not just its type of Callable.
  """

  def __init__(self, func, vm):
    super().__init__("typing.Callable", vm.convert.function_type.pytd_cls, vm)
    self.func = func

  def instantiate(self, node, container=None):
    del container  # unused
    return self.func.to_variable(node)


class InterpreterClass(SimpleAbstractValue, mixin.Class):
  """An abstract wrapper for user-defined class objects.

  These are the abstract value for class objects that are implemented in the
  program.
  """

  def __init__(self, name, bases, members, cls, vm):
    assert isinstance(name, str)
    assert isinstance(bases, list)
    assert isinstance(members, dict)
    self._bases = bases
    super().__init__(name, vm)
    self.members = datatypes.MonitorDict(members)
    mixin.Class.init_mixin(self, cls)
    self.instances = set()  # filled through register_instance
    self.slots = self._convert_slots(members.get("__slots__"))
    self.is_dynamic = self.compute_is_dynamic()
    log.info("Created class: %r", self)
    self.type_param_check()

  def type_param_check(self):
    """Throw exception for invalid type parameters."""

    def update_sig(method):
      method.signature.excluded_types.update(
          [t.name for t in self.template])
      method.signature.add_scope(self.full_name)

    if self.template:
      # For function type parameters check
      for mbr in self.members.values():
        m = abstract_utils.get_atomic_value(
            mbr, default=self.vm.convert.unsolvable)
        if isinstance(m, InterpreterFunction):
          update_sig(m)
        elif mbr.data and all(
            x.__class__.__name__ == "PropertyInstance" for x in mbr.data):
          # We generate a new variable every time we add a property slot, so we
          # take the last one (which contains bindings for all defined slots).
          prop = mbr.data[-1]
          for slot in (prop.fget, prop.fset, prop.fdel):
            if slot:
              for d in slot.data:
                if isinstance(d, InterpreterFunction):
                  update_sig(d)

      # nested class can not use the same type parameter
      # in current generic class
      inner_cls_types = self.collect_inner_cls_types()
      for cls, item in inner_cls_types:
        nitem = item.with_module(self.full_name)
        if nitem in self.template:
          raise abstract_utils.GenericTypeError(
              self, ("Generic class [%s] and its nested generic class [%s] "
                     "cannot use the same type variable %s.")
              % (self.full_name, cls.full_name, item.name))

    self._load_all_formal_type_parameters()  # Throw exception if there is error
    for t in self.template:
      if t.full_name in self.all_formal_type_parameters:
        raise abstract_utils.GenericTypeError(
            self, "Conflicting value for TypeVar %s" % t.full_name)

  def collect_inner_cls_types(self, max_depth=5):
    """Collect all the type parameters from nested classes."""
    templates = set()
    if max_depth > 0:
      for mbr in self.members.values():
        mbr = abstract_utils.get_atomic_value(
            mbr, default=self.vm.convert.unsolvable)
        if isinstance(mbr, InterpreterClass) and mbr.template:
          templates.update([(mbr, item.with_module(None))
                            for item in mbr.template])
          templates.update(mbr.collect_inner_cls_types(max_depth - 1))
    return templates

  def get_inner_classes(self):
    """Return the list of top-level nested classes."""
    values = [
        abstract_utils.get_atomic_value(mbr, default=self.vm.convert.unsolvable)
        for mbr in self.members.values()]
    return [x for x in values if isinstance(x, InterpreterClass)]

  def get_own_methods(self):
    def _can_be_function(var):
      return any(isinstance(v, FUNCTION_TYPES) or
                 v.isinstance_ClassMethodInstance() or
                 v.isinstance_StaticMethodInstance() for v in var.data)
    return {name for name, var in self.members.items() if _can_be_function(var)}

  def get_own_abstract_methods(self):
    def _can_be_abstract(var):
      return any((isinstance(v, Function) or v.isinstance_PropertyInstance())
                 and v.is_abstract for v in var.data)
    return {name for name, var in self.members.items() if _can_be_abstract(var)}

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
    if isinstance(val, mixin.PythonConstant):
      if isinstance(val.pyval, (list, tuple)):
        entries = val.pyval
      else:
        return None  # Happens e.g. __slots__ = {"foo", "bar"}. Not an error.
    else:
      return None  # Happens e.g. for __slots__ = dir(Foo)
    try:
      strings = [abstract_utils.get_atomic_python_constant(v) for v in entries]
    except abstract_utils.ConversionError:
      return None  # Happens e.g. for __slots__ = ["x" if b else "y"]
    for s in strings:
      # The identity check filters out compat.py subclasses.
      if s.__class__ is str:
        continue
      elif s.__class__ is compat.UnicodeType:
        # Unicode values should be ASCII.
        try:
          s = s.encode("ascii")
        except (UnicodeDecodeError, UnicodeEncodeError):
          pass
        else:
          continue
      if isinstance(s, str):
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
      return self.vm.convert.merge_classes([self])
    else:
      return None

  def instantiate(self, node, container=None):
    if self.vm.frame and self.vm.frame.current_opcode:
      return self._new_instance().to_variable(node)
    else:
      # When the analyze_x methods in CallTracer instantiate classes in
      # preparation for analysis, often there is no frame on the stack yet, or
      # the frame is a SimpleFrame with no opcode.
      return super().instantiate(node, container)

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
    super().__init__(name, vm)
    self.func = func
    self.bound_class = lambda callself, underlying: self

  def argcount(self, _):
    return self.func.func_code.co_argcount

  def call(self, node, _, args, alias_map=None):
    args = args.simplify(node, self.vm)
    posargs = [u.AssignToNewVariable(node) for u in args.posargs]
    namedargs = {k: u.AssignToNewVariable(node)
                 for k, u in args.namedargs.items()}
    try:
      inspect.signature(self.func).bind(node, *posargs, **namedargs)
    except ValueError as e:
      # Happens for, e.g.,
      #   def f((x, y)): pass
      #   f((42,))
      raise NotImplementedError("Wrong number of values to unpack") from e
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
        raise NotImplementedError("Unexpected keyword") from e
      # The function was passed the wrong number of arguments. The signature is
      # ([self, ]node, ...). The length of "..." tells us how many variables
      # are expected.
      expected_argcount = len(inspect.getfullargspec(self.func).args) - 1
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
        raise function.WrongArgCount(sig, args, self.vm)
      assert actual_argcount < expected_argcount
      # Assume that starargs or starstarargs fills in the missing arguments.
      # Instead of guessing where these arguments should go, overwrite all of
      # the arguments with a list of unsolvables of the correct length, which
      # is guaranteed to give us a correct (but imprecise) analysis.
      posargs = [self.vm.new_unsolvable(node)
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
    super().__init__(signature.name, vm)
    self.signature = signature
    # Track whether we've annotated `self` with `set_self_annot`, since
    # annotating `self` in `__init__` is otherwise illegal.
    self._has_self_annot = False

  @contextlib.contextmanager
  def set_self_annot(self, annot_class):
    """Set the annotation for `self` in a class."""
    self_name = self.signature.param_names[0]
    old_self = self.signature.annotations.get(self_name)
    old_has_self_annot = self._has_self_annot
    self.signature.annotations[self_name] = annot_class
    self._has_self_annot = True
    try:
      yield
    finally:
      if old_self:
        self.signature.annotations[self_name] = old_self
      else:
        del self.signature.annotations[self_name]
      self._has_self_annot = old_has_self_annot

  def argcount(self, _):
    return len(self.signature.param_names)

  def get_nondefault_params(self):
    return ((n, n in self.signature.kwonly_params)
            for n in self.signature.param_names
            if n not in self.signature.defaults)

  def match_and_map_args(self, node, args, alias_map):
    """Calls match_args() and _map_args()."""
    return self.match_args(node, args, alias_map), self._map_args(node, args)

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
      function.FailedFunctionCall: If the caller supplied incorrect arguments.
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
        raise function.DuplicateKeyword(sig, args, self.vm, key)
    extra_kws = set(kws).difference(sig.param_names + sig.kwonly_params)
    if extra_kws and not sig.kwargs_name:
      raise function.WrongKeywordArgs(sig, args, self.vm, extra_kws)
    callargs.update(positional)
    callargs.update(kws)
    for key, kwonly in self.get_nondefault_params():
      if key not in callargs:
        if args.starstarargs or (args.starargs and not kwonly):
          # We assume that because we have *args or **kwargs, we can use these
          # to fill in any parameters we might be missing.
          callargs[key] = self.vm.new_unsolvable(node)
        else:
          raise function.MissingParameter(sig, args, self.vm, key)
    for key in sig.kwonly_params:
      if key not in callargs:
        raise function.MissingParameter(sig, args, self.vm, key)
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
      raise function.WrongArgCount(sig, args, self.vm)
    if sig.kwargs_name:
      kwargs_name = sig.kwargs_name
      # Build a **kwargs dictionary out of the extraneous parameters
      if args.starstarargs:
        callargs[kwargs_name] = args.starstarargs.AssignToNewVariable(node)
      else:
        omit = sig.param_names + sig.kwonly_params
        k = Dict(self.vm)
        k.update(node, args.namedargs, omit=omit)
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
      raise function.WrongArgTypes(
          self.signature, args, self.vm, bad_param=bad_arg)
    return subst

  def get_first_opcode(self):
    return None

  def set_function_defaults(self, node, defaults_var):
    """Attempts to set default arguments of a function.

    If defaults_var is not an unambiguous tuple (i.e. one that can be processed
    by abstract_utils.get_atomic_python_constant), every argument is made
    optional and a warning is issued. This function emulates __defaults__.

    Args:
      node: The node where default arguments are being set. Needed if we cannot
            get a useful value from defaults_var.
      defaults_var: a Variable with a single binding to a tuple of default
                    values.
    """
    defaults = self._extract_defaults(defaults_var)
    if defaults is None:
      defaults = [self.vm.new_unsolvable(node)
                  for _ in self.signature.param_names]
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

  @classmethod
  def make(cls, name, code, f_locals, f_globals, defaults, kw_defaults, closure,
           annotations, vm):
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
      vm: VirtualMachine instance.

    Returns:
      An InterpreterFunction.
    """
    annotations = annotations or {}
    if "return" in annotations:
      # Check Generator/AsyncGenerator return type
      ret_type = annotations["return"]
      if code.has_generator():
        if not abstract_utils.matches_generator(ret_type):
          error = "Expected Generator, Iterable or Iterator"
          vm.errorlog.invalid_annotation(vm.frames, ret_type, error)
      elif code.has_async_generator():
        if not abstract_utils.matches_async_generator(ret_type):
          error = "Expected AsyncGenerator, AsyncIterable or AsyncIterator"
          vm.errorlog.invalid_annotation(vm.frames, ret_type, error)
    overloads = vm.frame.overloads[name]
    key = (name, code,
           abstract_utils.hash_all_dicts(
               (f_globals.members, set(code.co_names)),
               (f_locals.members,
                set(f_locals.members) - set(code.co_varnames)),
               ({key: vm.program.NewVariable([value], [], vm.root_cfg_node)
                 for key, value in annotations.items()}, None),
               (dict(enumerate(vm.program.NewVariable([f], [], vm.root_cfg_node)
                               for f in overloads)), None),
               (dict(enumerate(defaults)), None),
               (dict(enumerate(closure or ())), None)))
    if key not in cls._function_cache:
      cls._function_cache[key] = cls(
          name, code, f_locals, f_globals, defaults, kw_defaults, closure,
          annotations, overloads, vm)
    return cls._function_cache[key]

  def __init__(self, name, code, f_locals, f_globals, defaults, kw_defaults,
               closure, annotations, overloads, vm):
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
    # TODO(b/78034005): Combine this and PyTDFunction.signatures into a single
    # way to handle multiple signatures that SignedFunction can also use.
    self._overloads = overloads
    self.has_overloads = bool(overloads)
    self.is_overload = False  # will be set by typing_overlay.Overload.call
    self.nonstararg_count = self.code.co_argcount
    if self.code.co_kwonlyargcount >= 0:  # This is usually -1 or 0 (fast call)
      self.nonstararg_count += self.code.co_kwonlyargcount
    signature = self._build_signature(name, annotations)
    super().__init__(signature, vm)
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

  def _build_signature(self, name, annotations):
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
        annotations)

  def get_first_opcode(self):
    return self.code.co_code[0]

  def argcount(self, _):
    return self.code.co_argcount

  def match_args(self, node, args, alias_map=None, match_all_views=False):
    if not self.signature.has_param_annotations:
      return
    return super().match_args(node, args, alias_map, match_all_views)

  def _inner_cls_check(self, last_frame):
    """Check if the function and its nested class use same type parameter."""
    # get all type parameters from function annotations
    all_type_parameters = []
    for annot in self.signature.annotations.values():
      params = self.vm.annotations_util.get_type_parameters(annot)
      all_type_parameters.extend(itm.with_module(None) for itm in params)

    if all_type_parameters:
      for key, value in last_frame.f_locals.pyval.items():
        value = abstract_utils.get_atomic_value(
            value, default=self.vm.convert.unsolvable)
        if (not self.signature.has_param(key)  # skip the argument list
            and isinstance(value, InterpreterClass) and value.template):
          inner_cls_types = value.collect_inner_cls_types()
          inner_cls_types.update([(value, item.with_module(None))
                                  for item in value.template])
          # Report errors in a deterministic order.
          for cls, item in sorted(inner_cls_types, key=lambda typ: typ[1].name):
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
        inst = abstract_utils.get_atomic_value(first_posarg, Instance)
      except abstract_utils.ConversionError:
        return
      if inst.cls.template:
        for subst in substs:
          for k, v in subst.items():
            if k in inst.instance_type_parameters:
              value = inst.instance_type_parameters[k].AssignToNewVariable(node)
              value.PasteVariable(v, node)
              yield function.Mutation(inst, k, value)
    # Optimization: return a generator to avoid iterating over the mutations an
    # extra time.
    return generator

  def signature_functions(self):
    """Get the functions that describe this function's signature."""
    return self._overloads or [self]

  def iter_signature_functions(self):
    """Loop through signatures, setting each as the primary one in turn."""
    if not self._overloads:
      yield self
      return
    for f in self._overloads:
      old_overloads = self._overloads
      self._overloads = [f]
      try:
        yield f
      finally:
        self._overloads = old_overloads

  def _find_matching_sig(self, node, args, alias_map):
    error = None
    for f in self.signature_functions():
      try:
        # match_args and _map_args both do some matching, so together they fully
        # type-check the arguments.
        substs, callargs = f.match_and_map_args(node, args, alias_map)
      except function.FailedFunctionCall as e:
        if e > error:
          error = e
      else:
        # We use the first matching overload.
        return f.signature, substs, callargs
    raise error  # pylint: disable=raising-bad-type

  def _set_callself_maybe_missing_members(self):
    if self.vm.callself_stack:
      for b in self.vm.callself_stack[-1].bindings:
        b.data.maybe_missing_members = True

  def call(self, node, func, args, new_locals=False, alias_map=None):
    if self.is_overload:
      raise function.NotCallable(self)
    if (self.vm.is_at_maximum_depth() and
        not abstract_utils.func_name_is_class_init(self.name)):
      log.info("Maximum depth reached. Not analyzing %r", self.name)
      self._set_callself_maybe_missing_members()
      return node, self.vm.new_unsolvable(node)
    args = args.simplify(node, self.vm, self.signature)
    sig, substs, callargs = self._find_matching_sig(node, args, alias_map)
    if sig is not self.signature:
      # We've matched an overload; remap the callargs using the implementation
      # so that optional parameters, etc, are correctly defined.
      callargs = self._map_args(node, args)
    first_posarg = args.posargs[0] if args.posargs else None
    # Keep type parameters without substitutions, as they may be needed for
    # type-checking down the road.
    annotations = self.vm.annotations_util.sub_annotations(
        node, sig.annotations, substs, instantiate_unbound=False)
    if sig.has_param_annotations:
      for name in callargs:
        if (name in annotations and (not self.is_attribute_of_class or
                                     self.argcount(node) == 0 or
                                     name != sig.param_names[0])):
          extra_key = (self.get_first_opcode(), name)
          node, callargs[name] = self.vm.annotations_util.init_annotation(
              node, name, annotations[name], extra_key=extra_key)
    try:
      frame = self.vm.make_frame(
          node, self.code, self.f_globals, self.f_locals, callargs,
          self.closure, new_locals=new_locals, func=func,
          first_posarg=first_posarg)
    except self.vm.VirtualMachineRecursionError:
      # If we've encountered recursion in a constructor, then we have another
      # incompletely initialized instance of the same class (or a subclass) at
      # the same node. (See, e.g., testRecursiveConstructor and
      # testRecursiveConstructorSubclass in test_classes.ClassesTest.) If we
      # allow the VirtualMachineRecursionError to be raised, initialization of
      # that first instance will be aborted. Instead, mark this second instance
      # as incomplete.
      self._set_callself_maybe_missing_members()
      return node, self.vm.new_unsolvable(node)
    self_var = sig.param_names and callargs.get(sig.param_names[0])
    caller_is_abstract = abstract_utils.check_classes(
        self_var, lambda cls: cls.is_abstract)
    caller_is_protocol = abstract_utils.check_classes(
        self_var, lambda cls: cls.is_protocol)
    # We should avoid checking the return value against any return annotation
    # when we are analyzing an attribute of a protocol or an abstract class's
    # abstract method.
    check_return = (not (self.is_attribute_of_class and caller_is_protocol) and
                    not (caller_is_abstract and self.is_abstract))
    if sig.has_return_annotation or not check_return:
      frame.allowed_returns = annotations.get(
          "return", self.vm.convert.unsolvable)
      frame.check_return = check_return
    if self.vm.options.skip_repeat_calls:
      callkey = abstract_utils.hash_all_dicts(
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
    if self.code.has_generator():
      generator = Generator(frame, self.vm)
      # Run the generator right now, even though the program didn't call it,
      # because we need to know the contained type for futher matching.
      node2, _ = generator.run_generator(node)
      if self.is_coroutine():
        # This function is a generator-based coroutine. We convert the return
        # value here even though byte_GET_AWAITABLE repeats the conversion so
        # that matching against a typing.Awaitable annotation succeeds.
        # TODO(rechen): PyTDFunction probably also needs to do this.
        var = generator.get_instance_type_parameter(abstract_utils.V)
        ret = Coroutine(self.vm, var, node2).to_variable(node2)
      else:
        ret = generator.to_variable(node2)
      node_after_call = node2
    elif self.code.has_async_generator():
      async_generator = AsyncGenerator(frame, self.vm)
      node2, _ = async_generator.run_generator(node)
      node_after_call, ret = node2, async_generator.to_variable(node2)
    else:
      if self.vm.options.check_parameter_types:
        annotated_locals = {
            name: abstract_utils.Local(node, self.get_first_opcode(), annot,
                                       callargs.get(name), self.vm)
            for name, annot in annotations.items() if name != "return"}
      else:
        annotated_locals = {}
      node2, ret = self.vm.run_frame(frame, node, annotated_locals)
      if self.is_coroutine():
        ret = Coroutine(self.vm, ret, node2).to_variable(node2)
      node_after_call = node2
    self._inner_cls_check(frame)
    mutations = self._mutations_generator(node_after_call, first_posarg, substs)
    node_after_call = abstract_utils.apply_mutations(node_after_call, mutations)
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
        ret = self.vm.new_unsolvable(node_after_call)
      for combination in combinations:
        for return_value in ret.bindings:
          values = list(combination.values()) + [return_value]
          data = tuple(v.data for v in values)
          if data in signature_data:
            # This combination yields a signature we already know is possible
            continue
          # Optimization: when only one combination exists, assume it's visible.
          if (len(combinations) == 1 and len(ret.bindings) == 1 or
              node_after_call.HasCombination(values)):
            signature_data.add(data)
            all_combinations.append(
                (node_after_call, combination, return_value))
    if not all_combinations:
      # Fallback: Generate signatures only from the definition of the
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
    return self.code.has_varargs()

  def has_kwargs(self):
    return self.code.has_varkeywords()

  def property_get(self, callself, is_class=False):
    if (abstract_utils.func_name_is_class_init(self.name) and
        self.signature.param_names):
      self_name = self.signature.param_names[0]
      # If `_has_self_annot` is True, then we've intentionally temporarily
      # annotated `self`; otherwise, a `self` annotation is illegal.
      if not self._has_self_annot and self_name in self.signature.annotations:
        self.vm.errorlog.invalid_annotation(
            self.vm.simple_stack(self.get_first_opcode()),
            self.signature.annotations[self_name],
            details="Cannot annotate self argument of __init__", name=self_name)
        self.signature.del_annotation(self_name)
    return super().property_get(callself, is_class)

  def is_coroutine(self):
    return self.code.has_coroutine() or self.code.has_iterable_coroutine()

  def has_empty_body(self):
    ops = self.code.co_code
    if len(ops) != 2:
      # This check isn't strictly necessary but prevents us from wastefully
      # building a list of opcode names for a long method.
      return False
    if [op.name for op in ops] != ["LOAD_CONST", "RETURN_VALUE"]:
      return False
    return self.code.co_consts[ops[0].arg] is None


class SimpleFunction(SignedFunction):
  """An abstract value representing a function with a particular signature.

  Unlike InterpreterFunction, a SimpleFunction has a set signature and does not
  record calls or try to infer types.
  """

  def __init__(self, name, param_names, varargs_name, kwonly_params,
               kwargs_name, defaults, annotations, vm):
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
      vm: The virtual machine for this function.
    """
    annotations = dict(annotations)
    # Every parameter must have an annotation. Defaults to unsolvable.
    for n in itertools.chain(param_names, [varargs_name, kwargs_name],
                             kwonly_params):
      if n and n not in annotations:
        annotations[n] = vm.convert.unsolvable
    if not isinstance(defaults, dict):
      defaults = dict(zip(param_names[-len(defaults):], defaults))
    signature = function.Signature(name, param_names, varargs_name,
                                   kwonly_params, kwargs_name, defaults,
                                   annotations)
    super().__init__(signature, vm)
    self.bound_class = BoundFunction

  def call(self, node, _, args, alias_map=None):
    # We only simplify args for _map_args, because that simplifies checking.
    # This allows match_args to typecheck varargs and kwargs.
    # We discard the results from _map_args, because SimpleFunction only cares
    # that the arguments are acceptable.
    self._map_args(node, args.simplify(node, self.vm))
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
    super().__init__(underlying.name, underlying.vm)
    self._callself = callself
    self.underlying = underlying
    self.is_attribute_of_class = False

    # If the function belongs to `ParameterizedClass`, we will annotate the
    # `self` when do argument matching
    self.replace_self_annot = None
    inst = abstract_utils.get_atomic_value(
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
    if abstract_utils.func_name_is_class_init(self.name):
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
    except function.InvalidParameters as e:
      if self._callself and self._callself.bindings:
        if "." in e.name:
          # match_args will try to prepend the parent's name to the error name.
          # Overwrite it with _callself instead, which may be more exact.
          _, _, e.name = e.name.rpartition(".")
        e.name = "%s.%s" % (self._callself.data[0].name, e.name)
      raise
    finally:
      if abstract_utils.func_name_is_class_init(self.name):
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

  @property
  def is_classmethod(self):
    return self.underlying.is_classmethod

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

  @property
  def has_overloads(self):
    return self.underlying.has_overloads

  @property
  def is_overload(self):
    return self.underlying.is_overload

  @is_overload.setter
  def is_overload(self, value):
    self.underlying.is_overload = value

  @property
  def defaults(self):
    return self.underlying.defaults

  def iter_signature_functions(self):
    for f in self.underlying.iter_signature_functions():
      yield self.underlying.bound_class(self._callself, f)


class BoundPyTDFunction(BoundFunction):
  pass


class Coroutine(Instance):
  """A representation of instances of coroutine."""

  def __init__(self, vm, ret_var, node):
    super().__init__(vm.convert.coroutine_type, vm)
    self.merge_instance_type_parameter(
        node, abstract_utils.T, self.vm.new_unsolvable(node))
    self.merge_instance_type_parameter(
        node, abstract_utils.T2, self.vm.new_unsolvable(node))
    self.merge_instance_type_parameter(
        node, abstract_utils.V, ret_var.AssignToNewVariable(node))

  @classmethod
  def make(cls, vm, func, node):
    """Get return type of coroutine function."""
    assert func.signature.has_return_annotation
    ret_val = func.signature.annotations["return"]
    if func.code.has_coroutine():
      ret_var = ret_val.instantiate(node)
    elif func.code.has_iterable_coroutine():
      ret_var = ret_val.get_formal_type_parameter(
          abstract_utils.V).instantiate(node)
    return cls(vm, ret_var, node)


class BaseGenerator(Instance):
  """A base class of instances of generators and async generators."""

  def __init__(self, generator_type, frame, vm, is_return_allowed):
    super().__init__(generator_type, vm)
    self.frame = frame
    self.runs = 0
    self.is_return_allowed = is_return_allowed  # if return statement is allowed

  def run_generator(self, node):
    """Run the generator."""
    if self.runs == 0:  # Optimization: We only run it once.
      node, _ = self.vm.resume_frame(node, self.frame)
      ret_type = self.frame.allowed_returns
      if ret_type:
        # set type parameters according to annotated Generator return type
        type_params = [abstract_utils.T, abstract_utils.T2]
        if self.is_return_allowed:
          type_params.append(abstract_utils.V)
        for param_name in type_params:
          _, param_var = self.vm.init_class(
              node, ret_type.get_formal_type_parameter(param_name))
          self.merge_instance_type_parameter(node, param_name, param_var)
      else:
        # infer the type parameters based on the collected type information.
        self.merge_instance_type_parameter(
            node, abstract_utils.T, self.frame.yield_variable)
        # For T2 type, it can not be decided until the send/asend function is
        # called later on. So set T2 type as ANY so that the type check will
        # not fail when the function is called afterwards.
        self.merge_instance_type_parameter(
            node, abstract_utils.T2,
            self.vm.new_unsolvable(node))
        if self.is_return_allowed:
          self.merge_instance_type_parameter(
              node, abstract_utils.V, self.frame.return_variable)
      self.runs += 1
    return node, self.get_instance_type_parameter(abstract_utils.T)

  def call(self, node, func, args, alias_map=None):
    """Call this generator or (more common) its "next/anext" attribute."""
    del func, args
    return self.run_generator(node)


class Generator(BaseGenerator):
  """A representation of instances of generators."""

  def __init__(self, generator_frame, vm):
    super().__init__(vm.convert.generator_type, generator_frame, vm, True)

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
      return super().get_special_attribute(node, name, valself)

  def __iter__(self, node):  # pylint: disable=non-iterator-returned,unexpected-special-method-signature
    return node, self.to_variable(node)


class AsyncGenerator(BaseGenerator):
  """A representation of instances of async generators."""

  def __init__(self, async_generator_frame, vm):
    super().__init__(vm.convert.async_generator_type, async_generator_frame, vm,
                     False)


class Iterator(Instance, mixin.HasSlots):
  """A representation of instances of iterators."""

  def __init__(self, vm, return_var):
    super().__init__(vm.convert.iterator_type, vm)
    mixin.HasSlots.init_mixin(self)
    self.set_slot(self.vm.convert.next_attr, self.next_slot)
    # TODO(dbaum): Should we set instance_type_parameters[self.TYPE_PARAM] to
    # something based on return_var?
    self._return_var = return_var

  def next_slot(self, node):
    return node, self._return_var


class Module(Instance, mixin.LazyMembers):
  """Represents an (imported) module."""

  def __init__(self, vm, name, member_map, ast):
    super().__init__(vm.convert.module_type, vm)
    self.name = name
    self.ast = ast
    mixin.LazyMembers.init_mixin(self, member_map)

  def _convert_member(self, ty):
    """Called to convert the items in _member_map to cfg.Variable."""
    var = self.vm.convert.constant_to_var(ty)
    for value in var.data:
      # Only do this if this is a class which isn't already part of a module, or
      # is a module itself.
      # (This happens if e.g. foo.py does "from bar import x" and we then
      #  do "from foo import x".)
      if not value.module and not isinstance(value, Module):
        value.module = self.name
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
      return self.vm.new_unsolvable(node)
    else:
      log.warning("Couldn't find attribute / module %r", full_name)
      return None

  def items(self):
    for name in self._member_map:
      self.load_lazy_attribute(name)
    return list(self.members.items())

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
    super().__init__("__build_class__", vm)

  def call(self, node, _, args, alias_map=None):
    args = args.simplify(node, self.vm)
    funcvar, name = args.posargs[0:2]
    if isinstance(args.namedargs, dict):
      kwargs = args.namedargs
    else:
      kwargs = self.vm.convert.value_to_constant(args.namedargs, dict)
    # TODO(mdemello): Check if there are any changes between python2 and
    # python3 in the final metaclass computation.
    # TODO(b/123450483): Any remaining kwargs need to be passed to the
    # metaclass.
    metaclass = kwargs.get("metaclass", None)
    if len(funcvar.bindings) != 1:
      raise abstract_utils.ConversionError(
          "Invalid ambiguous argument to __build_class__")
    func, = funcvar.data
    if not isinstance(func, InterpreterFunction):
      raise abstract_utils.ConversionError(
          "Invalid argument to __build_class__")
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
      base = abstract_utils.get_atomic_value(
          base, default=self.vm.convert.unsolvable)
      if isinstance(base, PyTDClass) and base.full_name == "typing.NamedTuple":
        # The subclass of NamedTuple will ignore all its base classes. This is
        # controled by a metaclass provided to NamedTuple.
        # See: https://github.com/python/typing/blob/master/src/typing.py#L2170
        return base.make_class(node, func.f_locals.to_variable(node))
    return self.vm.make_class(
        node, name, list(bases), func.f_locals.to_variable(node), metaclass,
        new_class_var=class_closure_var, is_decorated=self.is_decorated)


class Unsolvable(Singleton):
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
    super().__init__("unsolveable", vm)

  def get_special_attribute(self, node, name, _):
    # Overrides Singleton.get_special_attributes.
    if name in self.IGNORED_ATTRIBUTES:
      return None
    else:
      return self.to_variable(node)

  def argcount(self, _):
    return 0


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
    name = escape.unknown(Unknown._current_id)
    super().__init__(name, vm)
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

  @classmethod
  def _to_pytd(cls, node, v):
    if isinstance(v, cfg.Variable):
      return pytd_utils.JoinTypes(cls._to_pytd(node, t) for t in v.data)
    elif isinstance(v, Unknown):
      # Do this directly, and use NamedType, in case there's a circular
      # dependency among the Unknown instances.
      return pytd.NamedType(v.class_name)
    else:
      return v.to_type(node)

  @classmethod
  def _make_params(cls, node, args):
    """Convert a list of types/variables to pytd parameters."""
    def _make_param(i, p):
      return pytd.Parameter("_%d" % (i + 1), cls._to_pytd(node, p),
                            kwonly=False, optional=False, mutated_type=None)
    return tuple(_make_param(i, p) for i, p in enumerate(args))

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
    starargs = None
    starstarargs = None
    def _make_sig(args, ret):
      return pytd.Signature(self_param + self._make_params(node, args),
                            starargs,
                            starstarargs,
                            return_type=Unknown._to_pytd(node, ret),
                            exceptions=(),
                            template=())
    calls = tuple(pytd_utils.OrderedSet(
        _make_sig(args, ret) for args, _, ret in self._calls))
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
        decorators=(),
        slots=None,
        template=())

  def get_class(self):
    # We treat instances of an Unknown as the same as the class.
    return self

  def instantiate(self, node, container=None):
    return self.to_variable(node)


AMBIGUOUS = (Unknown, Unsolvable)
AMBIGUOUS_OR_EMPTY = AMBIGUOUS + (Empty,)
FUNCTION_TYPES = (BoundFunction, Function)
INTERPRETER_FUNCTION_TYPES = (BoundInterpreterFunction, InterpreterFunction)
PYTD_FUNCTION_TYPES = (BoundPyTDFunction, PyTDFunction)
