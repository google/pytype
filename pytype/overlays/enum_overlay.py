"""Overlay for the enum standard library.

For InterpreterClass enums, i.e. ones in the file being analyzed, the overlay
is accessed by:
1. abstract.BuildClass sees a class with enum.Enum as its parent, and calls
EnumBuilder.make_class.
2. EnumBuilder.make_class does some validation, then passes along the actual
creation to vm.make_class. Notably, EnumBuilder passes in EnumInstance to
vm.make_class, which provides enum-specific behavior.
3. vm.make_class does its usual, then calls call_metaclass_init on the newly
created EnumInstance. This bounces back into the overlay, namely EnumMetaInit.
4. EnumMetaInit does the actual transformation of members into proper enum
members.

The transformation into an enum happens so late because enum members are
instances of the enums, which is easier to accomplish when the enum class has
already been created.

PytdClass enums, i.e. those loaded from type stubs, enter the overlay when the
pytd.Class is wrapped with an abstract.PyTDClass in convert.py. After wrapping,
call_metaclass_init is called, allowing EnumMetaInit to transform the PyTDClass
into a proper enum.
"""

import logging

from pytype import abstract
from pytype import abstract_utils
from pytype import overlay
from pytype import overlay_utils
from pytype.overlays import classgen
from pytype.pytd import pytd
from pytype.pytd import pytd_utils

log = logging.getLogger(__name__)


class EnumOverlay(overlay.Overlay):
  """An overlay for the enum std lib module."""

  def __init__(self, vm):
    if vm.options.use_enum_overlay:
      member_map = {
          "Enum": EnumBuilder,
          "EnumMeta": EnumMeta,
      }
    else:
      member_map = {}
    ast = vm.loader.import_name("enum")
    super().__init__(vm, "enum", member_map, ast)


class EnumBuilder(abstract.PyTDClass):
  """Overlays enum.Enum."""

  def __init__(self, vm):
    enum_ast = vm.loader.import_name("enum")
    pyval = enum_ast.Lookup("enum.Enum")
    super().__init__("Enum", pyval, vm)

  def make_class(self, node, name_var, bases, class_dict_var, cls_var,
                 new_class_var=None, is_decorated=False):
    """Check the members for errors, then create the enum class."""
    # TODO(tsudol): Handle is_decorated: @enum.unique, for example.
    del is_decorated
    # make_class intercepts the class creation for enums in order to check for
    # errors. EnumMeta turns the class into a full enum, but that's too late for
    # proper error checking.
    # TODO(tsudol): Check enum validity.
    return self.vm.make_class(node, name_var, bases, class_dict_var, cls_var,
                              new_class_var, class_type=EnumInstance)


class EnumInstance(abstract.InterpreterClass):
  """A wrapper for classes that subclass enum.Enum."""

  def __init__(self, name, bases, members, cls, vm):
    super().__init__(name, bases, members, cls, vm)
    # This is set by EnumMetaInit.setup_interpreterclass.
    self.member_type = None

  def instantiate(self, node, container=None):
    # Instantiate creates a canonical enum member. This intended for when no
    # particular enum member is needed, e.g. during analysis. Real members have
    # these fields set during class creation.
    # TODO(tsudol): Use the types of other members to set `value`.
    del container
    instance = abstract.Instance(self, self.vm)
    instance.members["name"] = self.vm.convert.build_string(node, "")
    if self.member_type:
      value = self.member_type.instantiate(node)
    else:
      # instantiate() should never be called before setup_interpreterclass sets
      # self.member_type, because pytype will complain about recursive types.
      # But there's no reason not to make sure this function is safe.
      value = self.vm.new_unsolvable(node)
    instance.members["value"] = value
    return instance.to_variable(node)


class EnumCmpEQ(abstract.SimpleFunction):
  """Implements the functionality of __eq__ for an enum."""

  def __init__(self, vm):
    super().__init__(
        name="__eq__",
        param_names=("self", "other"),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={
            "return": vm.convert.bool_type,
        },
        vm=vm)

  def call(self, node, unused_f, args, alias_map=None):
    _, argmap = self.match_and_map_args(node, args, alias_map)
    this_var = argmap["self"]
    other_var = argmap["other"]
    # This is called by vm._call_binop_on_bindings, so both should have
    # exactly 1 possibility.
    try:
      this = abstract_utils.get_atomic_value(this_var)
      other = abstract_utils.get_atomic_value(other_var)
    except abstract_utils.ConversionError:
      return node, self.vm.convert.build_bool(node)
    return node, self.vm.convert.build_bool(
        node,
        this.cls == other.cls and
        "name" in this.members and
        this.members["name"] == other.members.get("name"))


class EnumMeta(abstract.PyTDClass):
  """Wrapper for enum.EnumMeta.

  EnumMeta is essentially a container for the functions that drive a lot of the
  enum behavior: EnumMetaInit for modifying enum classes, for example.
  """

  def __init__(self, vm):
    enum_ast = vm.loader.import_name("enum")
    pytd_cls = enum_ast.Lookup("enum.EnumMeta")
    super().__init__("EnumMeta", pytd_cls, vm)
    init = EnumMetaInit(vm)
    self._member_map["__init__"] = init
    self.members["__init__"] = init.to_variable(vm.root_node)
    getitem = EnumMetaGetItem(vm)
    self._member_map["__getitem__"] = getitem
    self.members["__getitem__"] = getitem.to_variable(vm.root_node)


class EnumMetaInit(abstract.SimpleFunction):
  """Implements the functionality of EnumMeta.__init__.

  Overlaying this function is necessary in order to hook into pytype's metaclass
  handling and set up the Enum classes correctly.
  """

  def __init__(self, vm):
    super().__init__(
        name="__init__",
        param_names=("cls", "name", "bases", "namespace"),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={},
        vm=vm)
    self._str_pytd = vm.lookup_builtin("builtins.str")
    self._ignored_locals = {"__module__", "__qualname__"}

  def _make_new(self, node, member_type, cls):
    return overlay_utils.make_method(
        vm=self.vm,
        node=node,
        name="__new__",
        params=[
            overlay_utils.Param("value", member_type)
        ],
        return_type=cls)

  def _setup_interpreterclass(self, node, cls):
    member_types = []
    for name, value in classgen.get_class_locals(
        cls.name, False, classgen.Ordering.LAST_ASSIGN, self.vm).items():
      # Build instances directly, because you can't call instantiate() when
      # creating the class -- pytype complains about recursive types.
      member = abstract.Instance(cls, self.vm)
      member.members["value"] = value.orig
      member.members["name"] = self.vm.convert.build_string(node, name)
      cls.members[name] = member.to_variable(node)
      member_types.extend(value.orig.data)
    member_type = self.vm.convert.merge_classes(member_types)
    cls.member_type = member_type
    cls.members["__new__"] = self._make_new(node, member_type, cls)
    cls.members["__eq__"] = EnumCmpEQ(self.vm).to_variable(node)
    return node

  def _setup_pytdclass(self, node, cls):
    # We need to rewrite the member map of the PytdClass.
    members = dict(cls._member_map)  # pylint: disable=protected-access
    member_types = []
    for name, pytd_val in members.items():
      # Only constants need to be transformed.
      # TODO(tsudol): Ensure only valid enum members are transformed.
      if not isinstance(pytd_val, pytd.Constant):
        continue
      # Build instances directly, because you can't call instantiate() when
      # creating the class -- pytype complains about recursive types.
      member = abstract.Instance(cls, self.vm)
      member.members["name"] = self.vm.convert.constant_to_var(
          pyval=pytd.Constant(name="name", type=self._str_pytd),
          node=node)
      member.members["value"] = self.vm.convert.constant_to_var(
          pyval=pytd.Constant(name="value", type=pytd_val.type),
          node=node)
      cls._member_map[name] = member  # pylint: disable=protected-access
      cls.members[name] = member.to_variable(node)
      member_types.append(pytd_val.type)
    member_type = self.vm.convert.constant_to_value(
        pytd_utils.JoinTypes(member_types))
    cls.members["__new__"] = self._make_new(node, member_type, cls)
    cls.members["__eq__"] = EnumCmpEQ(self.vm).to_variable(node)
    return node

  def call(self, node, func, args, alias_map=None):
    # Use super.call to check args and get a return value.
    node, ret = super().call(node, func, args, alias_map)
    argmap = self._map_args(node, args)

    # Args: cls, name, bases, namespace_dict.
    # cls is the EnumInstance created by EnumBuilder.make_class, or an
    # abstract.PyTDClass created by convert.py.
    cls_var = argmap["cls"]
    cls, = cls_var.data

    # This function will get called for every class that has enum.EnumMeta as
    # its metaclass, including enum.Enum and other enum module members.
    # We don't have anything to do for those, so return early.
    if cls.isinstance_PyTDClass() and cls.full_name.startswith("enum."):
      return node, ret

    if cls.isinstance_InterpreterClass():
      node = self._setup_interpreterclass(node, cls)
    elif cls.isinstance_PyTDClass():
      node = self._setup_pytdclass(node, cls)
    else:
      raise ValueError(
          f"Expected an InterpreterClass or PyTDClass, but got {type(cls)}")

    return node, ret


class EnumMetaGetItem(abstract.SimpleFunction):
  """Implements the functionality of __getitem__ for enums."""

  def __init__(self, vm):
    super().__init__(
        name="__getitem__",
        param_names=("cls", "name"),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={"name": vm.convert.str_type},
        vm=vm)

  def _get_member_by_name(self, enum, name):
    if isinstance(enum, EnumInstance):
      return enum.members.get(name)
    else:
      assert isinstance(enum, abstract.PyTDClass)
      if name in enum:
        enum.load_lazy_attribute(name)
        return enum.members[name]

  def call(self, node, _, args, alias_map=None):
    _, argmap = self.match_and_map_args(node, args, alias_map)
    cls_var = argmap["cls"]
    name_var = argmap["name"]
    try:
      cls = abstract_utils.get_atomic_value(cls_var)
    except abstract_utils.ConversionError:
      return node, self.vm.new_unsolvable(node)
    # If we can't get a concrete name, treat it like it matches and return a
    # canonical enum member.
    try:
      name = abstract_utils.get_atomic_python_constant(name_var, str)
    except abstract_utils.ConversionError:
      return node, cls.instantiate(node)
    inst = self._get_member_by_name(cls, name)
    if inst:
      return node, inst
    else:
      self.vm.errorlog.attribute_error(
          self.vm.frames, cls_var.bindings[0], name)
      return node, self.vm.new_unsolvable(node)
