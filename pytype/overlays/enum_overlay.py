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
from pytype import function
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
    cls_var = cls_var or self.vm.loaded_overlays["enum"].members["EnumMeta"]
    return self.vm.make_class(node, name_var, bases, class_dict_var, cls_var,
                              new_class_var, class_type=EnumInstance)

  def call(self, node, func, args, alias_map=None):
    """Implements the behavior of the enum functional API."""
    # Because of how this is called, we supply our own "self" argument.
    # See class_mixin.Class._call_new_and_init.
    args = args.simplify(node, self.vm)
    args = args.replace(posargs=(self.vm.new_unsolvable(node),) + args.posargs)
    # To actually type check this call, we build a new SimpleFunction and check
    # against that. This guarantees we only check against the functional API
    # signature for __new__, rather than the value lookup signature.
    # Note that super().call or _call_new_and_init won't work here, because
    # they don't raise FailedFunctionCall.
    self.load_lazy_attribute("__new__")
    pytd_new = abstract_utils.get_atomic_value(self.members["__new__"])
    # There are two signatures for __new__. We want the longer one.
    sig = max(
        pytd_new.signatures, key=lambda s: s.signature.maximum_param_count())
    sig = sig.signature
    new = abstract.SimpleFunction.from_signature(sig, self.vm)
    new.call(node, None, args, alias_map)
    argmap = {name: var for name, var, _ in sig.iter_args(args)}

    cls_name_var = argmap["value"]
    try:
      names = abstract_utils.get_atomic_python_constant(argmap["names"])
    except abstract_utils.ConversionError as e:
      log.info("Failed to unwrap values in enum functional interface:\n%s", e)
      return node, self.vm.new_unsolvable(node)

    if isinstance(names, str):
      names = names.replace(",", " ").split()
      fields = {name: self.vm.convert.build_int(node) for name in names}
    elif isinstance(names, dict):
      # Dict keys are strings, not strings in variables. The values are
      # variables, they don't need to be changed.
      fields = names
    else:
      # List of names, or list of (name, value) pairs.
      try:
        possible_pairs = [abstract_utils.get_atomic_python_constant(p)
                          for p in names]
      except abstract_utils.ConversionError as e:
        log.debug("Failed to unwrap possible enum field pairs:\n  %s", e)
        return node, self.vm.new_unsolvable(node)
      if not possible_pairs:
        fields = {}
      elif isinstance(possible_pairs[0], str):
        fields = {name: self.vm.convert.build_int(node)
                  for name in possible_pairs}
      else:
        # List of (name_var, value_var) pairs.
        # The earlier get_atomic_python_constant call only unwrapped the tuple,
        # so the values in the tuple still need to be unwrapped.
        try:
          fields = {
              abstract_utils.get_atomic_python_constant(name):
                  value
              for name, value in possible_pairs
          }
        except abstract_utils.ConversionError as e:
          log.debug("Failed to unwrap field names for enum:\n  %s", e)
          return node, self.vm.new_unsolvable(node)

    cls_dict = abstract.Dict(self.vm)
    cls_dict.update(node, fields)

    metaclass = self.vm.loaded_overlays["enum"].members["EnumMeta"]

    return self.vm.make_class(
        node=node,
        name_var=cls_name_var,
        bases=[self.to_variable(node)],
        class_dict_var=cls_dict.to_variable(node),
        cls_var=metaclass,
        class_type=EnumInstance)


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

  def is_empty_enum(self):
    for member in self.members.values():
      for b in member.data:
        if b.cls == self:
          return False
    return True


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

  def _get_class_locals(self, node, cls_name, cls_dict):
    # First, check if get_class_locals works for this class.
    if cls_name in self.vm.local_ops:
      ret = classgen.get_class_locals(
          cls_name, False, classgen.Ordering.LAST_ASSIGN, self.vm).items()
      return ret

    # If it doesn't work, then it's likely this class was created using the
    # functional API. Grab members from the cls_dict instead.
    ret = {name: abstract_utils.Local(node, None, None, value, self.vm)
           for name, value in cls_dict.items()}
    return ret.items()

  def _make_new(self, node, member_type, cls):
    # Note that setup_interpreterclass and setup_pytdclass both set member_type
    # to `unsolvable` if the enum has no members. Technically, `__new__` should
    # not accept any arguments, because it will always fail if the enum has no
    # members. But `unsolvable` is much simpler to implement and use.
    return overlay_utils.make_method(
        vm=self.vm,
        node=node,
        name="__new__",
        params=[
            overlay_utils.Param("value", member_type)
        ],
        return_type=cls)

  def _get_base_type(self, bases):
    # Enums may have a data class as one of their bases: class F(str, Enum) will
    # make all of F's members strings, even if they're assigned a value of
    # a different type.
    # The enum library searches through cls's bases' MRO to find all possible
    # base types. For simplicity, we just grab the second-to-last base.
    if len(bases) > 1:
      base_type_var = bases[-2]
      return abstract_utils.get_atomic_value(base_type_var, default=None)
    elif bases and len(bases[0].data) == 1:
      base_type_cls = abstract_utils.get_atomic_value(bases[0])
      if isinstance(base_type_cls, EnumInstance):
        # Enums with no members and no explicit base type have `unsolvable` as
        # their member type. Their subclasses use the default base type, int.
        # Some enums may have members with actually unsolvable member types, so
        # check if the enum is empty.
        if (base_type_cls.member_type == self.vm.convert.unsolvable and
            base_type_cls.is_empty_enum()):
          return None
        else:
          return base_type_cls.member_type
      elif base_type_cls.is_enum:
        return self._get_base_type(base_type_cls.bases())
    return None

  def _is_orig_auto(self, orig):
    try:
      data = abstract_utils.get_atomic_value(orig)
    except abstract_utils.ConversionError as e:
      log.info("Failed to extract atomic enum value for auto() check: %s", e)
      return False
    return data.isinstance_Instance() and data.cls.full_name == "enum.auto"

  def _call_generate_next_value(self, node, cls, name):
    node, method = self.vm.attribute_handler.get_attribute(
        node, cls, "_generate_next_value_", cls.to_binding(node))
    if method:
      args = function.Args(posargs=(
          self.vm.convert.build_string(node, name),
          self.vm.convert.build_int(node),
          self.vm.convert.build_int(node),
          self.vm.convert.build_list(node, [])))
      return self.vm.call_function(node, method, args)
    else:
      return node, self.vm.convert.build_int(node)

  def _mark_dynamic_enum(self, cls):
    # Checks if the enum should be marked as having dynamic attributes.
    # The most typical use of custom subclasses of EnumMeta is to add more
    # members to the enum, or to (for example) make attribute access
    # case-insensitive. Treat such enums as having dynamic attributes.
    # Of course, if it's already marked dynamic, don't accidentally unmark it.
    if cls.maybe_missing_members:
      return
    if cls.cls and cls.cls.full_name != "enum.EnumMeta":
      cls.maybe_missing_members = True
      return
    for base_var in cls.bases():
      for base in base_var.data:
        if base.is_enum and base.cls and base.cls.full_name != "enum.EnumMeta":
          cls.maybe_missing_members = True
          return

  def _setup_interpreterclass(self, node, cls):
    member_types = []
    base_type = self._get_base_type(cls.bases())
    for name, local in self._get_class_locals(node, cls.name, cls.members):
      # Build instances directly, because you can't call instantiate() when
      # creating the class -- pytype complains about recursive types.
      member = abstract.Instance(cls, self.vm)
      assert local.orig, ("A local with no assigned value was passed to the "
                          "enum overlay.")
      value = local.orig
      if self._is_orig_auto(value):
        node, value = self._call_generate_next_value(node, cls, name)
      if base_type:
        args = function.Args(posargs=(value,))
        node, value = base_type.call(node, base_type.to_binding(node), args)
      member.members["value"] = value
      member.members["_value_"] = value
      member.members["name"] = self.vm.convert.build_string(node, name)
      cls.members[name] = member.to_variable(node)
      member_types.extend(value.data)
    if base_type:
      member_type = base_type
    elif member_types:
      member_type = self.vm.convert.merge_classes(member_types)
    else:
      member_type = self.vm.convert.unsolvable
    cls.member_type = member_type
    cls.members["__new__"] = self._make_new(node, member_type, cls)
    cls.members["__eq__"] = EnumCmpEQ(self.vm).to_variable(node)
    # _generate_next_value_ is used as a static method of the enum, not a class
    # method. We need to rebind it here to make pytype analyze it correctly.
    # However, we skip this if it's already a staticmethod.
    if "_generate_next_value_" in cls.members:
      gnv = cls.members["_generate_next_value_"]
      if not any(x.isinstance_StaticMethodInstance() for x in gnv.data):
        args = function.Args(posargs=(gnv,))
        node, new_gnv = self.vm.load_special_builtin("staticmethod").call(
            node, None, args)
        cls.members["_generate_next_value_"] = new_gnv
    self._mark_dynamic_enum(cls)
    return node

  def _setup_pytdclass(self, node, cls):
    # We need to rewrite the member map of the PytdClass.
    members = dict(cls._member_map)  # pylint: disable=protected-access
    member_types = []
    for name, pytd_val in members.items():
      # Only constants need to be transformed. We assume that enums in type
      # stubs are full realized, i.e. there are no auto() calls and the members
      # already have values of the base type.
      # TODO(tsudol): Ensure only valid enum members are transformed.
      if not isinstance(pytd_val, pytd.Constant):
        continue
      # Build instances directly, because you can't call instantiate() when
      # creating the class -- pytype complains about recursive types.
      member = abstract.Instance(cls, self.vm)
      member.members["name"] = self.vm.convert.constant_to_var(
          pyval=pytd.Constant(name="name", type=self._str_pytd),
          node=node)
      # Some type stubs may use the class type for enum member values, instead
      # of the actual value type. Detect that and use Any.
      if pytd_val.type.name == cls.pytd_cls.name:
        value_type = pytd.AnythingType()
      else:
        value_type = pytd_val.type
      member.members["value"] = self.vm.convert.constant_to_var(
          pyval=pytd.Constant(name="value", type=value_type),
          node=node)
      member.members["_value_"] = member.members["value"]
      cls._member_map[name] = member  # pylint: disable=protected-access
      cls.members[name] = member.to_variable(node)
      member_types.append(value_type)
    if not member_types:
      member_types.append(pytd.AnythingType())
    member_type = self.vm.convert.constant_to_value(
        pytd_utils.JoinTypes(member_types))
    cls.members["__new__"] = self._make_new(node, member_type, cls)
    cls.members["__eq__"] = EnumCmpEQ(self.vm).to_variable(node)
    self._mark_dynamic_enum(cls)
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
    # We may have been given an instance of the class, such as if pytype is
    # analyzing this method due to a super() call in a subclass.
    if cls.isinstance_Instance():
      cls = cls.cls
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
