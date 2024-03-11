"""Data stack."""

from typing import List, Sequence

from pytype.rewrite.abstract import abstract
from pytype.rewrite.flow import variables


_AbstractVariable = variables.Variable[abstract.BaseValue]  # typing alias


class DataStack:
  """Data stack."""

  def __init__(self):
    self._stack: List[_AbstractVariable] = []

  def push(self, var: _AbstractVariable) -> None:
    self._stack.append(var)

  def pop(self) -> _AbstractVariable:
    return self._stack.pop()

  def popn(self, n) -> Sequence[_AbstractVariable]:
    if not n:
      return ()
    if len(self._stack) < n:
      raise IndexError(
          f'Trying to pop {n} values from stack of size {len(self._stack)}')
    values = self._stack[-n:]
    self._stack = self._stack[:-n]
    return values

  def pop_and_discard(self) -> None:
    _ = self._stack.pop()

  def top(self) -> _AbstractVariable:
    return self._stack[-1]

  def peek(self, n) -> _AbstractVariable:
    if n <= 0:
      raise IndexError(f'peek(n) requires positive n, got: {n}')
    if n > len(self._stack):
      raise IndexError(f'Trying to peek value {n} places down a stack of size '
                       f'{len(self._stack)}')
    return self._stack[-n]

  def __bool__(self):
    return bool(self._stack)

  def __len__(self):
    return len(self._stack)

  def __repr__(self):
    return f'DataStack{self._stack}'
