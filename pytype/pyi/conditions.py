"""Process conditional blocks in pyi files."""

import sys
from typing import Optional, Tuple, Union

from pytype import utils
from pytype.ast import visitor as ast_visitor
from pytype.pyi.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import slots as cmp_slots

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


class ConditionEvaluator(ast_visitor.BaseVisitor):
  """Evaluates if statements in pyi files."""

  def __init__(self, options):
    super().__init__(ast=ast3)
    self._compares = {
        ast3.Eq: cmp_slots.EQ,
        ast3.Gt: cmp_slots.GT,
        ast3.Lt: cmp_slots.LT,
        ast3.GtE: cmp_slots.GE,
        ast3.LtE: cmp_slots.LE,
        ast3.NotEq: cmp_slots.NE
    }
    self._options = options

  def _eval_comparison(
      self, ident: Tuple[str, Optional[Union[int, slice]]], op: str,
      value: Union[str, int, Tuple[int, ...]]) -> bool:
    """Evaluate a comparison and return a bool.

    Args:
      ident: A tuple of a dotted name string and an optional __getitem__ key.
      op: One of the comparison operator strings in cmp_slots.COMPARES.
      value: The value to be compared against.

    Returns:
      The boolean result of the comparison.

    Raises:
      ParseError: If the comparison cannot be evaluated.
    """
    name, key = ident
    if name == "sys.version_info":
      if key is None:
        key = slice(None, None, None)
      if isinstance(key, int) and not isinstance(value, int):
        raise ParseError(
            "an element of sys.version_info must be compared to an integer")
      if isinstance(key, slice) and not _is_int_tuple(value):
        raise ParseError(
            "sys.version_info must be compared to a tuple of integers")
      try:
        actual = self._options.python_version[key]
      except IndexError as e:
        raise ParseError(utils.message(e)) from e
      if isinstance(key, slice):
        actual = _three_tuple(actual)
        value = _three_tuple(value)
    elif name == "sys.platform":
      if not isinstance(value, str):
        raise ParseError("sys.platform must be compared to a string")
      valid_cmps = (cmp_slots.EQ, cmp_slots.NE)
      if op not in valid_cmps:
        raise ParseError(
            "sys.platform must be compared using %s or %s" % valid_cmps)
      actual = self._options.platform
    else:
      raise ParseError(f"Unsupported condition: {name!r}.")
    return cmp_slots.COMPARES[op](actual, value)

  def fail(self, name=None):
    if name:
      msg = f"Unsupported condition: {name!r}. "
    else:
      msg = "Unsupported condition. "
    msg += "Supported checks are sys.platform and sys.version_info"
    raise ParseError(msg)

  def visit_Attribute(self, node):
    if not isinstance(node.value, ast3.Name):
      self.fail()
    name = f"{node.value.id}.{node.attr}"
    if node.value.id == "sys":
      return name
    elif node.value.id == "PYTYPE_OPTIONS":
      if hasattr(self._options, node.attr):
        return bool(getattr(self._options, node.attr))
    self.fail(name)

  def visit_Slice(self, node):
    return slice(node.lower, node.upper, node.step)

  def visit_Index(self, node):
    return node.value

  def visit_Constant(self, node):
    return node.value

  def visit_Num(self, node):
    return node.n

  def visit_Str(self, node):
    return node.s

  def visit_Subscript(self, node):
    return (node.value, node.slice)

  def visit_Tuple(self, node):
    return tuple(node.elts)

  def visit_BoolOp(self, node):
    if isinstance(node.op, ast3.Or):
      return any(node.values)
    elif isinstance(node.op, ast3.And):
      return all(node.values)
    else:
      raise ParseError(f"Unexpected boolean operator: {node.op}")

  def visit_UnaryOp(self, node):
    if isinstance(node.op, ast3.USub) and isinstance(node.operand, int):
      return -node.operand
    else:
      raise ParseError(f"Unexpected unary operator: {node.op}")

  def visit_Compare(self, node):
    if isinstance(node.left, tuple):
      ident = node.left
    else:
      ident = (node.left, None)
    op = self._compares[type(node.ops[0])]
    right = node.comparators[0]
    return self._eval_comparison(ident, op, right)


def evaluate(test: ast3.AST, options) -> bool:
  return ConditionEvaluator(options).visit(test)


def _is_int_tuple(value):
  """Return whether the value is a tuple of integers."""
  return isinstance(value, tuple) and all(isinstance(v, int) for v in value)


def _three_tuple(value):
  """Append zeros and slice to normalize the tuple to a three-tuple."""
  return (value + (0, 0))[:3]
