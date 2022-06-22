"""Base visitor for typed_ast parse trees."""

import sys

from pytype.ast import visitor as ast_visitor
from pytype.pyi import types
from pytype.pyi.types import ParseError  # pylint: disable=g-importing-member

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


class BaseVisitor(ast_visitor.BaseVisitor):
  """Base visitor for all typed_ast visitors.

  - Reraises ParseError with position information.
  - Handles literal constants
  - Has an optional Definitions member
  """

  def __init__(self, *, defs=None, filename=None):
    super().__init__(ast3, visit_decorators=False)
    self.defs = defs
    self.filename = filename  # used for error messages
    self.src_code = None  # set in subclass, used for error messages
    # Keep track of the name being subscripted. See AnnotationVisitor.visit_Name
    # for why this is needed.
    self.subscripted = []

  def _call_visitor(self, node):
    try:
      return super()._call_visitor(node)
    except Exception as e:  # pylint: disable=broad-except
      raise ParseError.from_exc(e).at(node, self.filename, self.src_code)

  def enter(self, node):
    try:
      return super().enter(node)
    except Exception as e:  # pylint: disable=broad-except
      raise ParseError.from_exc(e).at(node, self.filename, self.src_code)

  def leave(self, node):
    try:
      return super().leave(node)
    except Exception as e:  # pylint: disable=broad-except
      raise ParseError.from_exc(e).at(node, self.filename, self.src_code)

  def visit_Ellipsis(self, node):
    return self.defs.ELLIPSIS

  def visit_Constant(self, node):
    if node.value is Ellipsis:
      return self.defs.ELLIPSIS
    return types.Pyval.from_const(node)

  def visit_NameConstant(self, node):
    return types.Pyval.from_const(node)

  def visit_Num(self, node):
    return types.Pyval.from_num(node)

  def visit_Str(self, node):
    return types.Pyval.from_str(node)

  def visit_Bytes(self, node):
    return self.visit_Str(node)

  def visit_UnaryOp(self, node):
    if isinstance(node.op, ast3.USub):
      if isinstance(node.operand, types.Pyval):
        return node.operand.negated()
    raise ParseError(f"Unexpected unary operator: {node.op}")
