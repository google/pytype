"""Utilities for abstract.py."""

import collections
from collections.abc import Generator, Iterable, Mapping, Sequence
import dataclasses
import logging
from typing import Any, TYPE_CHECKING, TypeGuard

from pytype import datatypes
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils


if TYPE_CHECKING:
  from pytype import context  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype import state  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _base  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _classes  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _function_base  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _instance_base  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _instances  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import _typing  # pylint: disable=g-bad-import-order,g-import-not-at-top
  from pytype.abstract import class_mixin  # pylint: disable=g-bad-import-order,g-import-not-at-top

log: logging.Logger = logging.getLogger(__name__)

# Type parameter names matching the ones in builtins.pytd and typing.pytd.
T = "_T"
T2 = "_T2"
K = "_K"
V = "_V"
ARGS = "_ARGS"
RET = "_RET"

# TODO(rechen): Stop supporting all variants except _HAS_DYNAMIC_ATTRIBUTES.
DYNAMIC_ATTRIBUTE_MARKERS: list[str] = [
    "HAS_DYNAMIC_ATTRIBUTES",
    "_HAS_DYNAMIC_ATTRIBUTES",
    "has_dynamic_attributes",
]

# Names defined on every module/class that should be ignored in most cases.
TOP_LEVEL_IGNORE: frozenset[str] = frozenset({
    "__builtins__",
    "__doc__",
    "__file__",
    "__future__",
    "__module__",
    "__name__",
    "__annotations__",
})
CLASS_LEVEL_IGNORE: frozenset[str] = frozenset({
    "__builtins__",
    "__class__",
    "__module__",
    "__name__",
    "__qualname__",
    "__slots__",
    "__annotations__",
})

TYPE_GUARDS: set[str] = {"typing.TypeGuard", "typing.TypeIs"}


# A dummy container object for use in instantiating type parameters.
# A container is needed to preserve type parameter names for error messages
# and for sub_(one_)annotation(s). The matcher also uses function signatures and
# callable types as dummy containers. We wrap them in DummyContainer instances
# so that dummy containers have a consistent type. It's not strictly necessary
# to keep the wrapped object around, but it makes debugging easier.
class DummyContainer:

  def __init__(self, container):
    self.container = container


DUMMY_CONTAINER: DummyContainer = DummyContainer(None)


class ConversionError(ValueError):
  pass


class EvaluationError(Exception):
  """Used to signal an errorlog error during type name evaluation."""

  @property
  def errors(self):
    return self.args

  @property
  def details(self):
    return "\n".join(error.message for error in self.errors)


class GenericTypeError(Exception):
  """The error for user-defined generic types."""

  def __init__(self, annot, error) -> None:
    super().__init__(annot, error)
    self.annot = annot
    self.error = error


class ModuleLoadError(Exception):
  """Signal an error when trying to lazily load a submodule."""


class AsInstance:
  """Wrapper, used for marking things that we want to convert to an instance."""

  def __init__(self, cls: pytd.TypeU) -> None:
    self.cls = cls


class AsReturnValue(AsInstance):
  """Specially mark return values, to handle Never properly."""


# For lazy evaluation of ParameterizedClass.formal_type_parameters
@dataclasses.dataclass(eq=True, frozen=True)
class LazyFormalTypeParameters:
  template: Sequence[Any]
  parameters: Sequence[pytd.Node]
  subst: dict[str, cfg.Variable]


class Local:
  """A possibly annotated local variable."""

  def __init__(
      self,
      node: cfg.CFGNode,
      op: opcodes.Opcode | None,
      typ: "_base.BaseValue | None",
      orig: cfg.Variable | None,
      ctx: "context.Context",
  ):
    self._ops: list[opcodes.Opcode | None] = [op]
    self.final = False
    if typ:
      self.typ = ctx.program.NewVariable([typ], [], node)
    else:
      # Creating too many variables bloats the typegraph, hurting performance,
      # so we use None instead of an empty variable.
      self.typ = None
    self.orig = orig
    self.ctx = ctx

  @classmethod
  def merge(
      cls,
      node: cfg.CFGNode,
      op: opcodes.Opcode,
      local1: "Local",
      local2: "Local",
  ) -> "Local":
    """Merges two locals."""
    ctx = local1.ctx
    typ_values = set()
    for typ in [local1.typ, local2.typ]:
      if typ:
        typ_values.update(typ.Data(node))
    typ = ctx.convert.merge_values(typ_values) if typ_values else None
    if local1.orig and local2.orig:
      orig = ctx.program.NewVariable()
      orig.PasteVariable(local1.orig, node)
      orig.PasteVariable(local2.orig, node)
    else:
      orig = local1.orig or local2.orig
    return cls(node, op, typ, orig, ctx)

  def __repr__(self) -> str:
    return f"Local(typ={self.typ}, orig={self.orig}, final={self.final})"

  @property
  def stack(self) -> "tuple[state.SimpleFrame, ...]":
    return self.ctx.vm.simple_stack(self._ops[-1])

  @property
  def last_update_op(self) -> opcodes.Opcode | None:
    return self._ops[-1]

  def update(
      self,
      node: cfg.CFGNode,
      op: opcodes.Opcode,
      typ: cfg.Variable,
      orig: cfg.Variable,
      final: bool = False,
  ) -> None:
    """Update this variable's annotation and/or value."""
    if op in self._ops:
      return
    self._ops.append(op)
    self.final = final
    if typ:
      if self.typ:
        self.typ.AddBinding(typ, [], node)
      else:
        self.typ = self.ctx.program.NewVariable([typ], [], node)
    if orig:
      self.orig = orig

  def get_type(self, node: cfg.CFGNode, name: str) -> Any | None:
    """Gets the variable's annotation."""
    if not self.typ:
      return None
    values = self.typ.Data(node)
    if len(values) > 1:
      self.ctx.errorlog.ambiguous_annotation(self.stack, values, name)
      return self.ctx.convert.unsolvable
    elif values:
      return values[0]
    else:
      return None


class _Abstract:
  """A helper that lazily loads the 'abstract' module to prevent circular deps.

  Always import it like this:

  if TYPE_CHECKING:
    from pytype.abstract import abstract as _abstract
  else:
    _abstract = abstract_utils._abstract  # pylint: disable=protected-access
  """

  _loaded = False

  def __getattr__(self, name: str) -> object:
    if not self._loaded:
      from pytype.abstract import abstract  # pylint: disable=g-import-not-at-top,g-bad-import-order

      # Copy all the attributes from the module to this object.
      # This is done so that subsequent attribute accesses will not even need to
      # go through this __getattr__ method and will be resolved directly.
      self.__dict__.update({
          attr: getattr(abstract, attr)
          for attr in dir(abstract)
          if attr[0].isupper()
      })
      self._loaded = True

    return object.__getattribute__(self, name)


if TYPE_CHECKING:
  from pytype.abstract import abstract  # pylint: disable=g-import-not-at-top,g-bad-import-order

  _abstract = abstract
else:
  _abstract = _Abstract()


# Sentinel for get_atomic_value
class _None:
  pass


def get_atomic_value(
    variable: cfg.Variable, constant_type=None, default=_None()
):
  """Get the atomic value stored in this variable."""
  if len(variable.bindings) == 1:
    (v,) = variable.bindings
    if isinstance(v.data, constant_type or object):
      return v.data  # success
  if not isinstance(default, _None):
    # If a default is specified, we return it instead of failing.
    return default
  # Determine an appropriate failure message.
  if not variable.bindings:
    raise ConversionError("Cannot get atomic value from empty variable.")
  bindings = variable.bindings
  name = bindings[0].data.ctx.convert.constant_name(constant_type)
  raise ConversionError(
      "Cannot get atomic value %s from variable. %s %s"
      % (name, variable, [b.data for b in bindings])
  )


def match_atomic_value(variable: cfg.Variable, typ=None) -> bool:
  try:
    get_atomic_value(variable, typ)
  except ConversionError:
    return False
  return True


def get_atomic_python_constant(variable: cfg.Variable, constant_type=None):
  """Get the concrete atomic Python value stored in this variable.

  This is used for things that are stored in cfg.Variable, but we
  need the actual data in order to proceed. E.g. function / class definitions.

  Args:
    variable: A cfg.Variable. It can only have one possible value.
    constant_type: Optionally, the required type of the constant.

  Returns:
    A Python constant. (Typically, a string, a tuple, or a code object.)
  Raises:
    ConversionError: If the value in this Variable is purely abstract, i.e.
      doesn't store a Python value, or if it has more than one possible value.
  """
  atomic = get_atomic_value(variable)
  return atomic.ctx.convert.value_to_constant(atomic, constant_type)


def match_atomic_python_constant(variable: cfg.Variable, typ=None) -> bool:
  try:
    get_atomic_python_constant(variable, typ)
  except ConversionError:
    return False
  return True


def get_views(
    variables: list[cfg.Variable],
    node: cfg.CFGNode,
) -> Generator[
    datatypes.AccessTrackingDict[cfg.Variable, cfg.Binding], Any, None
]:
  """Get all possible views of the given variables at a particular node.

  For performance reasons, this method uses node.CanHaveCombination for
  filtering. For a more precise check, you can call
  node.HasCombination(list(view.values())). Do so judiciously, as the latter
  method can be very slow.

  This function can be used either as a regular generator or in an optimized way
  to yield only functionally unique views:
    views = get_views(...)
    skip_future = None
    while True:
      try:
        view = views.send(skip_future)
      except StopIteration:
        break
      ...
    The caller should set `skip_future` to True when it is safe to skip
    equivalent future views and False otherwise.

  Args:
    variables: The variables.
    node: The node.

  Yields:
    A datatypes.AcessTrackingDict mapping variables to bindings.
  """
  try:
    combinations = cfg_utils.deep_variable_product(variables)
  except cfg_utils.TooComplexError:
    log.info(
        "get_views: too many binding combinations to generate accurate "
        "views, falling back to unsolvable"
    )
    combinations = (
        (
            var.AddBinding(node.program.default_data, [], node)  # pytype: disable=attribute-error
            for var in variables
        ),
    )
  seen = []  # the accessed subsets of previously seen views
  for combination in combinations:
    view = {value.variable: value for value in combination}
    if any(subset <= view.items() for subset in seen):
      # Optimization: This view can be skipped because it matches the accessed
      # subset of a previous one.
      log.info("Skipping view (already seen): %r", view)
      continue
    combination = list(view.values())
    if not node.CanHaveCombination(combination):
      log.info("Skipping combination (unreachable): %r", combination)
      continue
    view = datatypes.AccessTrackingDict(view)
    skip_future = yield view
    if skip_future:
      # Skip future views matching this accessed subset.
      seen.append(view.accessed_subset.items())


def equivalent_to(binding, cls):
  """Whether binding.data is equivalent to cls, modulo parameterization."""
  return (
      isinstance(binding.data, _abstract.Class)
      and binding.data.full_name == cls.full_name
  )


def is_subclass(value, cls):
  """Whether value is a subclass of cls, modulo parameterization."""
  if isinstance(value, _abstract.Union):
    return any(is_subclass(v, cls) for v in value.options)
  return isinstance(value, _abstract.Class) and any(
      value_cls.full_name == cls.full_name for value_cls in value.mro
  )


def apply_mutations(node, get_mutations):
  """Apply mutations yielded from a get_mutations function."""
  log.info("Applying mutations")
  num_mutations = 0
  for mut in get_mutations():
    if not num_mutations:
      # mutations warrant creating a new CFG node
      node = node.ConnectNew("ApplyMutations")
    num_mutations += 1
    mut.instance.merge_instance_type_parameter(node, mut.name, mut.value)
  log.info("Applied %d mutations", num_mutations)
  return node


def get_mro_bases(bases):
  """Get bases for MRO computation."""
  mro_bases = []
  has_user_generic = False
  for base_var in bases:
    if not base_var.data:
      continue
    # A base class is a Variable. If it has multiple options, we would
    # technically get different MROs. But since ambiguous base classes are rare
    # enough, we instead just pick one arbitrary option per base class.
    base = base_var.data[0]
    mro_bases.append(base)
    # check if it contains user-defined generic types
    if (
        isinstance(base, _abstract.ParameterizedClass)
        and base.full_name != "typing.Generic"
    ):
      has_user_generic = True
  # if user-defined generic type exists, we won't add `typing.Generic` to
  # the final result list
  if has_user_generic:
    return [b for b in mro_bases if b.full_name != "typing.Generic"]
  else:
    return mro_bases


def _merge_type(
    t0: "_instance_base.SimpleValue",
    t1: "_instance_base.SimpleValue",
    name: str,
    cls: "class_mixin.Class",
) -> "_instance_base.SimpleValue":
  """Merge two types.

  Rules: Type `Any` can match any type, we will return the other type if one
  of them is `Any`. Return the sub-class if the types have inheritance
  relationship.

  Args:
    t0: The first type.
    t1: The second type.
    name: Type parameter name.
    cls: The class_mixin.Class on which any error should be reported.

  Returns:
    A type.
  Raises:
    GenericTypeError: if the types don't match.
  """
  if t0 is None or isinstance(t0, _abstract.Unsolvable):
    return t1
  if t1 is None or isinstance(t1, _abstract.Unsolvable):
    return t0
  # t0 is a base of t1
  if t0 in t1.mro:
    return t1
  # t1 is a base of t0
  if t1 in t0.mro:
    return t0
  raise GenericTypeError(cls, f"Conflicting value for TypeVar {name}")


def parse_formal_type_parameters(
    base: "_classes.InterpreterClass | _classes.PyTDClass | _classes.ParameterizedClass",
    prefix: str | None,
    formal_type_parameters: "datatypes.AliasingDict[str, _instance_base.SimpleValue]",
    container: "_instance_base.SimpleValue | DummyContainer | None" = None,
) -> None:
  """Parse type parameters from base class.

  Args:
    base: base class.
    prefix: the full name of subclass of base class.
    formal_type_parameters: the mapping of type parameter name to its type.
    container: An abstract value whose class template is used when prefix=None
      to decide how to handle type parameters that are aliased to other type
      parameters. Values that are in the class template are kept, while all
      others are ignored.

  Raises:
    GenericTypeError: If the lazy types of type parameter don't match
  """

  def merge(
      t0: "_instance_base.SimpleValue",
      t1: "_instance_base.SimpleValue",
      name: str,
  ) -> "_instance_base.SimpleValue":
    return _merge_type(t0, t1, name, base)

  if isinstance(base, _abstract.ParameterizedClass):
    if base.full_name == "typing.Generic":
      return
    if isinstance(
        base.base_cls, (_abstract.InterpreterClass, _abstract.PyTDClass)
    ):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(
          base.base_cls.all_formal_type_parameters, merge
      )
    params = base.get_formal_type_parameters()
    if hasattr(container, "cls"):
      container_template = container.cls.template
    else:
      container_template = ()
    for name, param in params.items():
      if isinstance(param, _abstract.TypeParameter):
        # We have type parameter renaming, e.g.,
        #  class List(Generic[T]): pass
        #  class Foo(List[U]): pass
        if prefix:
          formal_type_parameters.add_alias(
              name, prefix + "." + param.name, merge
          )
        elif param in container_template:
          formal_type_parameters[name] = param
      else:
        # We have either a non-formal parameter, e.g.,
        # class Foo(List[int]), or a non-1:1 parameter mapping, e.g.,
        # class Foo(List[K or V]). Initialize the corresponding instance
        # parameter appropriately.
        if name not in formal_type_parameters:
          formal_type_parameters[name] = param
        else:
          # Two unrelated containers happen to use the same type
          # parameter but with different types.
          last_type = formal_type_parameters[name]
          formal_type_parameters[name] = merge(last_type, param, name)  # pytype: disable=wrong-arg-types
  else:
    if isinstance(base, (_abstract.InterpreterClass, _abstract.PyTDClass)):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(base.all_formal_type_parameters, merge)
    if base.template:
      # handle unbound type parameters
      for item in base.template:
        if isinstance(item, _abstract.TypeParameter):
          # This type parameter will be set as `ANY`.
          name = full_type_name(base, item.name)
          if name not in formal_type_parameters:
            formal_type_parameters[name] = None


def full_type_name(val: "_instance_base.SimpleValue", name: str) -> str:
  """Compute complete type parameter name with scope.

  Args:
    val: The object with type parameters.
    name: The short type parameter name (e.g., T).

  Returns:
    The full type parameter name (e.g., List.T).
  """
  if isinstance(val, _abstract.Instance):
    return full_type_name(val.cls, name)
  # The type is in current `class`
  for t in val.template:
    if name in (t.name, t.full_name):
      return t.full_name
  # The type is instantiated in `base class`
  for t in val.all_template_names:
    if t.split(".")[-1] == name or t == name:
      return t
  return name


def maybe_extract_tuple(t: cfg.Variable) -> tuple[cfg.Variable, ...]:
  """Returns a tuple of Variables."""
  values = t.data
  if len(values) > 1:
    return (t,)
  (v,) = values
  if not isinstance(v, _abstract.Tuple):
    return (t,)
  return v.pyval


def eval_expr(
    ctx: "context.Context", node: cfg.CFGNode, f_globals, f_locals, expr
) -> tuple[Any, EvaluationError | None]:
  """Evaluate an expression with the given node and globals."""
  # This is used to resolve type comments and late annotations.
  #
  # We don't chain node and f_globals as we want to remain in the context
  # where we've just finished evaluating the module. This would prevent
  # nasty things like:
  #
  # def f(a: "A = 1"):
  #   pass
  #
  # def g(b: "A"):
  #   pass
  #
  # Which should simply complain at both annotations that 'A' is not defined
  # in both function annotations. Chaining would cause 'b' in 'g' to yield a
  # different error message.
  log.info("Evaluating expr: %r", expr)

  # Any errors logged here will have a filename of None and a linenumber of 1
  # when what we really want is to allow the caller to handle/log the error
  # themselves.  Thus we checkpoint the errorlog and then restore and raise
  # an exception if anything was logged.
  with ctx.errorlog.checkpoint() as record:
    try:
      code = ctx.vm.compile_src(expr, mode="eval")
    except pyc.CompileError as e:
      # We keep only the error message, since the filename and line number are
      # for a temporary file.
      ctx.errorlog.python_compiler_error(None, 0, e.error)
      ret = ctx.new_unsolvable(node)
    else:
      _, _, _, ret = ctx.vm.run_bytecode(node, code, f_globals, f_locals)
  log.info("Finished evaluating expr: %r", expr)
  if record.errors:
    # Annotations are constants, so tracebacks aren't needed.
    e = EvaluationError(*(error.drop_traceback() for error in record.errors))
  else:
    e = None
  return ret, e


def match_type_container(typ, container_type_name: str | tuple[str, ...]):
  """Unpack the type parameter from ContainerType[T]."""
  if typ is None:
    return None
  if isinstance(container_type_name, str):
    container_type_name = (container_type_name,)
  if not (
      isinstance(typ, _abstract.ParameterizedClass)
      and typ.full_name in container_type_name
  ):
    return None
  param = typ.get_formal_type_parameter(T)
  return param


def get_annotations_dict(
    members: dict[str, cfg.Variable],
) -> "_instances.AnnotationsDict | None":
  """Get __annotations__ from a members map.

  Returns None rather than {} if the dict does not exist so that callers always
  have a reference to the actual dictionary, and can mutate it if needed.

  Args:
    members: A dict of member name to variable

  Returns:
    members['__annotations__'] unpacked as a python dict, or None
  """
  if "__annotations__" not in members:
    return None
  annots_var = members["__annotations__"]
  try:
    annots = get_atomic_value(annots_var)
  except ConversionError:
    return None
  return annots if isinstance(annots, _abstract.AnnotationsDict) else None


def is_concrete_dict(val: "_base.BaseValue") -> bool:
  return val.is_concrete and isinstance(val, _abstract.Dict)


def is_concrete_list(val: "_base.BaseValue") -> bool:
  return val.is_concrete and isinstance(val, _abstract.List)


def is_indefinite_iterable(val: "_base.BaseValue") -> bool:
  """True if val is a non-concrete instance of typing.Iterable."""
  instance = isinstance(val, _abstract.Instance)
  cls_instance = isinstance(val.cls, _abstract.Class)
  if not (instance and cls_instance and not val.is_concrete):
    return False
  for cls in val.cls.mro:
    if cls.full_name == "builtins.str":
      return False
    elif cls.full_name == "builtins.tuple":
      # A tuple's cls attribute may point to either PyTDClass(tuple) or
      # TupleClass; only the former is indefinite.
      return isinstance(cls, _abstract.PyTDClass)
    elif cls.full_name == "typing.Iterable":
      return True
  return False


def is_var_indefinite_iterable(var: cfg.Variable) -> bool:
  """True if all bindings of var are indefinite sequences."""
  return all(is_indefinite_iterable(x) for x in var.data)


def is_dataclass(val: "class_mixin.Class") -> bool:
  # TODO: b/350643999 - isinstance call possibly not needed.
  return (
      isinstance(val, _abstract.Class)
      and "__dataclass_fields__" in val.metadata
  )


def is_attrs(val: "class_mixin.Class") -> bool:
  # TODO: b/350643999 - isinstance call possibly not needed.
  return isinstance(val, _abstract.Class) and "__attrs_attrs__" in val.metadata


def merged_type_parameter(
    node: cfg.CFGNode, var: cfg.Variable, param
) -> cfg.Variable:
  if not var.bindings:
    return node.program.NewVariable()
  if is_var_splat(var):
    var = unwrap_splat(var)
  params = [v.get_instance_type_parameter(param) for v in var.data]
  return var.data[0].ctx.join_variables(node, params)


# TODO: b/350643999 - Annotate this with a type guard instead. Since there's no
# syntax to typeguard something which is on the property, we would need to
# change the callsite to pass in var.data[0] instead.
def is_var_splat(var: cfg.Variable) -> bool:
  if var.data and isinstance(var.data[0], _abstract.Splat):
    # A splat should never have more than one binding, since we create and use
    # it immediately.
    assert len(var.bindings) == 1
    return True
  return False


def unwrap_splat(var: cfg.Variable) -> "cfg.Variable":
  return var.data[0].iterable


def is_callable(value: "_base.BaseValue") -> bool:
  """Returns whether 'value' is a callable."""
  if isinstance(
      value,
      (
          _abstract.Function,
          _abstract.BoundFunction,
          _abstract.ClassMethod,
          _abstract.StaticMethod,
      ),
  ):
    return True
  if not isinstance(value.cls, _abstract.Class):
    return False
  _, attr = value.ctx.attribute_handler.get_attribute(
      value.ctx.root_node, value.cls, "__call__"
  )
  return attr is not None


def expand_type_parameter_instances(
    bindings: Iterable[cfg.Binding],
) -> Generator[cfg.Binding, None, None]:
  """Expands any TypeParameterInstance values in `bindings`."""
  bindings = list(bindings)
  seen = set()
  while bindings:
    b = bindings.pop(0)
    if isinstance(b.data, _abstract.TypeParameterInstance):
      if b.data in seen:
        continue
      seen.add(b.data)
      param_value = b.data.instance.get_instance_type_parameter(b.data.name)
      if param_value.bindings:
        bindings = param_value.bindings + bindings
        continue
    yield b


def get_type_parameter_substitutions(
    val: "_base.BaseValue", type_params: "Iterable[_typing.TypeParameter]"
) -> Mapping[str, cfg.Variable]:
  """Get values for type_params from val's type parameters."""
  subst = {}
  for p in type_params:
    if isinstance(val, _abstract.Class):
      param_value = val.get_formal_type_parameter(p.name).instantiate(
          val.ctx.root_node
      )
    else:
      param_value = val.get_instance_type_parameter(p.name)
    subst[p.full_name] = param_value
  return subst


def is_type_variable(
    val: "_base.BaseValue",
) -> "TypeGuard[pytd.TypeParameter|pytd.ParamSpec]":
  """Check if a value is a type variable (TypeVar or ParamSpec)."""
  return isinstance(val, (_abstract.TypeParameter, _abstract.ParamSpec))


def build_generic_template(
    type_params: "Sequence[_base.BaseValue]", base_type: "_base.BaseValue"
) -> "tuple[Sequence[str], Sequence[_typing.TypeParameter]]":
  """Build a typing.Generic template from a sequence of type parameters."""
  if not all(is_type_variable(item) for item in type_params):
    base_type.ctx.errorlog.invalid_annotation(
        base_type.ctx.vm.frames,
        base_type,
        "Parameters to Generic[...] must all be type variables",
    )
    type_params = [item for item in type_params if is_type_variable(item)]

  template = [item.name for item in type_params]

  if len(set(template)) != len(template):
    base_type.ctx.errorlog.invalid_annotation(
        base_type.ctx.vm.frames,
        base_type,
        "Parameters to Generic[...] must all be unique",
    )

  return template, type_params  # pytype: disable=bad-return-type


def is_generic_protocol(val: "_base.BaseValue") -> bool:
  return (
      isinstance(val, _abstract.ParameterizedClass)
      and val.full_name == "typing.Protocol"
  )


def combine_substs(
    substs1: Sequence[Mapping[str, cfg.Variable]] | None,
    substs2: Sequence[Mapping[str, cfg.Variable]] | None,
) -> Sequence[Mapping[str, cfg.Variable]]:
  """Combines the two collections of type parameter substitutions."""
  if substs1 and substs2:
    return tuple({**sub1, **sub2} for sub1 in substs1 for sub2 in substs2)  # pylint: disable=g-complex-comprehension
  elif substs1:
    return substs1
  elif substs2:
    return substs2
  else:
    return ()


def flatten(
    value: "_instance_base.SimpleValue", classes: "list[class_mixin.Class]"
) -> bool:
  """Flatten the contents of value into classes.

  If value is a Class, it is appended to classes.
  If value is a PythonConstant of type tuple, then each element of the tuple
  that has a single binding is also flattened.
  Any other type of value, or tuple elements that have multiple bindings are
  ignored.

  Args:
    value: An abstract value.
    classes: A list to be modified.

  Returns:
    True iff a value was ignored during flattening.
  """
  # Used by special_builtins.IsInstance and IsSubclass
  if isinstance(value, _abstract.AnnotationClass):
    value = value.base_cls
  if isinstance(value, _abstract.Class):
    # A single class, no ambiguity.
    classes.append(value)
    return False
  elif isinstance(value, _abstract.Tuple):
    # A tuple, need to process each element.
    ambiguous = False
    for var in value.pyval:
      if len(var.bindings) != 1 or flatten(var.bindings[0].data, classes):
        # There were either multiple bindings or ambiguity deeper in the
        # recursion.
        ambiguous = True
    return ambiguous
  elif isinstance(value, _abstract.Union):
    # A Union cannot be used in an isinstance call before Python 3.10, but
    # there's no harm in processing it anyway.
    ambiguous = False
    for val in value.options:
      if flatten(val, classes):
        ambiguous = True
    return ambiguous
  else:
    return True


def check_against_mro(
    ctx: "context.Context",
    target: "_base.BaseValue",
    class_spec: "_instance_base.SimpleValue",
) -> bool | None:
  """Check if any of the classes are in the target's MRO.

  Args:
    ctx: The abstract context.
    target: A BaseValue whose MRO will be checked.
    class_spec: A Class or PythonConstant tuple of classes (i.e. the second
      argument to isinstance or issubclass).

  Returns:
    True if any class in classes is found in the target's MRO,
    False if no match is found and None if it's ambiguous.
  """
  # Determine the flattened list of classes to check.
  classes = []
  ambiguous = flatten(class_spec, classes)

  for c in classes:
    if ctx.matcher(None).match_from_mro(target, c, allow_compat_builtins=False):
      return True  # A definite match.
  # No matches, return result depends on whether flatten() was
  # ambiguous.
  return None if ambiguous else False


def maybe_unwrap_decorated_function(func: "_function_base.Function"):
  # Some decorators, like special_builtins.PropertyInstance, have a
  # 'func' pointer to the decorated function. Note that we check for .data to
  # make sure 'func' is a Variable.
  try:
    # TODO: b/350643999 - The type here passed in is indeed correct but
    # the intent of this functions is quite unclear. Figure out and fix it.
    func.func.data  # pytype: disable=attribute-error
  except AttributeError:
    return None
  return func.func  # pytype: disable=attribute-error


def unwrap_final(val: "_base.BaseValue") -> "_base.BaseValue":
  """Unwrap Final[T] -> T."""
  if isinstance(val, _abstract.FinalAnnotation):
    # Final type created via an annotation in the current module
    return val.annotation
  elif (
      isinstance(val, _abstract.Instance)
      and val.cls.full_name == "typing.Final"
  ):
    # Final types loaded from a pyi file get converted to abstract.Instance
    # with cls=typing.Final and instance type parameter T
    return get_atomic_value(val.get_instance_type_parameter(T))
  return val


def is_recursive_annotation(
    annot: "_typing.LateAnnotation | _base.BaseValue",
) -> bool:
  # TODO: b/350643999 - This is calling out for a type guard, but under pytype's
  # type system it's not possible to make this work without using isinstance(..)
  # We also cannot use isinstance because it will cause circular imports
  return annot.is_late_annotation() and annot.is_recursive()  # pytype: disable=attribute-error


def is_ellipsis(val) -> bool:
  return val == val.ctx.convert.ellipsis or (
      val.is_concrete and val.pyval == "..."
  )


def update_args_dict(
    args: dict[str, cfg.Variable],
    update: dict[str, cfg.Variable],
    node: cfg.CFGNode,
) -> None:
  """Update a {str: Variable} dict by merging bindings."""
  for k, v in update.items():
    if k in args:
      args[k].PasteVariable(v, node)
    else:
      args[k] = v


def get_generic_type(
    val: "_base.BaseValue",
) -> "_classes.ParameterizedClass | None":
  """Gets the generic type of an abstract value.

  Args:
    val: The abstract value.

  Returns:
    The type of the value, with concrete type parameters replaced by TypeVars.
    For example, the generic type of `[0]` is `List[T]`.
  """
  is_class = isinstance(val, _abstract.Class)
  if is_class:
    cls = val
  elif isinstance(val.cls, _abstract.Class):
    cls = val.cls
  else:
    return None
  for parent_cls in cls.mro:
    if isinstance(parent_cls, _abstract.ParameterizedClass):
      base_cls = parent_cls.base_cls
    else:
      base_cls = parent_cls
    if isinstance(base_cls, _abstract.Class) and base_cls.template:
      ctx = base_cls.ctx
      params = {item.name: item for item in base_cls.template}
      generic_cls = _abstract.ParameterizedClass(base_cls, params, ctx)
      if is_class:
        return _abstract.ParameterizedClass(
            ctx.convert.type_type, {T: generic_cls}, ctx
        )
      else:
        return generic_cls
  return None


def with_empty_substitutions(
    subst: datatypes.AliasingDict[str, cfg.Variable],
    pytd_type: "_base.BaseValue",
    node: cfg.CFGNode,
    ctx: "context.Context",
) -> datatypes.AliasingDict[str, cfg.Variable]:
  new_subst = {
      t.full_name: ctx.convert.empty.to_variable(node)
      for t in pytd_utils.GetTypeParameters(pytd_type)
      if t.full_name not in subst
  }
  return subst.copy(**new_subst)


def get_var_fullhash_component(
    var: cfg.Variable, seen: "set[_base.BaseValue] | None" = None
) -> tuple[Any, ...]:
  return tuple(sorted(v.get_fullhash(seen) for v in var.data))


def get_dict_fullhash_component(
    vardict: dict[str, cfg.Variable],
    *,
    names: set[str] | None = None,
    seen: "set[_base.BaseValue] | None" = None,
) -> tuple[Any, ...]:
  """Hash a dictionary.

  This contains the keys and the full hashes of the data in the values.

  Arguments:
    vardict: A dictionary mapping str to Variable.
    names: If this is non-None, the snapshot will include only those dictionary
      entries whose keys appear in names.
    seen: Optionally, a set of seen values for recursion detection.

  Returns:
    A hashable tuple of the dictionary.
  """
  if names is not None:
    vardict = {name: vardict[name] for name in names.intersection(vardict)}
  return tuple(
      sorted(
          (k, get_var_fullhash_component(v, seen)) for k, v in vardict.items()
      )
  )


def simplify_variable(
    var: cfg.Variable, node: cfg.CFGNode, ctx: "context.Context"
) -> cfg.Variable:
  """Deduplicates identical data in `var`."""
  if not var:
    return var
  bindings_by_hash = collections.defaultdict(list)
  for b in var.bindings:
    bindings_by_hash[b.data.get_fullhash()].append(b)
  if len(bindings_by_hash) == len(var.bindings):
    return var
  new_var = ctx.program.NewVariable()
  for bindings in bindings_by_hash.values():
    new_var.AddBinding(bindings[0].data, bindings, node)
  return new_var


def _abstractify_value(
    val: "_instances.ConcreteValue",
    ctx: "context.Context",
    seen: "set[_base.BaseValue] | None" = None,
) -> "_instances.ConcreteValue":
  """Converts a maybe-abstract value to a concrete one.

  Args:
    val: A value.
    ctx: The context.
    seen: Optionally, a seen values set.

  Unlike ctx.convert.get_maybe_abstract_instance, this method recursively
  descends into lists and tuples.

  Returns:
    A concrete value.
  """
  if seen is None:
    seen = set()

  if not val.is_concrete or val in seen:
    return val
  seen = seen | {val}

  if not isinstance(val.pyval, (list, tuple)):
    return ctx.convert.get_maybe_abstract_instance(val)
  new_content = []

  for elem in val.pyval:
    new_elem_data = [_abstractify_value(v, ctx, seen) for v in elem.data]
    if any(v != new_v for v, new_v in zip(elem.data, new_elem_data)):
      new_elem = ctx.program.NewVariable()
      for b, new_data in zip(elem.bindings, new_elem_data):
        new_elem.PasteBindingWithNewData(b, new_data)
      new_content.append(new_elem)
    else:
      new_content.append(elem)

  if any(elem != new_elem for elem, new_elem in zip(val.pyval, new_content)):
    # TODO: b/350643999 - There is no type that matches this signature and I
    # assume it to be dead code, try removing it.
    return type(val)(type(val.pyval)(new_content), ctx)  # pytype:disable=missing-parameter
  else:
    return val


def abstractify_variable(
    var: cfg.Variable, ctx: "context.Context"
) -> cfg.Variable:
  if not any(v.is_concrete for v in var.data):
    return var
  new_var = ctx.program.NewVariable()
  for b in var.bindings:
    new_var.PasteBindingWithNewData(b, _abstractify_value(b.data, ctx))
  return new_var
