"""Abstract class representations."""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import attrs

from pytype import datatypes
from pytype.abstract import _base
from pytype.abstract import _instance_base
from pytype.abstract import _instances
from pytype.abstract import _special_classes
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd.codegen import decorate
from pytype.typegraph import cfg

log = logging.getLogger(__name__)
_isinstance = abstract_utils._isinstance  # pylint: disable=protected-access

# These classes can't be imported due to circular deps.
_ContextType = Any  # context.Context
_TypeParamType = Any  # typing.TypeParameter


class BuildClass(_base.BaseValue):
  """Representation of the Python 3 __build_class__ object."""

  CLOSURE_NAME = "__class__"

  def __init__(self, ctx):
    super().__init__("__build_class__", ctx)

  def call(self, node, _, args, alias_map=None):
    args = args.simplify(node, self.ctx)
    funcvar, name = args.posargs[0:2]
    kwargs = args.namedargs
    # TODO(mdemello): Check if there are any changes between python2 and
    # python3 in the final metaclass computation.
    # TODO(b/123450483): Any remaining kwargs need to be passed to the
    # metaclass.
    metaclass = kwargs.get("metaclass", None)
    if len(funcvar.bindings) != 1:
      raise abstract_utils.ConversionError(
          "Invalid ambiguous argument to __build_class__")
    func, = funcvar.data
    if not _isinstance(func, "InterpreterFunction"):
      raise abstract_utils.ConversionError(
          "Invalid argument to __build_class__")
    func.is_class_builder = True
    bases = args.posargs[2:]
    subst = {}
    # We need placeholder values to stick in 'subst'. These will be replaced by
    # the actual type parameter values when attribute.py looks up generic
    # attributes on instances of this class.
    any_var = self.ctx.new_unsolvable(node)
    for basevar in bases:
      for base in basevar.data:
        if base.final:
          self.ctx.errorlog.subclassing_final_class(self.ctx.vm.frames, basevar)
        if isinstance(base, ParameterizedClass):
          subst.update(
              {v.name: any_var for v in base.formal_type_parameters.values()
               if _isinstance(v, "TypeParameter")})

    node, _ = func.call(node, funcvar.bindings[0],
                        args.replace(posargs=(), namedargs={}),
                        new_locals=True, frame_substs=(subst,))
    if func.last_frame:
      func.f_locals = func.last_frame.f_locals
      class_closure_var = func.last_frame.class_closure_var
    else:
      # We have hit 'maximum depth' before setting func.last_frame
      func.f_locals = self.ctx.convert.unsolvable
      class_closure_var = None

    props = class_mixin.ClassBuilderProperties(
        name_var=name,
        bases=list(bases),
        class_dict_var=func.f_locals.to_variable(node),
        metaclass_var=metaclass,
        new_class_var=class_closure_var,
        is_decorated=self.is_decorated)
    # Check for special classes first.
    node, clsvar = _special_classes.build_class(node, props, kwargs, self.ctx)
    if not clsvar:
      node, clsvar = self.ctx.make_class(node, props)

    self.ctx.vm.trace_classdef(clsvar)
    return node, clsvar


class InterpreterClass(_instance_base.SimpleValue, class_mixin.Class):
  """An abstract wrapper for user-defined class objects.

  These are the abstract value for class objects that are implemented in the
  program.
  """

  def __init__(self, name: str, bases: List[cfg.Variable],
               members: Dict[str, cfg.Variable], cls: _base.BaseValue,
               ctx: _ContextType):
    self._bases = bases
    super().__init__(name, ctx)
    self.members = datatypes.MonitorDict(members)
    class_mixin.Class.init_mixin(self, cls)
    self.instances = set()  # filled through register_instance
    # instances created by analyze.py for the purpose of analyzing this class,
    # a subset of 'instances'. Filled through register_canonical_instance.
    self.canonical_instances = set()
    self.slots = self._convert_str_tuple(members, "__slots__")
    self.match_args = self._convert_str_tuple(members, "__match_args__") or ()
    self.is_dynamic = self.compute_is_dynamic()
    log.info("Created class: %r", self)
    self.type_param_check()
    self.decorators = []

  def _get_class(self):
    return ParameterizedClass(self.ctx.convert.type_type,
                              {abstract_utils.T: self}, self.ctx)

  def update_signature_scope(self, method):
    method.signature.excluded_types.update(
        [t.name for t in self.template])
    method.signature.add_scope(self.full_name)

  def update_method_type_params(self):
    if self.template:
      # For function type parameters check
      for mbr in self.members.values():
        prop_updated = False
        for m in reversed(mbr.data):
          if _isinstance(m, "SignedFunction"):
            self.update_signature_scope(m)
          elif not prop_updated and m.__class__.__name__ == "PropertyInstance":
            # We generate a new variable every time we add a property slot, so
            # take the last one (which contains bindings for all defined slots).
            prop_updated = True
            for slot in (m.fget, m.fset, m.fdel):
              if slot:
                for d in slot.data:
                  if _isinstance(d, "SignedFunction"):
                    self.update_signature_scope(d)

  def type_param_check(self):
    """Throw exception for invalid type parameters."""
    self.update_method_type_params()
    if self.template:
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
            self, f"Conflicting value for TypeVar {t.full_name}")

  def collect_inner_cls_types(self, max_depth=5):
    """Collect all the type parameters from nested classes."""
    templates = set()
    if max_depth > 0:
      for mbr in self.members.values():
        mbr = abstract_utils.get_atomic_value(
            mbr, default=self.ctx.convert.unsolvable)
        if isinstance(mbr, InterpreterClass) and mbr.template:
          templates.update([(mbr, item.with_module(None))
                            for item in mbr.template])
          templates.update(mbr.collect_inner_cls_types(max_depth - 1))
    return templates

  def get_inner_classes(self):
    """Return the list of top-level nested classes."""
    inner_classes = []
    for member in self.members.values():
      try:
        value = abstract_utils.get_atomic_value(member)
      except abstract_utils.ConversionError:
        continue
      if not isinstance(value, class_mixin.Class) or value.module:
        # Skip non-classes and imported classes.
        continue
      if value.official_name is None or (
          self.official_name and
          value.official_name.startswith(f"{self.official_name}.")):
        inner_classes.append(value)
    return inner_classes

  def get_own_attributes(self):
    attributes = set(self.members)
    annotations_dict = abstract_utils.get_annotations_dict(self.members)
    if annotations_dict:
      attributes.update(annotations_dict.annotated_locals)
    return attributes - abstract_utils.CLASS_LEVEL_IGNORE

  def get_own_abstract_methods(self):
    def _can_be_abstract(var):
      return any(_isinstance(v, "Function") and v.is_abstract for v in var.data)
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

  def _convert_str_tuple(self, members, field_name):
    """Convert __slots__ and similar fields from a Variable to a tuple."""
    field_var = members.get(field_name)
    if field_var is None:
      return None
    if len(field_var.bindings) != 1:
      # Ambiguous slots
      return None  # Treat "unknown __slots__" and "no __slots__" the same.
    val = field_var.data[0]
    if isinstance(val, mixin.PythonConstant):
      if isinstance(val.pyval, (list, tuple)):
        entries = val.pyval
      else:
        return None  # Happens e.g. __slots__ = {"foo", "bar"}. Not an error.
    else:
      return None  # Happens e.g. for __slots__ = dir(Foo)
    try:
      names = [abstract_utils.get_atomic_python_constant(v) for v in entries]
    except abstract_utils.ConversionError:
      return None  # Happens e.g. for __slots__ = ["x" if b else "y"]
    # Slot names should be strings.
    for s in names:
      if not isinstance(s, str):
        self.ctx.errorlog.bad_slots(self.ctx.vm.frames,
                                    f"Invalid {field_name} entry: {str(s)!r}")
        return None
    return tuple(self._mangle(s) for s in names)

  def register_instance(self, instance):
    self.instances.add(instance)

  def register_canonical_instance(self, instance):
    self.canonical_instances.add(instance)

  def bases(self):
    return self._bases

  def metaclass(self, node):
    if (self.cls.full_name != "builtins.type" and
        self.cls is not self._get_inherited_metaclass()):
      return self.ctx.convert.merge_classes([self])
    else:
      return None

  def instantiate(self, node, container=None):
    if self.ctx.vm.frame and self.ctx.vm.frame.current_opcode:
      return self._new_instance(container, node, None).to_variable(node)
    else:
      # When the analyze_x methods in CallTracer instantiate classes in
      # preparation for analysis, often there is no frame on the stack yet, or
      # the frame is a SimpleFrame with no opcode.
      return super().instantiate(node, container)

  def __repr__(self):
    return f"InterpreterClass({self.name})"

  def __contains__(self, name):
    if name in self.members:
      return True
    annotations_dict = abstract_utils.get_annotations_dict(self.members)
    return annotations_dict and name in annotations_dict.annotated_locals

  def has_protocol_base(self):
    for base_var in self._bases:
      for base in base_var.data:
        if isinstance(base, PyTDClass) and base.full_name == "typing.Protocol":
          return True
    return False


class PyTDClass(
    _instance_base.SimpleValue, class_mixin.Class, mixin.LazyMembers):
  """An abstract wrapper for PyTD class objects.

  These are the abstract values for class objects that are described in PyTD.

  Attributes:
    cls: A pytd.Class
    mro: Method resolution order. An iterable of BaseValue.
  """

  def __init__(self, name, pytd_cls, ctx):
    # Apply decorators first, in case they set any properties that later
    # initialization code needs to read.
    self.has_explicit_init = any(x.name == "__init__" for x in pytd_cls.methods)
    pytd_cls, decorated = decorate.process_class(pytd_cls)
    self.pytd_cls = pytd_cls
    super().__init__(name, ctx)
    if decorate.has_decorator(
        pytd_cls, ("typing.final", "typing_extensions.final")):
      self.final = True
    # Keep track of the names of final methods and instance variables.
    self.final_members = {}
    mm = {}
    for val in pytd_cls.constants:
      if isinstance(val.type, pytd.Annotated):
        mm[val.name] = val.Replace(type=val.type.base_type)
      elif (isinstance(val.type, pytd.GenericType) and
            val.type.base_type.name == "typing.Final"):
        self.final_members[val.name] = val
        mm[val.name] = val.Replace(type=val.type.parameters[0])
      else:
        mm[val.name] = val
    for val in pytd_cls.methods:
      mm[val.name] = val
      if val.is_final:
        self.final_members[val.name] = val
    for val in pytd_cls.classes:
      mm[val.name.rsplit(".", 1)[-1]] = val
    if pytd_cls.metaclass is None:
      metaclass = None
    else:
      metaclass = self.ctx.convert.constant_to_value(
          pytd_cls.metaclass,
          subst=datatypes.AliasingDict(),
          node=self.ctx.root_node)
    self.slots = pytd_cls.slots
    mixin.LazyMembers.init_mixin(self, mm)
    self.is_dynamic = self.compute_is_dynamic()
    class_mixin.Class.init_mixin(self, metaclass)
    if decorated:
      self._populate_decorator_metadata()

  @classmethod
  def make(cls, name, pytd_cls, ctx):
    # See if any of the special classes can be built directly from the pytd
    # class or its list of direct base classes.
    ret = _special_classes.maybe_build_from_pytd(name, pytd_cls, ctx)
    if ret:
      return ret

    # Now construct the PyTDClass, since we need a fully constructed class to
    # check the MRO. If the MRO does match a special class we build it and
    # discard the class constructed here.
    c = cls(name, pytd_cls, ctx)
    ret = _special_classes.maybe_build_from_mro(c, name, pytd_cls, ctx)
    if ret:
      return ret

    # If none of the special classes have matched, return the PyTDClass
    return c

  def _populate_decorator_metadata(self):
    """Fill in class attribute metadata for decorators like @dataclass."""
    key = None
    keyed_decorator = None
    for decorator in self.pytd_cls.decorators:
      decorator_name = decorator.type.name
      decorator_key = class_mixin.get_metadata_key(decorator_name)
      if decorator_key:
        if key:
          error = f"Cannot apply both @{keyed_decorator} and @{decorator}."
          self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, self, error)
        else:
          key, keyed_decorator = decorator_key, decorator
          self._init_attr_metadata_from_pytd(decorator_name)
          self._recompute_init_from_metadata(key)

  def _init_attr_metadata_from_pytd(self, decorator):
    """Initialise metadata[key] with a list of Attributes."""
    # Use the __init__ function as the source of truth for dataclass fields; if
    # this is a generated module we will have already processed ClassVar and
    # InitVar attributes to generate __init__, so the fields we want to add to
    # the subclass __init__ are the init params rather than the full list of
    # class attributes.
    # We also need to use the list of class constants to restore names of the
    # form `_foo`, which get replaced by `foo` in __init__.
    init = next(x for x in self.pytd_cls.methods if x.name == "__init__")
    protected = {x.name[1:]: x.name for x in self.pytd_cls.constants
                 if x.name.startswith("_")}
    params = []
    for p in init.signatures[0].params[1:]:
      if p.name in protected:
        params.append(attrs.evolve(p, name=protected[p.name]))
      else:
        params.append(p)
    with self.ctx.allow_recursive_convert():
      own_attrs = [
          class_mixin.Attribute.from_param(p, self.ctx) for p in params
      ]
    self.compute_attr_metadata(own_attrs, decorator)

  def _recompute_init_from_metadata(self, key):
    # Some decorated classes (dataclasses e.g.) have their __init__ function
    # set via traversing the MRO to collect initializers from decorated parent
    # classes as well. Since we don't have access to the MRO when initially
    # decorating the class, we recalculate the __init__ signature from the
    # combined attribute list in the metadata.
    if self.has_explicit_init:
      # Do not override an __init__ from the pyi file
      return
    attributes = self.metadata[key]
    fields = [x.to_pytd_constant() for x in attributes]
    self.pytd_cls = decorate.add_init_from_fields(self.pytd_cls, fields)
    init = self.pytd_cls.Lookup("__init__")
    self._member_map["__init__"] = init

  def get_own_attributes(self):
    return {name for name, member in self._member_map.items()}

  def get_own_abstract_methods(self):
    return {name for name, member in self._member_map.items()
            if isinstance(member, pytd.Function) and member.is_abstract}

  def bases(self):
    convert = self.ctx.convert
    return [
        convert.constant_to_var(
            base, subst=datatypes.AliasingDict(), node=self.ctx.root_node)
        for base in self.pytd_cls.bases
    ]

  def load_lazy_attribute(self, name, subst=None):
    try:
      return super().load_lazy_attribute(name, subst)
    except self.ctx.convert.TypeParameterError as e:
      self.ctx.errorlog.unbound_type_param(self.ctx.vm.frames, self, name,
                                           e.type_param_name)
      member = self.ctx.new_unsolvable(self.ctx.root_node)
      self.members[name] = member
      return member

  def _convert_member(self, name, member, subst=None):
    """Convert a member as a variable. For lazy lookup."""
    subst = subst or datatypes.AliasingDict()
    node = self.ctx.root_node
    if isinstance(member, pytd.Constant):
      return self.ctx.convert.constant_to_var(
          abstract_utils.AsInstance(member.type), subst, node)
    elif isinstance(member, pytd.Function):
      c = self.ctx.convert.constant_to_value(member, subst=subst, node=node)
      c.parent = self
      return c.to_variable(node)
    elif isinstance(member, pytd.Class):
      return self.ctx.convert.constant_to_var(member, subst=subst, node=node)
    else:
      raise AssertionError(f"Invalid class member {pytd_utils.Print(member)}")

  def _new_instance(self, container, node, args):
    if self.full_name == "builtins.tuple" and args.is_empty():
      value = _instances.Tuple((), self.ctx)
    else:
      value = _instance_base.Instance(
          self.ctx.convert.constant_to_value(self.pytd_cls), self.ctx)
    for type_param in self.template:
      name = type_param.full_name
      if name not in value.instance_type_parameters:
        value.instance_type_parameters[name] = self.ctx.program.NewVariable()
    return value

  def instantiate(self, node, container=None):
    return self.ctx.convert.constant_to_var(
        abstract_utils.AsInstance(self.pytd_cls), {}, node)

  def __repr__(self):
    return f"PyTDClass({self.name})"

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
    if name not in self.pytd_cls:
      return None
    c = self.pytd_cls.Lookup(name)
    if isinstance(c, pytd.Constant):
      try:
        self._convert_member(name, c)
      except self.ctx.convert.TypeParameterError:
        # Constant c cannot be converted without type parameter substitutions,
        # so it must be an instance attribute.
        subst = datatypes.AliasingDict()
        for itm in self.pytd_cls.template:
          subst[itm.full_name] = self.ctx.convert.constant_to_value(
              itm.type_param, {}).instantiate(
                  self.ctx.root_node, container=instance)
        return self._convert_member(name, c, subst)

  def has_protocol_base(self):
    for base in self.pytd_cls.bases:
      if base.name == "typing.Protocol":
        return True
    return False


class FunctionPyTDClass(PyTDClass):
  """PyTDClass(Callable) subclass to support annotating higher-order functions.

  In InterpreterFunction calls, type parameter annotations are handled by
  getting the types of the parameters from the arguments and instantiating them
  in the return value. To handle a signature like (func: T) -> T, we need to
  save the value of `func`, not just its type of Callable.
  """

  def __init__(self, func, ctx):
    super().__init__("typing.Callable", ctx.convert.function_type.pytd_cls, ctx)
    self.func = func

  def instantiate(self, node, container=None):
    del container  # unused
    return self.func.to_variable(node)


class ParameterizedClass(  # pytype: disable=signature-mismatch
    _base.BaseValue, class_mixin.Class, mixin.NestedAnnotation):
  """A class that contains additional parameters.

  E.g. a container.

  Attributes:
    base_cls: The base type.
    formal_type_parameters: An iterable of BaseValue, one for each type
      parameter.
  """

  def __init__(
      self, base_cls: Union[PyTDClass, InterpreterClass],
      formal_type_parameters: Union[abstract_utils.LazyFormalTypeParameters,
                                    Dict[str, _base.BaseValue]],
      ctx: _ContextType, template: Optional[Tuple[_TypeParamType, ...]] = None):
    # A ParameterizedClass is created by converting a pytd.GenericType, whose
    # base type is restricted to NamedType and ClassType.
    self.base_cls = base_cls
    super().__init__(base_cls.name, ctx)
    self._cls = None  # lazily loaded 'cls' attribute
    self.module = base_cls.module
    # Lazily loaded to handle recursive types.
    # See the formal_type_parameters() property.
    self._formal_type_parameters = formal_type_parameters
    self._formal_type_parameters_loaded = False
    self._hash = None  # memoized due to expensive computation
    if template is None:
      self._template = self.base_cls.template
    else:
      # The ability to create a new template different from the base class's is
      # needed for typing.Generic.
      self._template = template
    self.slots = self.base_cls.slots
    self.is_dynamic = self.base_cls.is_dynamic
    class_mixin.Class.init_mixin(self, base_cls.cls)
    mixin.NestedAnnotation.init_mixin(self)
    self.type_param_check()

  def __repr__(self):
    return "ParameterizedClass(cls={!r} params={})".format(
        self.base_cls,
        self._formal_type_parameters)

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
        items = self._raw_formal_type_parameters()
        cache = False
      else:
        # Use the names of the parameter values to approximate a hash, to avoid
        # infinite recursion on recursive type annotations.
        items = []
        cache = True
        for name, val in self.formal_type_parameters.items():
          # The 'is not True' check is to prevent us from incorrectly caching
          # the hash when val.resolved == LateAnnotation._RESOLVING.
          if val.is_late_annotation() and val.resolved is not True:  # pylint: disable=g-bool-id-comparison
            cache = False
          items.append((name, val.full_name))
      hashval = hash((self.base_cls, tuple(items)))
      if cache:
        self._hash = hashval
    else:
      hashval = self._hash
    return hashval

  def __contains__(self, name):
    return name in self.base_cls

  def _raw_formal_type_parameters(self):
    assert isinstance(self._formal_type_parameters,
                      abstract_utils.LazyFormalTypeParameters)
    parameters = self._formal_type_parameters.parameters
    for i, name in enumerate(self._formal_type_parameters.template):
      # TODO(rechen): A missing parameter should be an error.
      yield name, parameters[i] if i < len(parameters) else None

  def get_own_attributes(self):
    return self.base_cls.get_own_attributes()

  def get_own_abstract_methods(self):
    return self.base_cls.get_own_abstract_methods()

  @property
  def members(self):
    return self.base_cls.members

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
          formal_type_parameters[name] = self.ctx.convert.unsolvable
        else:
          formal_type_parameters[name] = self.ctx.convert.constant_to_value(
              param, self._formal_type_parameters.subst, self.ctx.root_node)
      self._formal_type_parameters = formal_type_parameters
    # Hack: we'd like to evaluate annotations at the currently active node so
    # that imports, etc., are visible. The last created node is usually the
    # active one.
    self._formal_type_parameters = (
        self.ctx.annotation_utils.convert_class_annotations(
            self.ctx.program.cfg_nodes[-1], self._formal_type_parameters))
    self._formal_type_parameters_loaded = True

  def compute_mro(self):
    return (self,) + self.base_cls.mro[1:]

  def instantiate(self, node, container=None):
    if self.full_name == "builtins.type":
      # deformalize removes TypeVars.
      instance = self.ctx.annotation_utils.deformalize(
          self.formal_type_parameters[abstract_utils.T])
      return instance.to_variable(node)
    elif self.full_name == "typing.ClassVar":
      return self.formal_type_parameters[abstract_utils.T].instantiate(
          node, container)
    else:
      return self._new_instance(container, node, None).to_variable(node)

  @property
  def cls(self):
    if not self.ctx.converter_minimally_initialized:
      return self.ctx.convert.unsolvable
    if not self._cls:
      self._cls = self.base_cls.cls
    return self._cls

  @cls.setter
  def cls(self, cls):
    self._cls = cls

  def set_class(self, node, var):
    self.base_cls.set_class(node, var)

  @property
  def official_name(self):
    return self.base_cls.official_name

  @official_name.setter
  def official_name(self, official_name):
    self.base_cls.official_name = official_name

  def _is_callable(self):
    if not isinstance(self.base_cls, (InterpreterClass, PyTDClass)):
      # We don't know how to instantiate this base_cls.
      return False
    if self.from_annotation:
      # A user-provided annotation is always instantiable.
      return True
    # Otherwise, non-abstract classes are instantiable. The exception is
    # typing classes; for example,
    #   from typing import List
    #   print(List[str]())
    # produces 'TypeError: Type List cannot be instantiated; use list() instead'
    # at runtime. However, pytype represents concrete typing classes like List
    # with their builtins equivalents, so we can't distinguish between
    # List[str]() (illegal) and list[str]() (legal in Python 3.9+); we err on
    # the side of allowing such calls.
    return not self.is_abstract

  def call(self, node, func, args, alias_map=None):
    if not self._is_callable():
      raise function.NotCallable(self)
    else:
      return class_mixin.Class.call(self, node, func, args)

  def get_formal_type_parameter(self, t):
    return self.formal_type_parameters.get(t, self.ctx.convert.unsolvable)

  def get_inner_types(self):
    return self.formal_type_parameters.items()

  def update_inner_type(self, key, typ):
    self.formal_type_parameters[key] = typ

  def replace(self, inner_types):
    inner_types = dict(inner_types)
    if isinstance(self, LiteralClass):
      if inner_types == self.formal_type_parameters:
        # If the type hasn't changed, we can return a copy of this class.
        return LiteralClass(self._instance, self.ctx, self.template)
      # Otherwise, we can't create a LiteralClass because we don't have a
      # concrete value.
      typ = ParameterizedClass
    else:
      typ = self.__class__
    return typ(self.base_cls, inner_types, self.ctx, self.template)

  def has_protocol_base(self):
    return self.base_cls.has_protocol_base()


class CallableClass(ParameterizedClass, mixin.HasSlots):  # pytype: disable=signature-mismatch
  """A Callable with a list of argument types.

  The formal_type_parameters attribute stores the types of the individual
  arguments under their indices, the overall argument type under "ARGS", and the
  return type under "RET". So for
    CallableClass[[int, bool], str]
  formal_type_parameters is
    {0: int, 1: bool, ARGS: int or bool, RET: str}
  When there are no args (CallableClass[[], ...]), ARGS contains abstract.Empty.
  """

  def __init__(self, base_cls, formal_type_parameters, ctx, template=None):
    super().__init__(base_cls, formal_type_parameters, ctx, template)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__call__", self.call_slot)
    # We subtract two to account for "ARGS" and "RET".
    self.num_args = len(self.formal_type_parameters) - 2

  def __repr__(self):
    return f"CallableClass({self.formal_type_parameters})"

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
          function.Args(posargs=args, namedargs=kwargs), self.ctx,
          kwargs.keys())
    if len(args) != self.num_args:
      raise function.WrongArgCount(
          function.Signature.from_callable(self), function.Args(posargs=args),
          self.ctx)
    match_args = [function.Arg(function.argname(i), args[i],
                               self.formal_type_parameters[i])
                  for i in range(self.num_args)]
    matcher = self.ctx.matcher(node)
    try:
      matches = matcher.compute_matches(match_args, match_all_views=False)
    except matcher.MatchError as e:
      raise function.WrongArgTypes(
          function.Signature.from_callable(self),
          function.Args(posargs=args),
          self.ctx,
          bad_param=e.bad_type)
    ret = self.ctx.annotation_utils.sub_one_annotation(
        node, self.formal_type_parameters[abstract_utils.RET],
        [m.subst for m in matches])
    if args and ret.full_name == "typing.TypeGuard":
      typeguard_return = function.handle_typeguard(
          node, function.AbstractReturnType(ret, self.ctx), args[0], self.ctx)
    else:
      typeguard_return = None
    if typeguard_return:
      retvar = typeguard_return
    else:
      node, retvar = self.ctx.vm.init_class(node, ret)
    return node, retvar

  def get_special_attribute(self, node, name, valself):
    if (valself and not abstract_utils.equivalent_to(valself, self) and
        name in self._slots):
      return mixin.HasSlots.get_special_attribute(self, node, name, valself)
    return super().get_special_attribute(node, name, valself)


class LiteralClass(ParameterizedClass):
  """The class of a typing.Literal."""

  def __init__(self, instance, ctx, template=None):
    base_cls = ctx.convert.name_to_value("typing.Literal")
    formal_type_parameters = {abstract_utils.T: instance.cls}
    super().__init__(base_cls, formal_type_parameters, ctx, template)
    self._instance = instance

  def __repr__(self):
    return f"LiteralClass({self._instance})"

  def __eq__(self, other):
    if isinstance(other, LiteralClass):
      if (isinstance(self.value, mixin.PythonConstant) and
          isinstance(other.value, mixin.PythonConstant)):
        return self.value.pyval == other.value.pyval
      else:
        return self.value == other.value
    return super().__eq__(other)

  def __hash__(self):
    return hash((super().__hash__(), self._instance))

  @property
  def value(self):
    return self._instance

  def instantiate(self, node, container=None):
    return self._instance.to_variable(node)


class TupleClass(ParameterizedClass, mixin.HasSlots):  # pytype: disable=signature-mismatch
  """The class of a heterogeneous tuple.

  The formal_type_parameters attribute stores the types of the individual tuple
  elements under their indices and the overall element type under "T". So for
    Tuple[str, int]
  formal_type_parameters is
    {0: str, 1: int, T: str or int}.
  Note that we can't store the individual types as a mixin.PythonConstant as we
  do for Tuple, since we can't evaluate type parameters during initialization.
  """

  def __init__(self, base_cls, formal_type_parameters, ctx, template=None):
    super().__init__(base_cls, formal_type_parameters, ctx, template)
    mixin.HasSlots.init_mixin(self)
    self.set_slot("__getitem__", self.getitem_slot)
    self.set_slot("__add__", self.add_slot)
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
    return f"TupleClass({self.formal_type_parameters})"

  def compute_mro(self):
    # ParameterizedClass removes the base PyTDClass(tuple) from the mro; add it
    # back here so that isinstance(tuple) checks work.
    return (self,) + self.base_cls.mro

  def get_formal_type_parameters(self):
    return {abstract_utils.full_type_name(self, abstract_utils.T):
            self.formal_type_parameters[abstract_utils.T]}

  def _new_instance(self, container, node, args):
    del args  # unused
    if self._instance:
      return self._instance
    content = []
    for i in range(self.tuple_length):
      p = self.formal_type_parameters[i]
      if container is abstract_utils.DUMMY_CONTAINER or (
          isinstance(container, _instance_base.SimpleValue) and
          _isinstance(p, "TypeParameter") and
          p.full_name in container.all_template_names):
        content.append(p.instantiate(self.ctx.root_node, container))
      else:
        content.append(p.instantiate(self.ctx.root_node))
    # Note that we intentionally don't set self._instance to the new tuple,
    # since the tuple will create and register itself with a fresh TupleClass.
    return _instances.Tuple(tuple(content), self.ctx)

  def instantiate(self, node, container=None):
    return self._new_instance(container, node, None).to_variable(node)

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
      index = self.ctx.convert.value_to_constant(
          abstract_utils.get_atomic_value(index_var), (int, slice))
    except abstract_utils.ConversionError:
      pass
    else:
      if isinstance(index, slice):
        if self._instance:
          slice_content = self._instance.pyval[index]
          return node, self.ctx.convert.build_tuple(node, slice_content)
        else:
          # Constructing the tuple directly is faster than calling call_pytd.
          instance = _instance_base.Instance(
              self.ctx.convert.tuple_type, self.ctx)
          node, contained_type = self.ctx.vm.init_class(
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

  def add_slot(self, node, other_var):
    """Implementation of tuple.__add__."""
    try:
      other = abstract_utils.get_atomic_value(other_var)
    except abstract_utils.ConversionError:
      pass
    else:
      if self._instance and _isinstance(other, "Tuple"):
        pyval = self._instance.pyval + other.pyval
        ret = _instances.Tuple(pyval, self.ctx)
        return node, ret.to_variable(node)
    return self.call_pytd(node, "__add__", self.instantiate(node), other_var)
