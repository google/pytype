"""Variables, bindings, and conditions."""

import dataclasses
from typing import Generic, Optional, Tuple, TypeVar

_frozen_dataclass = dataclasses.dataclass(frozen=True)
_T = TypeVar('_T')
_T2 = TypeVar('_T2')


@_frozen_dataclass
class Condition:
  """A condition that must be satisified for a binding to apply."""

  def __repr__(self):
    if self is TRUE:
      return 'TRUE'
    elif self is FALSE:
      return 'FALSE'
    else:
      return super().__repr__()


TRUE = Condition()
FALSE = Condition()


@_frozen_dataclass
class Binding(Generic[_T]):
  """A binding to a value that applies when a condition is satisfied."""

  value: _T
  condition: Condition = TRUE

  def __repr__(self):
    if self.condition is TRUE:
      return f'Bind[{self.value}]'
    return f'Bind[{self.value} if {self.condition}]'


@_frozen_dataclass
class Variable(Generic[_T]):
  """A collection of bindings, optionally named."""

  bindings: Tuple[Binding[_T], ...]
  name: Optional[str] = None

  @classmethod
  def from_value(cls, value: _T2) -> 'Variable[_T2]':
    return cls((Binding(value),))

  def get_atomic_value(self) -> _T:
    """Gets this variable's value if there's exactly one, errors otherwise."""
    if len(self.bindings) != 1:
      desc = 'many' if len(self.bindings) > 1 else 'few'
      varname = f'variable {self.name}' if self.name else 'anonymous variable'
      raise ValueError(f'Too {desc} bindings for {varname}: {self.bindings}')
    return self.bindings[0].value

  def __repr__(self):
    bindings = ' | '.join(repr(b) for b in self.bindings)
    if self.name:
      return f'Var[{self.name} -> {bindings}]'
    return f'Var[{bindings}]'