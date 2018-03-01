"""Compare two variables."""

from pytype import abstract

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
  if isinstance(value, abstract.PythonConstant):
    return value.pyval.__class__ in vm.convert.primitive_classes
  elif isinstance(value, abstract.Instance):
    return value.get_full_name() in vm.convert.primitive_class_names
  return False


def _compare_primitive_value(vm, left, right):
  if _is_primitive(vm, right) and isinstance(right, abstract.PythonConstant):
    return left.pyval == right.pyval
  else:
    return _compare_primitive(left, right)


def _compare_primitive(left, right):
  if (isinstance(right, abstract.Instance) and
      _incompatible(left.get_full_name(), right.get_full_name())):
    return False
  return None


def _compare_tuple(left, right):
  if (isinstance(right, abstract.Tuple) and
      left.tuple_length != right.tuple_length):
    return False
  return None


def _compare_dict(left, right):
  if (not left.could_contain_anything and
      isinstance(right, abstract.Dict) and
      not right.could_contain_anything and
      set(left.pyval) != set(right.pyval)):
    return False
  return None


def cmp_eq(vm, left, right):
  """Compare two variables."""
  if _is_primitive(vm, left) and isinstance(left, abstract.PythonConstant):
    return _compare_primitive_value(vm, left, right)
  elif _is_primitive(vm, left) and _is_primitive(vm, right):
    return _compare_primitive(left, right)
  elif isinstance(left, abstract.Tuple):
    return _compare_tuple(left, right)
  elif isinstance(left, abstract.Dict):
    return _compare_dict(left, right)
  else:
    return None
