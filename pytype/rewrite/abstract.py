"""Abstract representations of Python values."""


class BaseValue:
  pass


class PythonConstant(BaseValue):

  def __init__(self, constant):
    self.constant = constant

  def __repr__(self):
    return f'PythonConstant({self.constant!r})'

  def __eq__(self, other):
    return type(self) == type(other) and self.constant == other.constant  # pylint: disable=unidiomatic-typecheck
