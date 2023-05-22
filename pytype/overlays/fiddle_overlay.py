"""Implementation of types from the fiddle library."""

from typing import Any, Dict, Tuple

from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.overlays import classgen
from pytype.overlays import overlay
from pytype.pytd import pytd


# Type aliases so we aren't importing stuff purely for annotations
Node = Any
Variable = Any


# Cache instances, so that we don't generate two different classes when
# Config[Foo] is used in two separate places. We use a tuple of the abstract
# class of Foo and a string (either "Config" or "Partial") as a key and store
# the generated Buildable instance (either Config or Partial) as a value.
_INSTANCE_CACHE: Dict[Tuple[Node, abstract.Class, str], abstract.Instance] = {}


class FiddleOverlay(overlay.Overlay):
  """A custom overlay for the 'fiddle' module."""

  def __init__(self, ctx):
    """Initializes the FiddleOverlay.

    This function loads the AST for the fiddle module, which is used to
    access type information for any members that are not explicitly provided by
    the overlay. See get_attribute in attribute.py for how it's used.

    Args:
      ctx: An instance of context.Context.
    """
    if ctx.options.use_fiddle_overlay:
      member_map = {
          "Config": ConfigBuilder,
          "Partial": PartialBuilder,
      }
    else:
      member_map = {}

    ast = ctx.loader.import_name("fiddle")
    super().__init__(ctx, "fiddle", member_map, ast)


class BuildableBuilder(abstract.PyTDClass, mixin.HasSlots):
  """Factory for creating fiddle.Config classes."""

  _NAME_INDEX = 0
  BUILDABLE_NAME = ""

  def __init__(self, ctx):
    assert self.BUILDABLE_NAME, "Only instantiate BuildableBuilder subclasses."
    fiddle_ast = ctx.loader.import_name("fiddle")
    pytd_cls = fiddle_ast.Lookup(f"fiddle.{self.BUILDABLE_NAME}")
    # fiddle.Config/Partial loads as a LateType, convert to pytd.Class
    if isinstance(pytd_cls, pytd.Constant):
      pytd_cls = ctx.convert.constant_to_value(pytd_cls).pytd_cls
    super().__init__(self.BUILDABLE_NAME, pytd_cls, ctx)
    mixin.HasSlots.init_mixin(self)
    self.set_native_slot("__getitem__", self.getitem_slot)
    # For consistency with the rest of the overlay
    self.fiddle_type_name = self.BUILDABLE_NAME

  def __repr__(self):
    return f"Fiddle{self.BUILDABLE_NAME}"

  @classmethod
  def generate_name(cls):
    cls._NAME_INDEX += 1
    return f"{cls.BUILDABLE_NAME}_{cls._NAME_INDEX}"

  def _match_pytd_init(self, node, init_var, args):
    init = init_var.data[0]
    try:
      init.match_args(node, args)
    except function.FailedFunctionCall as e:
      if not isinstance(e, function.MissingParameter):
        # We don't surface missing parameter errors because fiddle config
        # objects have defaults for all fields.
        self.ctx.errorlog.invalid_function_call(self.ctx.vm.frames, e)

  def _match_interpreter_init(self, node, init_var, args):
    # Buildables support partial initialization, so give every parameter a
    # default when matching __init__.
    init = init_var.data[0]
    for k in init.signature.param_names:
      init.signature.defaults[k] = self.ctx.new_unsolvable(node)
    # TODO(mdemello): We are calling the function and discarding the return
    # value, when ideally we should just call function.match_all_args().
    function.call_function(self.ctx, node, init_var, args)

  def _make_init_args(self, node, underlying, args, kwargs):
    """Unwrap Config instances for arg matching."""
    def unwrap(arg_var):
      # If an arg has a Config object, just use its underlying type and don't
      # bother with the rest of the bindings (assume strict arg matching)
      for d in arg_var.data:
        if isinstance(d, Buildable):
          if isinstance(d.underlying, abstract.Function):
            # If the underlying type is a function, do not try to instantiate it
            return self.ctx.new_unsolvable(node)
          else:
            return d.underlying.instantiate(node)
      return arg_var
    new_args = (underlying.instantiate(node),)
    new_args += tuple(unwrap(arg) for arg in args[1:])
    new_kwargs = {k: unwrap(arg) for k, arg in kwargs.items()}
    return function.Args(posargs=new_args, namedargs=new_kwargs)

  def _check_init_args(self, node, underlying, args, kwargs):
    # Configs can be initialized either with no args, e.g. Config(Class) or with
    # initial values, e.g. Config(Class, x=10, y=20). We need to check here that
    # the extra args match the underlying __init__ signature.
    if len(args) > 1 or kwargs:
      _, init_var = self.ctx.attribute_handler.get_attribute(
          node, underlying, "__init__")
      if abstract_utils.is_dataclass(underlying):
        # Only do init matching for dataclasses for now
        args = self._make_init_args(node, underlying, args, kwargs)
        init = init_var.data[0]
        if isinstance(init, abstract.PyTDFunction):
          self._match_pytd_init(node, init_var, args)
        else:
          self._match_interpreter_init(node, init_var, args)

  def new_slot(
      self, node, unused_cls, *args, **kwargs
  ) -> Tuple[Node, abstract.Instance]:
    """Create a Config or Partial instance from args."""

    underlying = args[0].data[0]
    self._check_init_args(node, underlying, args, kwargs)

    # Now create the Config object.
    node, ret = make_instance(self.BUILDABLE_NAME, underlying, node, self.ctx)
    return node, ret.to_variable(node)

  def getitem_slot(self, node, index_var) -> Tuple[Node, abstract.Instance]:
    """Specialize the generic class with the value of index_var."""

    underlying = index_var.data[0]
    ret = BuildableType(self.BUILDABLE_NAME, underlying, self.ctx)
    return node, ret.to_variable(node)

  def get_own_new(self, node, value) -> Tuple[Node, Variable]:
    new = abstract.NativeFunction("__new__", self.new_slot, self.ctx)
    return node, new.to_variable(node)


class ConfigBuilder(BuildableBuilder):
  """Subclasses PyTDClass(fiddle.Config)."""

  BUILDABLE_NAME = "Config"


class PartialBuilder(BuildableBuilder):
  """Subclasses PyTDClass(fiddle.Partial)."""

  BUILDABLE_NAME = "Partial"


class BuildableType(abstract.ParameterizedClass):
  """Base generic class for fiddle.Config and fiddle.Partial."""

  def __init__(self, fiddle_type_name, underlying, ctx, template=None):
    if fiddle_type_name == "Config":
      base_cls = ConfigBuilder(ctx)
    else:
      base_cls = PartialBuilder(ctx)

    if isinstance(underlying, abstract.Function):
      # We don't support functions for now, but falling back to Any here gets us
      # as much of the functionality as possible.
      formal_type_parameters = {abstract_utils.T: ctx.convert.unsolvable}
    else:
      # Classes and TypeVars
      formal_type_parameters = {abstract_utils.T: underlying}

    super().__init__(base_cls, formal_type_parameters, ctx, template)  # pytype: disable=wrong-arg-types
    self.fiddle_type_name = fiddle_type_name
    self.underlying = underlying

  def replace(self, inner_types):
    inner_types = dict(inner_types)
    new_underlying = inner_types[abstract_utils.T]
    typ = self.__class__
    return typ(self.fiddle_type_name, new_underlying, self.ctx, self.template)

  def instantiate(self, node, container=None):
    _, ret = make_instance(
        self.fiddle_type_name, self.underlying, node, self.ctx)
    return ret.to_variable(node)

  def __repr__(self):
    return f"{self.fiddle_type_name}Type[{self.underlying}]"


class Buildable(abstract.Instance):
  def __init__(self, fiddle_type_name, cls, ctx, container=None):
    super().__init__(cls, ctx, container)
    self.fiddle_type_name = fiddle_type_name
    self.underlying = None


class Config(Buildable):
  """An instantiation of a fiddle.Config with a particular template."""

  def __init__(self, *args, **kwargs):
    super().__init__("Config", *args, **kwargs)


class Partial(Buildable):
  """An instantiation of a fiddle.Partial with a particular template."""

  def __init__(self, *args, **kwargs):
    super().__init__("Partial", *args, **kwargs)


def _convert_type(typ, subst, ctx):
  """Helper function for recursive type conversion of fields."""
  if isinstance(typ, abstract.TypeParameter) and typ.name in subst:
    # TODO(mdemello): Handle typevars in unions.
    typ = subst[typ.name]
  new_typ = BuildableType("Config", typ, ctx)
  return abstract.Union([new_typ, typ], ctx)


def _make_fields(typ, ctx):
  """Helper function for recursive type conversion of fields."""
  if isinstance(typ, abstract.ParameterizedClass):
    subst = typ.formal_type_parameters
    typ = typ.base_cls
  else:
    subst = {}
  if abstract_utils.is_dataclass(typ):
    fields = [
        classgen.Field(x.name, _convert_type(x.typ, subst, ctx), x.default)
        for x in typ.metadata["__dataclass_fields__"]
    ]
    return fields
  return []


def make_instance(
    subclass_name: str, underlying: abstract.Class, node, ctx
) -> Tuple[Node, abstract.BaseValue]:
  """Generate a Buildable instance from an underlying template class."""

  if subclass_name not in ("Config", "Partial"):
    raise ValueError(f"Unexpected instance class: {subclass_name}")

  # We include the root node in case the cache is shared between multiple runs.
  cache_key = (ctx.root_node, underlying, subclass_name)
  if cache_key in _INSTANCE_CACHE:
    return node, _INSTANCE_CACHE[cache_key]

  instance_class = {"Config": Config, "Partial": Partial}[subclass_name]
  # Create the specialized class Config[underlying] or Partial[underlying]
  try:
    cls = BuildableType(subclass_name, underlying, ctx)
  except KeyError:
    # We are in the middle of constructing the fiddle ast; fiddle.Config doesn't
    # exist yet
    return node, ctx.convert.unsolvable
  # Now create the instance, setting its class to `cls`
  obj = instance_class(cls, ctx)
  obj.underlying = underlying
  fields = _make_fields(underlying, ctx)
  for f in fields:
    obj.members[f.name] = f.typ.instantiate(node)
  # Add a per-instance annotations dict so setattr can be typechecked.
  obj.members["__annotations__"] = classgen.make_annotations_dict(
      fields, node, ctx)
  _INSTANCE_CACHE[cache_key] = obj
  return node, obj


def is_fiddle_buildable_pytd(cls: pytd.Class) -> bool:
  # We need the awkward check for the full name because while fiddle reexports
  # the class as fiddle.Config, we expand that in inferred pyi files to
  # fiddle._src.config.Config
  return cls.name.startswith("fiddle.") and (
      cls.name.endswith(".Config") or cls.name.endswith(".Partial"))


def get_fiddle_buildable_subclass(cls: pytd.Class) -> str:
  if cls.name.endswith(".Config"):
    return "Config"
  if cls.name.endswith(".Partial"):
    return "Partial"
  raise ValueError(f"Unexpected {cls.name} when computing fiddle Buildable "
                   "subclass; allowed suffixes are `.Config`, and `.Partial`.")
