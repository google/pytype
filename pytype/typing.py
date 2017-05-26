"""Implementation of the types in Python 3's typing.py."""

# pylint's detection of this is error-prone:
# pylint: disable=unpacking-non-sequence


from pytype import abstract
from pytype import overlay
from pytype.pytd import pep484
from pytype.pytd import pytd


class TypingOverlay(overlay.Overlay):
  """A representation of the 'typing' module that allows custom overlays."""

  is_lazy = True  # uses _convert_member

  def __init__(self, vm):
    member_map = typing_overload.copy()
    ast = vm.loader.typing
    for cls in ast.classes:
      _, name = cls.name.rsplit(".", 1)
      if name not in member_map and pytd.IsContainer(cls) and cls.template:
        member_map[name] = TypingContainer
    super(TypingOverlay, self).__init__(vm, "typing", member_map, ast)


class Union(abstract.AnnotationClass):
  """Implementation of typing.Union[...]."""

  def __init__(self, name, vm, options=()):
    super(Union, self).__init__(name, vm)
    self.options = options

  def _build_value(self, node, inner, _):
    return abstract.Union(self.options + inner, self.vm)


class TypingContainer(abstract.AnnotationContainer):

  def __init__(self, name, vm):
    if name in pep484.PEP484_CAPITALIZED:
      pytd_name = "__builtin__." + name.lower()
    else:
      pytd_name = "typing." + name
    base = vm.convert.name_to_value(pytd_name)
    super(TypingContainer, self).__init__(name, vm, base)


class Tuple(TypingContainer):

  def _get_value_info(self, inner, ends_with_ellipsis):
    if not ends_with_ellipsis:
      template = range(len(inner)) + [abstract.T]
      inner += (abstract.merge_values(inner, self.vm),)
      return template, inner, abstract.TupleClass
    else:
      return super(Tuple, self)._get_value_info(inner, ends_with_ellipsis)


class Callable(TypingContainer):
  """Implementation of typing.Callable[...]."""

  def getitem_slot(self, node, slice_var):
    content = self._maybe_extract_tuple(node, slice_var)
    inner, ends_with_ellipsis = self._build_inner(content)
    args = inner[0]
    if isinstance(args, abstract.List) and not args.could_contain_anything:
      inner[0], _ = self._build_inner(args.pyval)
    else:
      if args.cls and any(v.full_name == "__builtin__.list"
                          for v in args.cls.data):
        self.vm.errorlog.invalid_annotation(
            self.vm.frames, args, "Must be constant")
      elif (args is not self.vm.convert.ellipsis and
            not isinstance(args, abstract.Unsolvable)):
        self.vm.errorlog.invalid_annotation(
            self.vm.frames, args,
            "First argument to Callable must be a list of argument types.")
      inner[0] = self.vm.convert.unsolvable
    value = self._build_value(node, tuple(inner), ends_with_ellipsis)
    return node, value.to_variable(node)

  def _get_value_info(self, inner, ends_with_ellipsis):
    if isinstance(inner[0], list):
      template = range(len(inner[0])) + [t.name for t in self.base_cls.template]
      combined_args = abstract.merge_values(inner[0], self.vm, formal=True)
      inner = tuple(inner[0]) + (combined_args,) + inner[1:]
      return template, inner, abstract.Callable
    else:
      return super(Callable, self)._get_value_info(inner, ends_with_ellipsis)


class TypeVarError(Exception):
  """Raised if an error is encountered while initializing a TypeVar."""

  def __init__(self, message, bad_call=None):
    super(TypeVarError, self).__init__(message)
    self.bad_call = bad_call


class TypeVar(abstract.PyTDFunction):
  """Representation of typing.TypeVar, as a function."""

  def __init__(self, name, vm):
    pyval = vm.loader.typing.Lookup("typing._typevar_new")
    f = vm.convert.constant_to_value(pyval, {}, vm.root_cfg_node)
    super(TypeVar, self).__init__(name, f.signatures, pytd.METHOD, vm)

  def _get_class_or_constant(self, var, name, arg_type):
    if arg_type is abstract.Class:
      convert_func = abstract.get_atomic_value
      type_desc = "an unambiguous type"
    else:
      convert_func = abstract.get_atomic_python_constant
      type_desc = "a constant " + arg_type.__name__
    try:
      return convert_func(var, arg_type)
    except abstract.ConversionError:
      raise TypeVarError("%s must be %s" % (name, type_desc))

  def _get_namedarg(self, args, name, arg_type, default_value):
    if name in args.namedargs:
      value = self._get_class_or_constant(args.namedargs[name], name, arg_type)
      if name != "bound":
        self.vm.errorlog.not_supported_yet(
            self.vm.frames, "argument \"%s\" to TypeVar" % name)
      return value
    return default_value

  def _get_typeparam(self, node, args):
    args = args.simplify(node)
    try:
      self._match_args(node, args)
    except abstract.InvalidParameters as e:
      raise TypeVarError("wrong arguments", e.bad_call)
    except abstract.FailedFunctionCall:
      # It is currently impossible to get here, since the only
      # FailedFunctionCall that is not an InvalidParameters is NotCallable.
      raise TypeVarError("initialization failed")
    name = self._get_class_or_constant(args.posargs[0], "name", str)
    constraints = tuple(self._get_class_or_constant(
        c, "constraint", abstract.Class) for c in args.posargs[1:])
    if len(constraints) == 1:
      raise TypeVarError("the number of constraints must be 0 or more than 1")
    bound = self._get_namedarg(args, "bound", abstract.Class, None)
    covariant = self._get_namedarg(args, "covariant", bool, False)
    contravariant = self._get_namedarg(args, "contravariant", bool, False)
    if constraints and bound:
      raise TypeVarError("constraints and a bound are mutually exclusive")
    extra_kwargs = set(args.namedargs) - {"bound", "covariant", "contravariant"}
    if extra_kwargs:
      raise TypeVarError("extra keyword arguments: " + ", ".join(extra_kwargs))
    if args.starargs:
      raise TypeVarError("*args must be a constant tuple")
    if args.starstarargs:
      raise TypeVarError("ambiguous **kwargs not allowed")
    return abstract.TypeParameter(name, self.vm, constraints=constraints,
                                  bound=bound, covariant=covariant,
                                  contravariant=contravariant)

  def call(self, node, _, args):
    """Call typing.TypeVar()."""
    try:
      param = self._get_typeparam(node, args)
    except TypeVarError as e:
      self.vm.errorlog.invalid_typevar(self.vm.frames, e.message, e.bad_call)
      return node, self.vm.convert.unsolvable.to_variable(node)
    return node, param.to_variable(node)


class Cast(abstract.PyTDFunction):
  """Implements typing.cast."""

  def call(self, node, func, args):
    if args.posargs:
      try:
        annot = self.vm.annotations_util.process_annotation_var(
            args.posargs[0], "typing.cast", self.vm.frames, node)
      except self.vm.annotations_util.LateAnnotationError:
        self.vm.errorlog.invalid_annotation(
            self.vm.frames,
            abstract.merge_values(args.posargs[0].data, self.vm),
            "Forward references not allowed in typing.cast.\n"
            "Consider switching to a type comment.")
        annot = self.vm.convert.create_new_unsolvable(node)
      args = args.replace(posargs=(annot,) + args.posargs[1:])
    return super(Cast, self).call(node, func, args)


def build_any(name, vm):
  del name
  return abstract.Unsolvable(vm)


# TODO(kramm): Do a full implementation of this.
def build_namedtuple(name, vm):
  vm.errorlog.not_supported_yet(vm.frames, name)
  return abstract.Unsolvable(vm)


def build_optional(name, vm):
  return Union(name, vm, (vm.convert.none_type.data[0],))


def build_generic(name, vm):
  vm.errorlog.not_supported_yet(vm.frames, name)
  return vm.convert.unsolvable


def build_typechecking(name, vm):
  del name
  return vm.convert.true


def build_cast(name, vm):
  f = vm.lookup_builtin("typing.cast")
  signatures = [abstract.PyTDSignature(name, sig, vm) for sig in f.signatures]
  return Cast(name, signatures, f.kind, vm)


typing_overload = {
    "Any": build_any,
    "Callable": Callable,
    "Generic": build_generic,
    "NamedTuple": build_namedtuple,
    "Optional": build_optional,
    "Tuple": Tuple,
    "TypeVar": TypeVar,
    "Union": Union,
    "TYPE_CHECKING": build_typechecking,
    "cast": build_cast,
}
