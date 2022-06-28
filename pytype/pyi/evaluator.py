"""Evaluate subtrees corresponding to python literals.

This is a modified copy of typed_ast.ast3.literal_eval. The latter doesn't
handle Name nodes, so it would not handle something like "{'type': A}". Our
version converts that to "{'type': 'A'}" which is consistent with
auto-stringifying type annotations.

We also separate out string and node evaluation into separate functions.
"""

import sys

from pytype.pyi import types

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


_NUM_TYPES = (int, float, complex)


# pylint: disable=invalid-unary-operand-type
def _convert(node):
  """Helper function for literal_eval."""
  if isinstance(node, ast3.Constant):  # pytype: disable=module-attr
    return node.value
  elif isinstance(node, (ast3.Str, ast3.Bytes)):
    return node.s
  elif isinstance(node, ast3.Num):
    return node.n
  elif isinstance(node, ast3.Tuple):
    return tuple(map(_convert, node.elts))
  elif isinstance(node, ast3.List):
    return list(map(_convert, node.elts))
  elif isinstance(node, ast3.Set):
    return set(map(_convert, node.elts))
  elif isinstance(node, ast3.Dict):
    return {_convert(k): _convert(v) for k, v in zip(node.keys, node.values)}
  elif isinstance(node, ast3.NameConstant):
    return node.value
  elif isinstance(node, ast3.Name):
    return node.id
  elif isinstance(node, types.Pyval):
    return node.value
  elif node.__class__.__name__ == "NamedType" and node.name == "None":
    # We convert None to pytd.NamedType('None') in types.Pyval
    return None
  elif (isinstance(node, ast3.UnaryOp) and
        isinstance(node.op, (ast3.UAdd, ast3.USub))):
    operand = _convert(node.operand)
    if isinstance(operand, _NUM_TYPES):
      if isinstance(node.op, ast3.UAdd):
        return operand
      else:
        return -operand
  elif (isinstance(node, ast3.BinOp) and
        isinstance(node.op, (ast3.Add, ast3.Sub))):
    left = _convert(node.left)
    right = _convert(node.right)
    if isinstance(left, _NUM_TYPES) and isinstance(right, _NUM_TYPES):
      if isinstance(node.op, ast3.Add):
        return left + right
      else:
        return left - right
  raise ValueError("Cannot evaluate node: " + repr(node))
# pylint: enable=invalid-unary-operand-type


def literal_eval(node):
  """Modified version of ast3.literal_eval, handling things like typenames."""
  if isinstance(node, ast3.Expression):
    node = node.body
  if isinstance(node, ast3.Expr):
    node = node.value
  return _convert(node)


def eval_string_literal(src: str):
  return literal_eval(ast3.parse(src, mode="eval"))
