"""Do comparisons involving abstract values."""

from pytype import abstract
from pytype import abstract_utils
from pytype import mixin
from pytype.pytd import slots

# Equality classes.
NUMERIC = {"__builtin__.bool", "__builtin__.int", "__builtin__.float",
           "__builtin__.complex"}
STRING = {"__builtin__.str", "__builtin__.unicode"}

# Fully qualified names of types that are parameterized containers.
_CONTAINER_NAMES = {
    "__builtin__.list", "__builtin__.set", "__builtin__.frozenset"}


def _incompatible(left_name, right_name):
  """Incompatible primitive types can never be equal."""
  if left_name == right_name:
    return False
  for group in NUMERIC, STRING:
    if left_name in group and right_name in group:
      return False
  return True


def _is_primitive(vm, value):
  if isinstance(value, mixin.PythonConstant):
    return value.pyval.__class__ in vm.convert.primitive_classes
  elif isinstance(value, abstract.Instance):
    return value.full_name in vm.convert.primitive_class_names
  return False


def _is_equality_cmp(op):
  return op in (slots.EQ, slots.NE)


def _compare_primitive_value(vm, op, left, right):
  if _is_primitive(vm, right) and isinstance(right, mixin.PythonConstant):
    try:
      return slots.COMPARES[op](left.pyval, right.pyval)
    except TypeError:
      # TODO(rechen): In host Python 3, some types are not comparable; e.g.,
      # `3 < ""` leads to a type error. We should do a Python 2-style comparison
      # for target Python 2 and log an error for target Python 3.
      pass
  return _compare_primitive(op, left, right)


def _compare_primitive(op, left, right):
  # Determines when primitives are definitely not equal by checking for
  # compatibility of their types.
  if (_is_equality_cmp(op) and
      isinstance(right, abstract.Instance) and
      _incompatible(left.full_name, right.full_name)):
    return op != slots.EQ
  return None


def _compare_tuple(op, left, right):
  # Determines when tuples are definitely not equal by checking their lengths.
  if (_is_equality_cmp(op) and
      isinstance(right, abstract.Tuple) and
      left.tuple_length != right.tuple_length):
    return op != slots.EQ
  return None


def _compare_dict(op, left, right):
  # Determines when dicts are definitely not equal by checking their key sets.
  if (_is_equality_cmp(op) and
      not left.could_contain_anything and
      isinstance(right, abstract.Dict) and
      not right.could_contain_anything and
      set(left.pyval) != set(right.pyval)):
    return op != slots.EQ
  return None


def cmp_rel(vm, op, left, right):
  """Compare two variables."""
  if _is_primitive(vm, left) and isinstance(left, mixin.PythonConstant):
    return _compare_primitive_value(vm, op, left, right)
  elif _is_primitive(vm, left) and _is_primitive(vm, right):
    return _compare_primitive(op, left, right)
  elif isinstance(left, abstract.Tuple):
    return _compare_tuple(op, left, right)
  elif isinstance(left, abstract.Dict):
    return _compare_dict(op, left, right)
  else:
    return None


def compatible_with(value, logical_value):
  """Returns the conditions under which the value could be True or False.

  Args:
    value: An abstract value.
    logical_value: Either True or False.

  Returns:
    False: If the value could not evaluate to logical_value under any
        circumstance (e.g. value is the empty list and logical_value is True).
    True: If it is possible for the value to evaluate to the logical_value,
        and any ambiguity cannot be resolved by additional bindings.
  """
  if isinstance(value, abstract.List) and value.could_contain_anything:
    return True
  elif isinstance(value, abstract.Dict) and value.could_contain_anything:
    # Always compatible with False. Compatible with True only if type
    # parameters have been established (meaning that the dict can be
    # non-empty).
    return (not logical_value or
            bool(value.get_instance_type_parameter(abstract_utils.K).bindings))
  elif isinstance(value, abstract.LazyConcreteDict):
    return value.is_empty() != logical_value
  elif isinstance(value, mixin.PythonConstant):
    return bool(value.pyval) == logical_value
  elif isinstance(value, abstract.Instance):
    # Containers with unset parameters and NoneType instances cannot match True.
    name = value.full_name
    if logical_value and name in _CONTAINER_NAMES:
      return (
          value.has_instance_type_parameter(abstract_utils.T) and
          bool(value.get_instance_type_parameter(abstract_utils.T).bindings))
    elif name == "__builtin__.NoneType":
      return not logical_value
    return True
  elif isinstance(value, (abstract.Function, mixin.Class)):
    # Functions and classes always evaluate to True.
    return logical_value
  else:
    # By default a value is ambiguous - it could potentially evaluate to either
    # True or False. Thus we return True here regardless of logical_value.
    return True
