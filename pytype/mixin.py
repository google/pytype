"""Mixins for abstract.py."""

import logging

from pytype import abstract_utils
from pytype import datatypes
from pytype import function
from pytype.pytd import mro
from pytype.pytd import pytd

import six

log = logging.getLogger(__name__)


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
              cls.__mixin_overloads__[method] = sup
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

  overloads = ("__repr__",)

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
      self._function_cache[key] = self.vm.make_native_function(name, method)
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
    return self.vm.call_function(node, self._super[name], function.Args(args),
                                 fallback_to_unsolvable=False)

  def get_special_attribute(self, node, name, valself):
    if name in self._slots:
      attr = self.vm.program.NewVariable()
      additional_sources = {valself} if valself else None
      attr.PasteVariable(self._slots[name], node, additional_sources)
      return attr
    return HasSlots.super(self.get_special_attribute)(node, name, valself)


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
    # Key-value store of metadata for overlays to use.
    self.metadata = {}
    self._instance_cache = {}
    self._init_abstract_methods()
    self._init_protocol_methods()
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

    bases = [
        abstract_utils.get_atomic_value(
            base, default=self.vm.convert.unsolvable) for base in self.bases()]
    for base in bases:
      abstract_utils.parse_formal_type_parameters(
          base, self.full_name, self._all_formal_type_parameters)

    self._all_formal_type_parameters_loaded = True

  def get_own_methods(self):
    """Get the methods defined by this class."""
    raise NotImplementedError(self.__class__.__name__)

  def _is_protocol(self):
    """Whether this class is a protocol."""
    if self.isinstance_PyTDClass():
      for parent in self.pytd_cls.parents:
        if isinstance(
            parent, pytd.ClassType) and parent.name == "typing.Protocol":
          return True
    elif self.isinstance_InterpreterClass():
      for parent_var in self._bases:
        for parent in parent_var.data:
          if (parent.isinstance_PyTDClass() and
              parent.full_name == "typing.Protocol"):
            return True
    return False

  def _init_protocol_methods(self):
    """Compute this class's protocol methods."""
    if self.isinstance_ParameterizedClass():
      self.protocol_methods = self.base_cls.protocol_methods
      return
    if not self._is_protocol():
      self.protocol_methods = set()
      return
    if self.isinstance_PyTDClass() and self.pytd_cls.name.startswith("typing."):
      # In typing.pytd, we've experimentally marked some classes such as
      # Sequence, which contains a mix of abstract and non-abstract methods, as
      # protocols, with only the abstract methods being required.
      self.protocol_methods = self.abstract_methods
      return
    # For the algorithm to run, protocol_methods needs to be populated with the
    # protocol methods defined by this class. We'll overwrite the attribute
    # with the full set of protocol methods later.
    self.protocol_methods = self.get_own_methods()
    protocol_methods = set()
    for cls in reversed(self.mro):
      if not isinstance(cls, Class):
        continue
      if cls.is_protocol:
        # Add protocol methods defined by this class.
        protocol_methods |= {m for m in cls.protocol_methods if m in cls}
      else:
        # Remove methods implemented by this class.
        protocol_methods = {m for m in protocol_methods if m not in cls}
    self.protocol_methods = protocol_methods

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
  def is_abstract(self):
    has_abstract_metaclass = self.cls and any(
        parent.full_name == "abc.ABCMeta" for parent in self.cls.mro)
    return has_abstract_metaclass and bool(self.abstract_methods)

  @property
  def is_test_class(self):
    return any(base.full_name in ("unittest.TestCase", "unittest.case.TestCase")
               for base in self.mro)

  @property
  def is_protocol(self):
    return bool(self.protocol_methods)

  def _get_inherited_metaclass(self):
    for base in self.mro[1:]:
      if isinstance(base, Class) and base.cls is not None:
        return base.cls
    return None

  def call_metaclass_init(self, node):
    """Call the metaclass's __init__ method if it does anything interesting."""
    if not self.cls:
      return node
    node, init = self.vm.attribute_handler.get_attribute(
        node, self.cls, "__init__")
    if not init or not any(
        f.isinstance_InterpreterFunction() for f in init.data):
      # Only an InterpreterFunction has interesting side effects.
      return node
    # TODO(rechen): The signature is (cls, name, bases, dict); should we fill in
    # the last three args more precisely?
    args = function.Args(posargs=(self.to_variable(node),) + tuple(
        self.vm.new_unsolvable(node) for _ in range(3)))
    log.debug("Calling __init__ on metaclass %s of class %s",
              self.cls.name, self.name)
    node, _ = self.vm.call_function(node, init, args)
    return node

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
      if (f.isinstance_AMBIGUOUS_OR_EMPTY() or
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
      # If val.data is a class, _call_init mistakenly calls val.data's __init__
      # method rather than that of val.data.cls.
      if not isinstance(val.data, Class) and self == val.data.cls:
        node = self._call_init(node, val, args)
    return node, variable

  def _call_method(self, node, value, method_name, args):
    node, method = self.vm.attribute_handler.get_attribute(
        node, value.data, method_name, value)
    if method:
      call_repr = "%s.%s(..._)" % (self.name, method_name)
      log.debug("calling %s", call_repr)
      node, ret = self.vm.call_function(node, method, args)
      log.debug("%s returned %r", call_repr, ret)
    return node

  def _call_init(self, node, value, args):
    node = self._call_method(node, value, "__init__", args)
    # Test classes initialize attributes in setUp() as well.
    if self.is_test_class:
      node = self._call_method(node, value, "setUp", function.Args(()))
    return node

  def _new_instance(self):
    # We allow only one "instance" per code location, regardless of call stack.
    key = self.vm.frame.current_opcode
    assert key
    if key not in self._instance_cache:
      self._instance_cache[key] = self._to_instance()
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
      container = self.to_annotation_container()
      return container.get_special_attribute(node, name, valself)
    return Class.super(self.get_special_attribute)(node, name, valself)

  def has_dynamic_attributes(self):
    return any(a in self for a in abstract_utils.DYNAMIC_ATTRIBUTE_MARKERS)

  def compute_is_dynamic(self):
    # This needs to be called after self.mro is set.
    return any(c.has_dynamic_attributes()
               for c in self.mro
               if isinstance(c, Class))

  def compute_mro(self):
    """Compute the class precedence list (mro) according to C3."""
    bases = abstract_utils.get_mro_bases(self.bases(), self.vm)
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
        if base.isinstance_ParameterizedClass():
          base2cls[base.base_cls] = base
          baselist.append(base.base_cls)
        else:
          base2cls[base] = base
          baselist.append(base)
      newbases.append(baselist)

    # calc MRO and replace them with original base classes
    return tuple(base2cls[base] for base in mro.MROMerge(newbases))
