"""Abstract representations of Python values."""

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

  def __init__(self, name: str, code: blocks.OrderedCode):
    self.name = name
    self.code = code

  def __repr__(self):
    return f'Function({self.name})'


class _Null(BaseValue):
  pass


NULL = _Null()
