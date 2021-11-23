"""Utilities for abstract.py."""

import collections
import hashlib
import logging
from typing import Any, Collection, Dict, Iterable, Mapping, Optional, Sequence, Tuple, Union

from pytype import datatypes
from pytype import utils
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)

# We can't import abstract here due to a circular dep.
_BaseValue = Any  # abstract.BaseValue
_TypeParameter = Any  # abstract.TypeParameter

# Type parameter names matching the ones in builtins.pytd and typing.pytd.
T = "_T"
T2 = "_T2"
K = "_K"
V = "_V"
ARGS = "_ARGS"
RET = "_RET"

# TODO(rechen): Stop supporting all variants except _HAS_DYNAMIC_ATTRIBUTES.
DYNAMIC_ATTRIBUTE_MARKERS = [
    "HAS_DYNAMIC_ATTRIBUTES",
    "_HAS_DYNAMIC_ATTRIBUTES",
    "has_dynamic_attributes",
]

# A dummy container object for use in instantiating type parameters.
# A container is needed to preserve type parameter names for error messages
# and for sub_(one_)annotation(s).
DUMMY_CONTAINER = object()

# Names defined on every module/class that should be ignored in most cases.
TOP_LEVEL_IGNORE = frozenset({
    "__builtins__",
    "__doc__",
    "__file__",
    "__future__",
    "__module__",
    "__name__",
    "__annotations__",
    "google_type_annotations",
})
CLASS_LEVEL_IGNORE = frozenset({
    "__builtins__",
    "__class__",
    "__module__",
    "__name__",
    "__qualname__",
    "__slots__",
    "__annotations__",
})


class ConversionError(ValueError):
  pass


class EvaluationError(Exception):
  """Used to signal an errorlog error during type name evaluation."""

  @property
  def errors(self):
    return utils.message(self)

  @property
  def details(self):
    return "\n".join(error.message for error in self.errors)


class GenericTypeError(Exception):
  """The error for user-defined generic types."""

  def __init__(self, annot, error):
    super().__init__(annot, error)
    self.annot = annot
    self.error = error


class ModuleLoadError(Exception):
  """Signal an error when trying to lazily load a submodule."""


class AsInstance:
  """Wrapper, used for marking things that we want to convert to an instance."""

  def __init__(self, cls):
    self.cls = cls


class AsReturnValue(AsInstance):
  """Specially mark return values, to handle NoReturn properly."""


# For lazy evaluation of ParameterizedClass.formal_type_parameters
LazyFormalTypeParameters = collections.namedtuple(
    "LazyFormalTypeParameters", ("template", "parameters", "subst"))


# Sentinel for get_atomic_value
class _None:
  pass


def get_atomic_value(variable, constant_type=None, default=_None()):
  """Get the atomic value stored in this variable."""
  if len(variable.bindings) == 1:
    v, = variable.bindings
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
      % (name, variable, [b.data for b in bindings]))


def get_atomic_python_constant(variable, constant_type=None):
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


def get_views(variables, node):
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
    combinations = ((var.AddBinding(node.program.default_data, [], node)
                     for var in variables),)
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


def func_name_is_class_init(name):
  """Return True if |name| is that of a class' __init__ method."""
  # Python 3's MAKE_FUNCTION byte code takes an explicit fully qualified
  # function name as an argument and that is used for the function name.
  # On the other hand, Python 2's MAKE_FUNCTION does not take any name
  # argument so we pick the name from the code object. This name is not
  # fully qualified. Hence, constructor names in Python 3 are fully
  # qualified ending in '.__init__', and constructor names in Python 2
  # are all '__init__'. So, we identify a constructor by matching its
  # name with one of these patterns.
  return name == "__init__" or name.endswith(".__init__")


def equivalent_to(binding, cls):
  """Whether binding.data is equivalent to cls, modulo parameterization."""
  return (_isinstance(binding.data, "Class") and
          binding.data.full_name == cls.full_name)


def apply_mutations(node, get_mutations):
  """Apply mutations yielded from a get_mutations function."""
  log.info("Applying mutations")
  num_mutations = 0
  for obj, name, value in get_mutations():
    if not num_mutations:
      # mutations warrant creating a new CFG node
      node = node.ConnectNew(node.name)
    num_mutations += 1
    obj.merge_instance_type_parameter(node, name, value)
  log.info("Applied %d mutations", num_mutations)
  return node


def get_mro_bases(bases, ctx):
  """Get bases for MRO computation."""
  mro_bases = []
  has_user_generic = False
  for base_var in bases:
    if not base_var.data:
      continue
    # A base class is a Variable. If it has multiple options, we would
    # technically get different MROs. But since ambiguous base classes are rare
    # enough, we instead just pick one arbitrary option per base class.
    base = get_atomic_value(base_var, default=ctx.convert.unsolvable)
    mro_bases.append(base)
    # check if it contains user-defined generic types
    if (_isinstance(base, "ParameterizedClass") and
        base.full_name != "typing.Generic"):
      has_user_generic = True
  # if user-defined generic type exists, we won't add `typing.Generic` to
  # the final result list
  if has_user_generic:
    return [b for b in mro_bases if b.full_name != "typing.Generic"]
  else:
    return mro_bases


def _merge_type(t0, t1, name, cls):
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
  if t0 is None or _isinstance(t0, "Unsolvable"):
    return t1
  if t1 is None or _isinstance(t1, "Unsolvable"):
    return t0
  # t0 is a base of t1
  if t0 in t1.mro:
    return t1
  # t1 is a base of t0
  if t1 in t0.mro:
    return t0
  raise GenericTypeError(cls, "Conflicting value for TypeVar %s" % name)


def parse_formal_type_parameters(
    base, prefix, formal_type_parameters, container=None):
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
  def merge(t0, t1, name):
    return _merge_type(t0, t1, name, base)

  if _isinstance(base, "ParameterizedClass"):
    if base.full_name == "typing.Generic":
      return
    if _isinstance(base.base_cls, ("InterpreterClass", "PyTDClass")):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(
          base.base_cls.all_formal_type_parameters, merge)
    params = base.get_formal_type_parameters()
    if hasattr(container, "cls"):
      container_template = container.cls.template
    else:
      container_template = ()
    for name, param in params.items():
      if _isinstance(param, "TypeParameter"):
        # We have type parameter renaming, e.g.,
        #  class List(Generic[T]): pass
        #  class Foo(List[U]): pass
        if prefix:
          formal_type_parameters.add_alias(
              name, prefix + "." + param.name, merge)
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
          formal_type_parameters[name] = merge(last_type, param, name)
  else:
    if _isinstance(base, ("InterpreterClass", "PyTDClass")):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(
          base.all_formal_type_parameters, merge)
    if base.template:
      # handle unbound type parameters
      for item in base.template:
        if _isinstance(item, "TypeParameter"):
          # This type parameter will be set as `ANY`.
          name = full_type_name(base, item.name)
          if name not in formal_type_parameters:
            formal_type_parameters[name] = None


def full_type_name(val, name):
  """Compute complete type parameter name with scope.

  Args:
    val: The object with type parameters.
    name: The short type parameter name (e.g., T).

  Returns:
    The full type parameter name (e.g., List.T).
  """
  if _isinstance(val, "Instance"):
    return full_type_name(val.cls, name)
  # The type is in current `class`
  for t in val.template:
    if t.name == name:
      return val.full_name + "." + name
    elif t.full_name == name:
      return t.full_name
  # The type is instantiated in `base class`
  for t in val.all_template_names:
    if t.split(".")[-1] == name or t == name:
      return t
  return name


def maybe_extract_tuple(t):
  """Returns a tuple of Variables."""
  values = t.data
  if len(values) > 1:
    return (t,)
  v, = values
  if not _isinstance(v, "Tuple"):
    return (t,)
  return v.pyval


def _hash_dict(vardict, names):
  """Hash a dictionary.

  This contains the keys and the full hashes of the data in the values.

  Arguments:
    vardict: A dictionary mapping str to Variable.
    names: If this is non-None, the snapshot will include only those
      dictionary entries whose keys appear in names.

  Returns:
    A hash of the dictionary.
  """
  if names is not None:
    vardict = {name: vardict[name] for name in names.intersection(vardict)}
  m = hashlib.md5()
  for name, var in sorted(vardict.items()):
    m.update(str(name).encode("utf-8"))
    for value in var.bindings:
      m.update(value.data.get_fullhash())
  return m.digest()


def hash_all_dicts(*hash_args):
  """Convenience method for hashing a sequence of dicts."""
  return hashlib.md5(b"".join(_hash_dict(*args) for args in hash_args)).digest()


def _matches_generator(type_obj, allowed_types):
  """Check if type_obj matches a Generator/AsyncGenerator type."""
  if _isinstance(type_obj, "Union"):
    return all(_matches_generator(sub_type, allowed_types)
               for sub_type in type_obj.options)
  else:
    base_cls = type_obj
    if _isinstance(type_obj, "ParameterizedClass"):
      base_cls = type_obj.base_cls
    return ((_isinstance(base_cls, "PyTDClass") and
             base_cls.name in allowed_types) or
            _isinstance(base_cls, "AMBIGUOUS_OR_EMPTY"))


def matches_generator(type_obj):
  allowed_types = ("generator", "Iterable", "Iterator")
  return _matches_generator(type_obj, allowed_types)


def matches_async_generator(type_obj):
  allowed_types = ("asyncgenerator", "AsyncIterable", "AsyncIterator")
  return _matches_generator(type_obj, allowed_types)


def var_map(func, var):
  return (func(v) for v in var.data)


def eval_expr(ctx, node, f_globals, f_locals, expr):
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
    e = EvaluationError([error.drop_traceback() for error in record.errors])
  else:
    e = None
  return ret, e


def check_classes(var, check):
  """Check whether the cls of each value in `var` is a class and passes `check`.

  Args:
    var: A cfg.Variable or empty.
    check: (BaseValue) -> bool.

  Returns:
    Whether the check passes.
  """
  if not var:
    return False
  for v in var.data:
    if _isinstance(v, "Class"):
      if not check(v):
        return False
    elif _isinstance(v.cls, "Class") and v.cls != v:
      if not check(v.cls):
        return False
  return True


def match_type_container(typ, container_type_name: Union[str, Tuple[str, ...]]):
  """Unpack the type parameter from ContainerType[T]."""
  if typ is None:
    return None
  if isinstance(container_type_name, str):
    container_type_name = (container_type_name,)
  if not (_isinstance(typ, "ParameterizedClass") and
          typ.full_name in container_type_name):
    return None
  param = typ.get_formal_type_parameter(T)
  return param


def get_annotations_dict(members):
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
  return annots if _isinstance(annots, "AnnotationsDict") else None


class Local:
  """A possibly annotated local variable."""

  def __init__(self, node, op: Optional[opcodes.Opcode],
               typ: Optional[_BaseValue], orig: Optional[cfg.Variable], ctx):
    self._ops = [op]
    if typ:
      self.typ = ctx.program.NewVariable([typ], [], node)
    else:
      # Creating too many variables bloats the typegraph, hurting performance,
      # so we use None instead of an empty variable.
      self.typ = None
    self.orig = orig
    self.ctx = ctx

  @property
  def stack(self):
    return self.ctx.vm.simple_stack(self._ops[-1])

  def update(self, node, op, typ, orig):
    """Update this variable's annotation and/or value."""
    if op in self._ops:
      return
    self._ops.append(op)
    if typ:
      if self.typ:
        self.typ.AddBinding(typ, [], node)
      else:
        self.typ = self.ctx.program.NewVariable([typ], [], node)
    if orig:
      self.orig = orig

  def get_type(self, node, name):
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


def is_literal(annot: Optional[_BaseValue]):
  if _isinstance(annot, "Union"):
    return all(is_literal(o) for o in annot.options)  # pytype: disable=attribute-error
  return _isinstance(annot, "LiteralClass")


def is_concrete_dict(val: _BaseValue):
  return _isinstance(val, "Dict") and not val.could_contain_anything


def is_concrete_list(val: _BaseValue):
  return _isinstance(val, "List") and not val.could_contain_anything


def is_concrete(val: _BaseValue):
  return (_isinstance(val, "PythonConstant") and
          not getattr(val, "could_contain_anything", False))


def is_indefinite_iterable(val: _BaseValue):
  """True if val is a non-concrete instance of typing.Iterable."""
  instance = _isinstance(val, "Instance")
  concrete = is_concrete(val)
  cls_instance = _isinstance(val.cls, "Class")
  if not (instance and cls_instance and not concrete):
    return False
  for cls in val.cls.mro:
    if cls.full_name == "builtins.str":
      return False
    elif cls.full_name == "builtins.tuple":
      # A tuple's cls attribute may point to either PyTDClass(tuple) or
      # TupleClass; only the former is indefinite.
      return _isinstance(cls, "PyTDClass")
    elif cls.full_name == "typing.Iterable":
      return True
  return False


def is_var_indefinite_iterable(var):
  """True if all bindings of var are indefinite sequences."""
  return all(is_indefinite_iterable(x) for x in var.data)


def merged_type_parameter(node, var, param):
  if not var.bindings:
    return node.program.NewVariable()
  if is_var_splat(var):
    var = unwrap_splat(var)
  params = [v.get_instance_type_parameter(param) for v in var.data]
  return var.data[0].ctx.join_variables(node, params)


def is_var_splat(var):
  if var.data and _isinstance(var.data[0], "Splat"):
    # A splat should never have more than one binding, since we create and use
    # it immediately.
    assert len(var.bindings) == 1
    return True
  return False


def unwrap_splat(var):
  return var.data[0].iterable


def is_callable(value: _BaseValue):
  """Returns whether 'value' is a callable."""
  if _isinstance(
      value, ("Function", "BoundFunction", "ClassMethod", "StaticMethod")):
    return True
  if not _isinstance(value.cls, "Class"):
    return False
  _, attr = value.ctx.attribute_handler.get_attribute(value.ctx.root_node,
                                                      value.cls, "__call__")
  return attr is not None


def expand_type_parameter_instances(bindings: Iterable[cfg.Binding]):
  bindings = list(bindings)
  while bindings:
    b = bindings.pop(0)
    if _isinstance(b.data, "TypeParameterInstance"):
      param_value = b.data.instance.get_instance_type_parameter(b.data.name)
      if param_value.bindings:
        bindings = param_value.bindings + bindings
        continue
    yield b


def get_type_parameter_substitutions(
    val: _BaseValue, type_params: Iterable[_TypeParameter]
) -> Mapping[str, cfg.Variable]:
  """Get values for type_params from val's type parameters."""
  subst = {}
  for p in type_params:
    if _isinstance(val, "Class"):
      param_value = val.get_formal_type_parameter(p.name).instantiate(
          val.ctx.root_node)
    else:
      param_value = val.get_instance_type_parameter(p.name)
    subst[p.full_name] = param_value
  return subst


def build_generic_template(
    type_params: Sequence[_BaseValue], base_type: _BaseValue
) -> Tuple[Sequence[str], Sequence[_TypeParameter]]:
  """Build a typing.Generic template from a sequence of type parameters."""
  if not all(_isinstance(item, "TypeParameter") for item in type_params):
    base_type.ctx.errorlog.invalid_annotation(
        base_type.ctx.vm.frames, base_type,
        "Parameters to Generic[...] must all be type variables")
    type_params = [item for item in type_params
                   if _isinstance(item, "TypeParameter")]

  template = [item.name for item in type_params]

  if len(set(template)) != len(template):
    base_type.ctx.errorlog.invalid_annotation(
        base_type.ctx.vm.frames, base_type,
        "Parameters to Generic[...] must all be unique")

  return template, type_params


def is_generic_protocol(val: _BaseValue) -> bool:
  return (_isinstance(val, "ParameterizedClass") and
          val.full_name == "typing.Protocol")


def combine_substs(
    substs1: Optional[Collection[Dict[str, cfg.Variable]]],
    substs2: Optional[Collection[Dict[str, cfg.Variable]]]
) -> Collection[Dict[str, cfg.Variable]]:
  """Combines the two collections of type parameter substitutions."""
  if substs1 and substs2:
    return tuple({**sub1, **sub2} for sub1 in substs1 for sub2 in substs2)  # pylint: disable=g-complex-comprehension
  elif substs1:
    return substs1
  elif substs2:
    return substs2
  else:
    return ()


def flatten(value, classes):
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
  if _isinstance(value, "AnnotationClass"):
    value = value.base_cls
  if _isinstance(value, "Class"):
    # A single class, no ambiguity.
    classes.append(value)
    return False
  elif _isinstance(value, "Tuple"):
    # A tuple, need to process each element.
    ambiguous = False
    for var in value.pyval:
      if (len(var.bindings) != 1 or
          flatten(var.bindings[0].data, classes)):
        # There were either multiple bindings or ambiguity deeper in the
        # recursion.
        ambiguous = True
    return ambiguous
  else:
    return True


def check_against_mro(ctx, target, class_spec):
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


def maybe_unwrap_decorated_function(func):
  # Some decorators, like special_builtins.PropertyInstance, have a
  # 'func' pointer to the decorated function. Note that we check for .data to
  # make sure 'func' is a Variable.
  try:
    func.func.data
  except AttributeError:
    return None
  return func.func


def _isinstance(obj, name_or_names):
  """Do an isinstance() call for a class defined in pytype.abstract.

  This method should be used only in pytype.abstract submodules that are unable
  to do normal isinstance() checks on abstract values due to circular
  dependencies. To prevent accidental misuse, this method is marked private.
  Callers are expected to alias it like so:
    _isinstance = abstract_utils._isinstance  # pylint: disable=protected-access

  Args:
    obj: An instance.
    name_or_names: A name or tuple of names of classes in pytype.abstract.

  Returns:
    Whether obj is an instance of name_or_names.
  """
  if not obj.__class__.__module__.startswith("pytype."):
    return False
  if isinstance(name_or_names, tuple):
    names = name_or_names
  elif name_or_names == "AMBIGUOUS_OR_EMPTY":
    names = ("Unknown", "Unsolvable", "Empty")
  else:
    names = (name_or_names,)
  obj_cls = obj.__class__
  if obj_cls.__module__.startswith("pytype.abstract") and obj_cls in names:
    # Do a simple check first to avoid expensive recursive calls and mro lookup
    # when possible.
    return True
  if len(names) > 1:
    return any(_isinstance(obj, name) for name in names)
  name = names[0]
  return any(cls.__module__.startswith("pytype.abstract") and
             cls.__name__ == name for cls in obj.__class__.mro())
