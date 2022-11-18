"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence

from typing import Dict as _Dict, Optional as _Optional, Tuple as _Tuple

from pytype import utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import class_mixin
from pytype.abstract import function
from pytype.overlays import named_tuple
from pytype.overlays import overlay
from pytype.overlays import overlay_utils
from pytype.overlays import typed_dict
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.typegraph import cfg


# type alias
Param = overlay_utils.Param


def _is_typing_container(cls: pytd.Class):
  return pytd.IsContainer(cls) and cls.template


class TypingOverlay(overlay.Overlay):
  """A representation of the 'typing' module that allows custom overlays.

  This overlay's member_map is a little different from others'. Members are a
  tuple of a builder method and the lowest runtime version that supports that
  member. This allows us to reuse the same code for both typing and
  typing_extensions and to direct users to typing_extensions when they attempt
  to import a typing member in a too-low runtime version.
  """

  def __init__(self, ctx):
    # Make sure we have typing available as a dependency
    member_map = typing_overlay.copy()
    ast = ctx.loader.typing
    for cls in ast.classes:
      _, name = cls.name.rsplit(".", 1)
      if name not in member_map and _is_typing_container(cls):
        member_map[name] = (overlay.build(name, TypingContainer), None)
    super().__init__(ctx, "typing", member_map, ast)

  # pytype: disable=signature-mismatch  # overriding-parameter-type-checks
  def _convert_member(
      self,
      name: str,
      member: _Tuple[overlay.BuilderType, _Tuple[int, int]],
      subst: _Optional[_Dict[str, cfg.Variable]] = None) -> cfg.Variable:
  # pytype: enable=signature-mismatch  # overriding-parameter-type-checks
    builder, lowest_supported_version = member
    if (lowest_supported_version and
        self.ctx.python_version < lowest_supported_version and
        name not in _unsupported_members):
      # For typing constructs that are being imported in a runtime version that
      # does not support them but are supported by pytype, we print a hint to
      # import them from typing_extensions instead.
      details = (f"Import {name} from typing_extensions in Python versions "
                 f"before {utils.format_version(lowest_supported_version)}.")
      return not_supported_yet(name, self.ctx, details=details).to_variable(
          self.ctx.root_node)
    return super()._convert_member(name, builder, subst)


class Redirect(overlay.Overlay):
  """Base class for overlays that redirect to typing."""

  def __init__(self, module_name, aliases, ctx):
    ast = ctx.loader.import_name(module_name)
    member_map = {k: _build(v) for k, v in aliases.items()}
    for pyval in ast.aliases + ast.classes + ast.constants + ast.functions:
      # Any public members that are not explicitly implemented are unsupported.
      _, name = pyval.name.rsplit(".", 1)
      if name.startswith("_") or name in member_map:
        continue
      if name in typing_overlay:
        member_map[name] = typing_overlay[name][0]
      elif f"typing.{name}" in ctx.loader.typing:
        member_map[name] = _build(f"typing.{name}")
      elif name not in member_map:
        member_map[name] = _build_not_supported_yet(name, ast)
    super().__init__(ctx, module_name, member_map, ast)


def _build(name):
  def resolve(ctx):
    ast = ctx.loader.typing
    pytd_val = ast.Lookup(name)
    if isinstance(pytd_val, pytd.Class) and _is_typing_container(pytd_val):
      return TypingContainer(name.rsplit(".", 1)[-1], ctx)
    pytd_type = pytd.ToType(ast.Lookup(name), True, True, True)
    return ctx.convert.constant_to_value(pytd_type)
  return resolve


def _build_not_supported_yet(name, ast):
  return lambda ctx: not_supported_yet(name, ctx, ast=ast)


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


class Final(abstract.AnnotationClass):
  """Implementation of typing.Final[T]."""

  def _build_value(self, node, inner, ellipses):
    self.ctx.errorlog.invalid_ellipses(self.ctx.vm.frames, ellipses, self.name)
    if len(inner) != 1:
      error = "typing.Final must wrap a single type"
      self.ctx.errorlog.invalid_annotation(self.ctx.vm.frames, self, error)
    return abstract.FinalAnnotation(inner[0], self.ctx)

  def instantiate(self, node, container=None):
    self.ctx.errorlog.invalid_final_type(self.ctx.vm.frames)
    return self.ctx.new_unsolvable(node)


class TypingContainer(abstract.AnnotationContainer):

  def __init__(self, name, ctx):
    if name in pep484.TYPING_TO_BUILTIN:
      pytd_name = "builtins." + pep484.TYPING_TO_BUILTIN[name]
    else:
      pytd_name = "typing." + name
    base = ctx.convert.name_to_value(pytd_name)
    super().__init__(name, ctx, base)


class Tuple(TypingContainer):
  """Implementation of typing.Tuple."""

  def _get_value_info(self, inner, ellipses, allowed_ellipses=frozenset()):
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
    if inner and getattr(inner[-1], "full_name", None) == "typing.TypeGuard":
      if isinstance(inner[0], list) and len(inner[0]) < 1:
        self.ctx.errorlog.invalid_annotation(
            self.ctx.vm.frames, args,
            "A TypeGuard function must have at least one required parameter")
      if not isinstance(inner[-1], abstract.ParameterizedClass):
        self.ctx.errorlog.invalid_annotation(
            self.ctx.vm.frames, inner[-1], "Expected 1 parameter, got 0")
    value = self._build_value(node, tuple(inner), ellipses)
    return node, value.to_variable(node)

  def _get_value_info(self, inner, ellipses, allowed_ellipses=frozenset()):
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

  def call(self, node, _, args, alias_map=None):
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

  def call(self, node, func, args, alias_map=None):
    if args.posargs:
      _, value = self.ctx.annotation_utils.extract_and_init_annotation(
          node, "typing.cast", args.posargs[0])
      return node, value
    return super().call(node, func, args)


class NoReturn(abstract.Singleton):
  """Implements typing.NoReturn as a singleton."""

  def __init__(self, ctx):
    super().__init__("NoReturn", ctx)
    # Sets cls to Type so that runtime usages of NoReturn don't cause pytype to
    # think that NoReturn is being used illegally in type annotations.
    self.cls = ctx.convert.type_type


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

  def call(self, node, func, args, alias_map=None):
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
    props = class_mixin.ClassBuilderProperties(
        name_var=name_arg,
        bases=[type_arg],
        class_dict_var=members.to_variable(node))
    return self.ctx.make_class(node, props)


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


class FinalDecorator(abstract.PyTDFunction):
  """Implementation of typing.final."""

  def call(self, node, unused_func, args):
    """Marks that the given function is final."""
    self.match_args(node, args)
    arg = args.posargs[0]
    for obj in arg.data:
      if self._can_be_final(obj):
        obj.final = True
      else:
        self.ctx.errorlog.bad_final_decorator(self.ctx.vm.frames, obj)
    return node, arg

  def _can_be_final(self, obj):
    if isinstance(obj, abstract.Class):
      return True
    if isinstance(obj, abstract.Function):
      return obj.is_method
    return False


class Generic(TypingContainer):
  """Implementation of typing.Generic."""

  def _get_value_info(self, inner, ellipses, allowed_ellipses=frozenset()):
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


def not_supported_yet(name, ctx, *, ast=None, details=None):
  ast = ast or ctx.loader.typing
  full_name = f"{ast.name}.{name}"
  ctx.errorlog.not_supported_yet(ctx.vm.frames, full_name, details=details)
  pytd_type = pytd.ToType(ast.Lookup(full_name), True, True, True)
  return ctx.convert.constant_to_value(pytd_type, node=ctx.root_node)


def build_any(ctx):
  return ctx.convert.unsolvable


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


def build_final_decorator(ctx):
  return FinalDecorator.make("final", ctx, "typing")


# name -> lowest_supported_version
_unsupported_members = {
    "Concatenate": (3, 10),
    "ParamSpec": (3, 10),
    "is_typeddict": (3, 10),
    "Self": (3, 11),
}


# name -> (builder, lowest_supported_version)
typing_overlay = {
    "Annotated": (overlay.build("Annotated", Annotated), (3, 9)),
    "Any": (build_any, None),
    "Callable": (overlay.build("Callable", Callable), None),
    "final": (build_final_decorator, (3, 8)),
    "Final": (overlay.build("Final", Final), (3, 8)),
    "Generic": (overlay.build("Generic", Generic), None),
    "Literal": (overlay.build("Literal", Literal), (3, 8)),
    "NamedTuple": (named_tuple.NamedTupleClassBuilder, None),
    "NewType": (build_newtype, None),
    "NoReturn": (build_noreturn, None),
    "Optional": (overlay.build("Optional", Optional), None),
    "Tuple": (overlay.build("Tuple", Tuple), None),
    "TypeGuard": (_build("typing.TypeGuard"), (3, 10)),
    "TypeVar": (build_typevar, None),
    "TypedDict": (typed_dict.TypedDictBuilder, (3, 8)),
    "Union": (Union, None),
    "TYPE_CHECKING": (build_typechecking, None),
    "cast": (build_cast, None),
    "overload": (build_overload, None),
    **{k: (overlay.build(k, not_supported_yet), v)
       for k, v in _unsupported_members.items()}
}
