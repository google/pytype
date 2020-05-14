# Lint as: python3
"""Utilities for abstract.py."""

import collections
import hashlib
import logging
from typing import Tuple, Union

from pytype import compat
from pytype import datatypes
from pytype import utils
from pytype.pyc import pyc
from pytype.pytd import mro
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

import six

log = logging.getLogger(__name__)


# Type parameter names matching the ones in __builtin__.pytd and typing.pytd.
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
    super(GenericTypeError, self).__init__(annot, error)
    self.annot = annot
    self.error = error


class AsInstance(object):
  """Wrapper, used for marking things that we want to convert to an instance."""

  def __init__(self, cls):
    self.cls = cls


class AsReturnValue(AsInstance):
  """Specially mark return values, to handle NoReturn properly."""


# For lazy evaluation of ParameterizedClass.formal_type_parameters
LazyFormalTypeParameters = collections.namedtuple(
    "LazyFormalTypeParameters", ("template", "parameters", "subst"))


_NONE = object()  # sentinel for get_atomic_value


def get_atomic_value(variable, constant_type=None, default=_NONE):
  """Get the atomic value stored in this variable."""
  if len(variable.bindings) == 1:
    v, = variable.bindings
    if isinstance(v.data, constant_type or object):
      return v.data  # success
  if default is not _NONE:
    # If a default is specified, we return it instead of failing.
    return default
  # Determine an appropriate failure message.
  if not variable.bindings:
    raise ConversionError("Cannot get atomic value from empty variable.")
  bindings = variable.bindings
  name = bindings[0].data.vm.convert.constant_name(constant_type)
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
  return atomic.vm.convert.value_to_constant(atomic, constant_type)


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
    if any(subset <= six.viewitems(view) for subset in seen):
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
      seen.append(six.viewitems(view.accessed_subset))


def get_signatures(func):
  if func.isinstance_PyTDFunction():
    return [sig.signature for sig in func.signatures]
  elif func.isinstance_InterpreterFunction():
    return [f.signature for f in func.signature_functions()]
  elif func.isinstance_BoundFunction():
    sigs = get_signatures(func.underlying)
    return [sig.drop_first_parameter() for sig in sigs]  # drop "self"
  else:
    raise NotImplementedError(func.__class__.__name__)


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


def has_type_parameters(node, val, seen=None):
  """Checks if the given object contains any TypeParameters.

  This method differs from the `.formal` attribute on abstract values in that it
  recurses into container instances to detect type parameters that have
  (likely incorrectly) been inserted into runtime objects.

  Args:
    node: The current CFG node.
    val: The object to check for TypeParameters. Will likely be a
      SimpleAbstractValue or a cfg.Variable with SimpleAbstractValues bindings.
    seen: Optional. A set of already-visited objects, to avoid infinite loops.

  Returns:
    True if the object contains any TypeParameters, or False otherwise.
  """
  if seen is None:
    seen = set()
  if val in seen:
    return False
  seen.add(val)
  if isinstance(val, cfg.Variable):
    return any((has_type_parameters(node, d, seen) for d in val.data))
  elif val.isinstance_TypeParameter():
    return True
  elif val.isinstance_ParameterizedClass() or val.isinstance_Union():
    return val.formal
  elif val.isinstance_SimpleAbstractValue():
    return any((has_type_parameters(node, tp, seen)
                for tp in val.instance_type_parameters.values()))
  else:
    return False


def equivalent_to(binding, cls):
  """Whether binding.data is equivalent to cls, modulo parameterization."""
  return (binding.data.isinstance_Class() and
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


def get_template(val):
  """Get the value's class template."""
  if val.isinstance_Class():
    res = {t.full_name for t in val.template}
    if val.isinstance_ParameterizedClass():
      res.update(get_template(val.base_cls))
    elif val.isinstance_PyTDClass() or val.isinstance_InterpreterClass():
      for base in val.bases():
        base = get_atomic_value(base, default=val.vm.convert.unsolvable)
        res.update(get_template(base))
    return res
  elif val.cls:
    return get_template(val.cls)
  else:
    return set()


def get_mro_bases(bases, vm):
  """Get bases for MRO computation."""
  mro_bases = []
  has_user_generic = False
  for base_var in bases:
    if not base_var.data:
      continue
    # A base class is a Variable. If it has multiple options, we would
    # technically get different MROs. But since ambiguous base classes are rare
    # enough, we instead just pick one arbitrary option per base class.
    base = get_atomic_value(base_var, default=vm.convert.unsolvable)
    mro_bases.append(base)
    # check if it contains user-defined generic types
    if (base.isinstance_ParameterizedClass() and
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
    cls: The mixin.Class on which any error should be reported.
  Returns:
    A type.
  Raises:
    GenericTypeError: if the types don't match.
  """
  if t0 is None or t0.isinstance_Unsolvable():
    return t1
  if t1 is None or t1.isinstance_Unsolvable():
    return t0
  # t0 is parent of t1
  if t0 in t1.mro:
    return t1
  # t1 is parent of t0
  if t1 in t0.mro:
    return t0
  raise GenericTypeError(cls, "Conflicting value for TypeVar %s" % name)


def parse_formal_type_parameters(base, prefix, formal_type_parameters):
  """Parse type parameters from base class.

  Args:
    base: base class.
    prefix: the full name of subclass of base class.
    formal_type_parameters: the mapping of type parameter name to its type

  Raises:
    GenericTypeError: If the lazy types of type parameter don't match
  """
  def merge(t0, t1, name):
    return _merge_type(t0, t1, name, base)

  if base.isinstance_ParameterizedClass():
    if base.full_name == "typing.Generic":
      return
    if (base.base_cls.isinstance_InterpreterClass() or
        base.base_cls.isinstance_PyTDClass()):
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(
          base.base_cls.all_formal_type_parameters, merge)
    params = base.get_formal_type_parameters()
    for name, param in params.items():
      if param.isinstance_TypeParameter():
        # We have type parameter renaming, e.g.,
        #  class List(Generic[T]): pass
        #  class Foo(List[U]): pass
        if prefix:
          formal_type_parameters.add_alias(
              name, prefix + "." + param.name, merge)
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
    if base.isinstance_InterpreterClass() or base.isinstance_PyTDClass():
      # merge the type parameters info from base class
      formal_type_parameters.merge_from(
          base.all_formal_type_parameters, merge)
    if base.template:
      # handle unbound type parameters
      for item in base.template:
        if item.isinstance_TypeParameter():
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
  if val.isinstance_Instance():
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
  if not v.isinstance_Tuple():
    return (t,)
  return v.pyval


def compute_template(val):
  """Compute the precedence list of template parameters according to C3.

  1. For the base class list, if it contains `typing.Generic`, then all the
  type parameters should be provided. That means we don't need to parse extra
  base class and then we can get all the type parameters.
  2. If there is no `typing.Generic`, parse the precedence list according to
  C3 based on all the base classes.
  3. If `typing.Generic` exists, it must contain at least one type parameters.
  And there is at most one `typing.Generic` in the base classes. Report error
  if the check fails.

  Args:
    val: The abstract.AtomicAbstractValue to compute a template for.

  Returns:
    parsed type parameters

  Raises:
    GenericTypeError: if the type annotation for generic type is incorrect
  """
  if val.isinstance_PyTDClass():
    return [val.vm.convert.constant_to_value(itm.type_param)
            for itm in val.pytd_cls.template]
  elif not val.isinstance_InterpreterClass():
    return ()
  bases = [get_atomic_value(base, default=val.vm.convert.unsolvable)
           for base in val.bases()]
  template = []

  # Compute the number of `typing.Generic` and collect the type parameters
  for base in bases:
    if base.full_name == "typing.Generic":
      if base.isinstance_PyTDClass():
        raise GenericTypeError(val, "Cannot inherit from plain Generic")
      if template:
        raise GenericTypeError(
            val, "Cannot inherit from Generic[...] multiple times")
      for item in base.template:
        param = base.formal_type_parameters.get(item.name)
        template.append(param.with_module(val.full_name))

  if template:
    # All type parameters in the base classes should appear in
    # `typing.Generic`
    for base in bases:
      if base.full_name != "typing.Generic":
        if base.isinstance_ParameterizedClass():
          for item in base.template:
            param = base.formal_type_parameters.get(item.name)
            if param.isinstance_TypeParameter():
              t = param.with_module(val.full_name)
              if t not in template:
                raise GenericTypeError(
                    val, "Generic should contain all the type variables")
  else:
    # Compute template parameters according to C3
    seqs = []
    for base in bases:
      if base.isinstance_ParameterizedClass():
        seq = []
        for item in base.template:
          param = base.formal_type_parameters.get(item.name)
          if param.isinstance_TypeParameter():
            seq.append(param.with_module(val.full_name))
        seqs.append(seq)
    try:
      template.extend(mro.MergeSequences(seqs))
    except ValueError:
      raise GenericTypeError(
          val, "Illegal type parameter order in class %s" % val.name)

  return template


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
    m.update(compat.bytestring(name))
    for value in var.bindings:
      m.update(value.data.get_fullhash())
  return m.digest()


def hash_all_dicts(*hash_args):
  """Convenience method for hashing a sequence of dicts."""
  return hashlib.md5(b"".join(_hash_dict(*args) for args in hash_args)).digest()


def _matches_generator(type_obj, allowed_types):
  """Check if type_obj matches a Generator/AsyncGenerator type."""
  if type_obj.isinstance_Union():
    return all(_matches_generator(sub_type, allowed_types)
               for sub_type in type_obj.options)
  else:
    base_cls = type_obj
    if type_obj.isinstance_ParameterizedClass():
      base_cls = type_obj.base_cls
    return ((base_cls.isinstance_PyTDClass() and
             base_cls.name in allowed_types) or
            base_cls.isinstance_AMBIGUOUS_OR_EMPTY())


def matches_generator(type_obj):
  allowed_types = ("generator", "Iterable", "Iterator")
  return _matches_generator(type_obj, allowed_types)


def matches_async_generator(type_obj):
  allowed_types = ("asyncgenerator", "AsyncIterable", "AsyncIterator")
  return _matches_generator(type_obj, allowed_types)


def var_map(func, var):
  return (func(v) for v in var.data)


def eval_expr(vm, node, f_globals, f_locals, expr):
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
  with vm.errorlog.checkpoint() as record:
    try:
      code = vm.compile_src(expr, mode="eval")
    except pyc.CompileError as e:
      # We keep only the error message, since the filename and line number are
      # for a temporary file.
      vm.errorlog.python_compiler_error(None, 0, e.error)
      ret = vm.new_unsolvable(node)
    else:
      _, _, _, ret = vm.run_bytecode(node, code, f_globals, f_locals)
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
    check: (AtomicAbstractValue) -> bool.

  Returns:
    Whether the check passes.
  """
  return var and all(
      v.cls.isinstance_Class() and check(v.cls) for v in var.data if v.cls)


def match_type_container(typ, container_type_name: Union[str, Tuple[str, ...]]):
  """Unpack the type parameter from ContainerType[T]."""
  if typ is None:
    return None
  if isinstance(container_type_name, str):
    container_type_name = (container_type_name,)
  if not (typ.isinstance_ParameterizedClass() and
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
  return annots if annots.isinstance_AnnotationsDict() else None
