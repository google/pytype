"""Abstract representations of Python values."""

from typing import Tuple

from pytype.blocks import blocks


class BaseValue:
  pass


class PythonConstant(BaseValue):

  def __init__(self, constant):
    self.constant = constant

  def __repr__(self):
    return f'PythonConstant({self.constant!r})'

  def __eq__(self, other):
    return type(self) == type(other) and self.constant == other.constant  # pylint: disable=unidiomatic-typecheck


class Function(BaseValue):
  """Function with a code object."""

  def __init__(
      self, name: str,
      code: blocks.OrderedCode,
      enclosing_scope: Tuple[str, ...],
  ):
    self.name = name
    self.code = code
    self.enclosing_scope = enclosing_scope

  def __repr__(self):
    return f'Function({self.name})'


class _Null(BaseValue):
  pass


NULL = _Null()
