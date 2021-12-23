"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence

from pytype import overlay
from pytype import overlay_utils
from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.overlays import named_tuple
from pytype.overlays import typed_dict
from pytype.pytd import pep484
from pytype.pytd import pytd


# type alias
Param = overlay_utils.Param


class TypingOverlay(overlay.Overlay):
  """A representation of the 'typing' module that allows custom overlays."""

  def __init__(self, ctx):
    # Make sure we have typing available as a dependency
    member_map = typing_overlay.copy()
    ast = ctx.loader.typing
    for cls in ast.classes:
      _, name = cls.name.rsplit(".", 1)
      if name not in member_map and pytd.IsContainer(cls) and cls.template:
        member_map[name] = overlay.build(name, TypingContainer)
    super().__init__(ctx, "typing", member_map, ast)


class Union(abstract.AnnotationClass):
  """Implementation of typing.Union[...]."""

  def __init__(self, ctx, options=()):
    super().__init__("Union", ctx)
    self.options = options

  def _build_value(self, node, inner, ellipses):
    self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames, ellipses, self.name)
    return abstract.Union(self.options + inner, self.ctx)


class Annotated(abstract.AnnotationClass):
  """Implementation of typing.Annotated[T, *annotations]."""

  def _build_value(self, node, inner, ellipses):
    self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames, ellipses, self.name)
    if len(inner) == 1:
      error = "typing.Annotated must have at least 1 annotation"
      self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, self, error)
    # discard annotations
    return inner[0]


class TypingContainer(abstract.AnnotationContainer):

  def __init__(self, name, ctx):
    if name in pep484.PEP484_CAPITALIZED:
      pytd_name = "builtins." + name.lower()
    else:
      pytd_name = "typing." + name
    base = ctx.convert.name_to_value(pytd_name)
    super().__init__(name, ctx, base)


class Tuple(TypingContainer):
  """Implementation of typing.Tuple."""

  def _get_value_info(self, inner, ellipses):
    if ellipses:
      # An ellipsis may appear at the end of the parameter list as long as it is
      # not the only parameter.
      return super()._get_value_info(
          inner, ellipses, allowed_ellipses={len(inner) - 1} - {0})
    else:
      template = list(range(len(inner))) + [abstract_utils.T]
      inner += (self.ctx.convert.merge_values(inner),)
      return template, inner, abstract.TupleClass


class Callable(TypingContainer):
  """Implementation of typing.Callable[...]."""

  def getitem_slot(self, node, slice_var):
    content = abstract_utils.maybe_extract_tuple(slice_var)
    inner, ellipses = self._build_inner(content)
    args = inner[0]
    if abstract_utils.is_concrete_list(args):
      inner[0], inner_ellipses = self._build_inner(args.pyval)
      self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames, inner_ellipses,
                                         args.name)
    else:
      if args.cls.full_name == "builtins.list":
        self.ctx.errorlog.ambiguous_annotation(self.ctx.vm.frames, [args])
      elif 0 not in ellipses or not isinstance(args, abstract.Unsolvable):
        self.ctx.errorlog.invalid_annotation(
            self.ctx.vm.frames, args,
            ("First argument to Callable must be a list"
             " of argument types or ellipsis."))
      inner[0] = self.ctx.convert.unsolvable
    value = self._build_value(node, tuple(inner), ellipses)
    return node, value.to_variable(node)

  def _get_value_info(self, inner, ellipses):
    if isinstance(inner[0], list):
      template = (list(range(len(inner[0]))) +
                  [t.name for t in self.base_cls.template])
      combined_args = self.ctx.convert.merge_values(inner[0])
      inner = tuple(inner[0]) + (combined_args,) + inner[1:]
      self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames, ellipses,
                                         self.name)
      return template, inner, abstract.CallableClass
    else:
      # An ellipsis may take the place of the ARGS list.
      return super()._get_value_info(inner, ellipses, allowed_ellipses={0})


class TypeVarError(Exception):
  """Raised if an error is encountered while initializing a TypeVar."""

  def __init__(self, message, bad_call=None):
    super().__init__(message)
    self.bad_call = bad_call


class TypeVar(abstract.PyTDFunction):
  """Representation of typing.TypeVar, as a function."""

  def _get_constant(self, var, name, arg_type, arg_type_desc=None):
    try:
      ret = abstract_utils.get_atomic_python_constant(var, arg_type)
    except abstract_utils.ConversionError as e:
      desc = arg_type_desc or f"a constant {arg_type.__name__}"
      raise TypeVarError(f"{name} must be {desc}") from e
    return ret

  def _get_annotation(self, node, var, name):
    with self.ctx.errorlog.checkpoint() as record:
      annot = self.ctx.annotation_utils.extract_annotation(
          node, var, name, self.ctx.vm.simple_stack())
    if record.errors:
      raise TypeVarError("\n".join(error.message for error in record.errors))
    return annot

  def _get_namedarg(self, node, args, name, default_value):
    if name not in args.namedargs:
      return default_value
    if name == "bound":
      return self._get_annotation(node, args.namedargs[name], name)
    else:
      ret = self._get_constant(args.namedargs[name], name, bool)
      # This error is logged only if _get_constant succeeds.
      self.ctx.errorlog.not_supported_yet(self.ctx.vm.frames,
                                          f"argument \"{name}\" to TypeVar")
      return ret

  def _get_typeparam(self, node, args):
    args = args.simplify(node, self.ctx)
    try:
      self.match_args(node, args)
    except function.InvalidParameters as e:
      raise TypeVarError("wrong arguments", e.bad_call) from e
    except function.FailedFunctionCall as e:
      # It is currently impossible to get here, since the only
      # FailedFunctionCall that is not an InvalidParameters is NotCallable.
      raise TypeVarError("initialization failed") from e
    name = self._get_constant(args.posargs[0], "name", str,
                              arg_type_desc="a constant str")
    constraints = tuple(
        self._get_annotation(node, c, "constraint") for c in args.posargs[1:])
    if len(constraints) == 1:
      raise TypeVarError("the number of constraints must be 0 or more than 1")
    bound = self._get_namedarg(node, args, "bound", None)
    covariant = self._get_namedarg(node, args, "covariant", False)
    contravariant = self._get_namedarg(node, args, "contravariant", False)
    if constraints and bound:
      raise TypeVarError("constraints and a bound are mutually exclusive")
    extra_kwargs = set(args.namedargs) - {"bound", "covariant", "contravariant"}
    if extra_kwargs:
      raise TypeVarError("extra keyword arguments: " + ", ".join(extra_kwargs))
    if args.starargs:
      raise TypeVarError("*args must be a constant tuple")
    if args.starstarargs:
      raise TypeVarError("ambiguous **kwargs not allowed")
    return abstract.TypeParameter(
        name,
        self.ctx,
        constraints=constraints,
        bound=bound,
        covariant=covariant,
        contravariant=contravariant)

  def call(self, node, _, args):
    """Call typing.TypeVar()."""
    try:
      param = self._get_typeparam(node, args)
    except TypeVarError as e:
      self.ctx.errorlog.invalid_typevar(self.ctx.vm.frames, utils.message(e),
                                        e.bad_call)
      return node, self.ctx.new_unsolvable(node)
    return node, param.to_variable(node)


class Cast(abstract.PyTDFunction):
  """Implements typing.cast."""

  def call(self, node, func, args):
    if args.posargs:
      _, value = self.ctx.annotation_utils.extract_and_init_annotation(
          node, "typing.cast", args.posargs[0])
      return node, value
    return super().call(node, func, args)


class NoReturn(abstract.Singleton):
  """Implements typing.NoReturn as a singleton."""

  def __init__(self, ctx):
    super().__init__("NoReturn", ctx)


def build_any(ctx):
  return ctx.convert.unsolvable


class NewType(abstract.PyTDFunction):
  """Implementation of typing.NewType as a function."""

  def __init__(self, name, signatures, kind, ctx):
    super().__init__(name, signatures, kind, ctx)
    assert len(self.signatures) == 1, "NewType has more than one signature."
    signature = self.signatures[0].signature
    self._name_arg_name = signature.param_names[0]
    self._type_arg_name = signature.param_names[1]
    self._internal_name_counter = 0

  @property
  def internal_name_counter(self):
    val = self._internal_name_counter
    self._internal_name_counter += 1
    return val

  def call(self, node, func, args):
    args = args.simplify(node, self.ctx)
    self.match_args(node, args, match_all_views=True)
    # As long as the types match we do not really care about the actual
    # class name. But, if we have a string literal value as the name arg,
    # we will use it.
    name_arg = args.namedargs.get(self._name_arg_name) or args.posargs[0]
    try:
      _ = abstract_utils.get_atomic_python_constant(name_arg, str)
    except abstract_utils.ConversionError:
      name_arg = self.ctx.convert.constant_to_var(
          f"_NewType_Internal_Class_Name_{self.internal_name_counter}_")
    type_arg = args.namedargs.get(self._type_arg_name) or args.posargs[1]
    try:
      type_value = abstract_utils.get_atomic_value(type_arg)
    except abstract_utils.ConversionError:
      # We need the type arg to be an atomic value. If not, we just
      # silently return unsolvable.
      return node, self.ctx.new_unsolvable(node)
    value_arg_name = "val"
    constructor = overlay_utils.make_method(
        self.ctx,
        node,
        name="__init__",
        params=[Param(value_arg_name, type_value)])
    members = abstract.Dict(self.ctx)
    members.set_str_item(node, "__init__", constructor)
    return self.ctx.make_class(node, name_arg, (type_arg,),
                               members.to_variable(node), None)


class Overload(abstract.PyTDFunction):
  """Implementation of typing.overload."""

  def call(self, node, unused_func, args):
    """Marks that the given function is an overload."""
    self.match_args(node, args)

    # Since we have only 1 argument, it's easy enough to extract.
    func_var = args.posargs[0] if args.posargs else args.namedargs["func"]

    for func in func_var.data:
      if isinstance(func, abstract.INTERPRETER_FUNCTION_TYPES):
        func.is_overload = True
        self.ctx.vm.frame.overloads[func.name].append(func)

    return node, func_var


class Generic(TypingContainer):
  """Implementation of typing.Generic."""

  def _get_value_info(self, inner, ellipses):
    template, inner = abstract_utils.build_generic_template(inner, self)
    return template, inner, abstract.ParameterizedClass


class Optional(abstract.AnnotationClass):
  """Implementation of typing.Optional."""

  def _build_value(self, node, inner, ellipses):
    self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames, ellipses, self.name)
    if len(inner) != 1:
      error = "typing.Optional can only contain one type parameter"
      self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, self, error)
    return abstract.Union((self.ctx.convert.none_type,) + inner, self.ctx)


class Literal(TypingContainer):
  """Implementation of typing.Literal."""

  def _build_value(self, node, inner, ellipses):
    values = []
    errors = []
    for i, param in enumerate(inner):
      # TODO(b/173742489): Once the enum overlay is enabled, we should
      # stop allowing unsolvable and handle enums here.
      if (param == self.ctx.convert.none or
          isinstance(param, abstract.LiteralClass) or
          param == self.ctx.convert.unsolvable and i not in ellipses):
        value = param
      elif (isinstance(param, abstract.ConcreteValue) and
            isinstance(param.pyval, (int, str, bytes))):
        value = abstract.LiteralClass(param, self.ctx)
      elif isinstance(param, abstract.Instance) and param.cls.is_enum:
        value = abstract.LiteralClass(param, self.ctx)
      else:
        if i in ellipses:
          invalid_param = "..."
        else:
          invalid_param = param.name
        errors.append((invalid_param, i))
        value = self.ctx.convert.unsolvable
      values.append(value)
    if errors:
      self.ctx.errorlog.invalid_annotation(
          self.ctx.vm.frames, self,
          "\n".join("Bad parameter %r at index %d" % e for e in errors))
    return self.ctx.convert.merge_values(values)


def not_supported_yet(name, ctx):
  ctx.errorlog.not_supported_yet(ctx.vm.frames, "typing." + name)
  return ctx.convert.unsolvable


def build_namedtuple(ctx):
  if ctx.python_version < (3, 6):
    return named_tuple.NamedTupleFuncBuilder.make(ctx)
  else:
    return named_tuple.NamedTupleClassBuilder(ctx)


def build_typeddict(ctx):
  if ctx.options.enable_typed_dicts:
    return typed_dict.TypedDictBuilder(ctx)
  else:
    return not_supported_yet("TypedDict", ctx)


def build_newtype(ctx):
  return NewType.make("NewType", ctx, "typing")


def build_noreturn(ctx):
  return ctx.convert.no_return


def build_overload(ctx):
  return Overload.make("overload", ctx, "typing")


def build_typevar(ctx):
  return TypeVar.make("TypeVar", ctx, "typing", pyval_name="_typevar_new")


def build_typechecking(ctx):
  return ctx.convert.true


def build_cast(ctx):
  return Cast.make("cast", ctx, "typing")


def build_final(ctx):
  ctx.errorlog.not_supported_yet(ctx.vm.frames, "typing.final")
  return ctx.convert.name_to_value("typing.final")


typing_overlay = {
    "Annotated": overlay.build("Annotated", Annotated),
    "Any": build_any,
    "Callable": overlay.build("Callable", Callable),
    "final": build_final,
    "Generic": overlay.build("Generic", Generic),
    "Literal": overlay.build("Literal", Literal),
    "NamedTuple": build_namedtuple,
    "NewType": build_newtype,
    "NoReturn": build_noreturn,
    "Optional": overlay.build("Optional", Optional),
    "Tuple": overlay.build("Tuple", Tuple),
    "TypeVar": build_typevar,
    "TypedDict": build_typeddict,
    "Union": Union,
    "TYPE_CHECKING": build_typechecking,
    "cast": build_cast,
    "overload": build_overload,
}
