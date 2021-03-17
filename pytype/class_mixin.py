"""Mixin for all class-like abstract classes."""

import logging

from pytype import abstract_utils
from pytype import datatypes
from pytype import function
from pytype import mixin
from pytype.pytd import mro

log = logging.getLogger(__name__)


# Classes have a metadata dictionary that can store arbitrary metadata for
# various overlays. We define the dictionary keys here so that they can be
# shared by abstract.py and the overlays.
# TODO(mdemello): We choose the key based on the attribute used by the actual
# decorator for a similar purpose, but we never actually read that attribute. We
# should just use the decorator name as a key and eliminate one level of
# indirection.
_METADATA_KEYS = {
    "dataclasses.dataclass": "__dataclass_fields__",
    # attr.s gets resolved to attr._make.attrs in pyi files but intercepted by
    # the attr overlay as attr.s when processing bytecode.
    "attr.s": "__attrs_attrs__",
    "attr.attrs": "__attrs_attrs__",
    "attr._make.attrs": "__attrs_attrs__"
}


def get_metadata_key(decorator):
  return _METADATA_KEYS.get(decorator)


class Attribute:
  """Represents a class member variable.

  Members:
    name: field name
    typ: field python type
    init: Whether the field should be included in the generated __init__
    kw_only: Whether the field is kw_only in the generated __init__
    default: Default value

  Used in metadata (see Class.metadata below).
  """

  def __init__(self, name, typ, init, kw_only, default, pytd_const=None):
    self.name = name
    self.typ = typ
    self.init = init
    self.kw_only = kw_only
    self.default = default
    # Store the pytd_const if we have generated this via from_pytd_constant.
    self.pytd_const = pytd_const

  @classmethod
  def from_pytd_constant(cls, const, vm):
    typ = vm.convert.constant_to_value(const.type)
    val = const.value and vm.convert.constant_to_value(const.value)
    # Dataclasses and similar decorators in pytd files cannot set init and
    # kw_only properties.
    return cls(name=const.name, typ=typ, init=True, kw_only=False, default=val,
               pytd_const=const)

  def to_pytd_constant(self):
    # TODO(mdemello): This is a bit fragile, but we only call this when
    # constructing a dataclass from a PyTDClass, where the initial Attribute
    # will have been created from a parent PyTDClass.
    return self.pytd_const

  def __repr__(self):
    return str({"name": self.name, "typ": self.typ, "init": self.init,
                "default": self.default})


class Class(metaclass=mixin.MixinMeta):
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
    self._init_overrides_bool()
    self._all_formal_type_parameters = datatypes.AliasingMonitorDict()
    self._all_formal_type_parameters_loaded = False
    # Call these methods in addition to __init__ when constructing instances.
    self.additional_init_methods = []
    if self._is_test_class():
      self.additional_init_methods.append("setUp")

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
        if parent.name == "typing.Protocol":
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

  def _init_overrides_bool(self):
    """Compute and cache whether the class sets its own boolean value."""
    # A class's instances can evaluate to False if it defines __bool__ or
    # __len__. Python2 used __nonzero__ rather than __bool__.
    bool_override = "__bool__" if self.vm.PY3 else "__nonzero__"
    if self.isinstance_ParameterizedClass():
      self.overrides_bool = self.base_cls.overrides_bool
      return
    for cls in self.mro:
      if isinstance(cls, Class):
        if any(x in cls.get_own_methods() for x in (bool_override, "__len__")):
          self.overrides_bool = True
          return
    self.overrides_bool = False

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

  def _has_explicit_abcmeta(self):
    return self.cls and any(
        parent.full_name == "abc.ABCMeta" for parent in self.cls.mro)

  def _has_implicit_abcmeta(self):
    """Whether the class should be considered implicitly abstract."""
    # Protocols must be marked as abstract to get around the
    # [ignored-abstractmethod] check for interpreter classes.
    if not self.isinstance_InterpreterClass():
      return False
    # We check self._bases (immediate parents) instead of self.mro because our
    # builtins and typing stubs are inconsistent about implementing abstract
    # methods, and we don't want [not-instantiable] errors all over the place
    # because a class has Protocol buried in its MRO.
    for var in self._bases:
      if any(parent.full_name == "typing.Protocol" for parent in var.data):
        return True
    return False

  @property
  def is_abstract(self):
    return ((self._has_explicit_abcmeta() or self._has_implicit_abcmeta()) and
            bool(self.abstract_methods))

  def _is_test_class(self):
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

  def call_init_subclass(self, node):
    """Call init_subclass(cls) for all base classes."""
    for b in self.bases():
      # If a base has multiple bindings don't try to call init_subclass, since
      # it is not clear what to do if different bindings implement the method
      # differently.
      if len(b.data) == 1:
        base, = b.data
        node = base.init_subclass(node, self)
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
    # Call any additional initalizers the class has registered.
    for method in self.additional_init_methods:
      node = self._call_method(node, value, method, function.Args(()))
    return node

  def _new_instance(self, container):
    # We allow only one "instance" per code location, regardless of call stack.
    key = self.vm.frame.current_opcode
    assert key
    if key not in self._instance_cache:
      self._instance_cache[key] = self._to_instance(container)
    return self._instance_cache[key]

  def call(self, node, value, args):
    if self.is_abstract and not self.from_annotation:
      self.vm.errorlog.not_instantiable(self.vm.frames, self)
    node, variable = self._call_new_and_init(node, value, args)
    if variable is None:
      value = self._new_instance(None)
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

  def _get_base_class_attrs(self, cls_attrs, metadata_key):
    """Traverse the MRO and collect base class attributes for metadata_key."""
    # We only add an attribute if it hasn't been defined before.
    base_attrs = []
    taken_attr_names = {a.name for a in cls_attrs}
    for base_cls in self.mro[1:]:
      if not isinstance(base_cls, Class):
        continue
      sub_attrs = base_cls.metadata.get(metadata_key, None)
      if sub_attrs is None:
        continue
      for a in sub_attrs:
        if a.name not in taken_attr_names:
          taken_attr_names.add(a.name)
          base_attrs.append(a)
    return base_attrs

  def compute_attr_metadata(self, own_attrs, decorator):
    """Sets combined metadata based on inherited and own attrs.

    Args:
      own_attrs: The attrs defined explicitly in this class
      decorator: The fully qualified decorator name

    Returns:
      The list of combined attrs.
    """
    # We want this to crash if 'decorator' is not in _METADATA_KEYS
    assert decorator in _METADATA_KEYS, f"No metadata key for {decorator}"
    key = _METADATA_KEYS[decorator]
    base_attrs = self._get_base_class_attrs(own_attrs, key)
    attrs = base_attrs + own_attrs
    # Stash attributes in class metadata for subclasses.
    self.metadata[key] = attrs
    return attrs

  def init_attr_metadata_from_pytd(self, decorator, fields):
    """Initialise metadata[key] with a list of Attributes."""
    # Called in abstract.PyTDClass.__init__
    own_attrs = [Attribute.from_pytd_constant(c, self.vm) for c in fields]
    self.compute_attr_metadata(own_attrs, decorator)
