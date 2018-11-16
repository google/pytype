"""Compare two variables."""

from pytype import abstract
from pytype import mixin
from pytype.pytd import slots

# Equality classes.
NUMERIC = {"__builtin__.bool", "__builtin__.int", "__builtin__.float",
           "__builtin__.complex"}
STRING = {"__builtin__.str", "__builtin__.unicode"}


def _incompatible(left_name, right_name):
  """Incompatible primitive types can never be equal."""
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
