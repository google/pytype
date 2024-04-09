"""Variables, bindings, and conditions."""

import dataclasses
from typing import Any, Generic, Optional, Tuple, Type, TypeVar, get_origin, overload

from pytype.rewrite.flow import conditions

_frozen_dataclass = dataclasses.dataclass(frozen=True)
_T = TypeVar('_T')
_T2 = TypeVar('_T2')


@_frozen_dataclass
class Binding(Generic[_T]):
  """A binding to a value that applies when a condition is satisfied."""

  value: _T
  condition: conditions.Condition = conditions.TRUE

  def __repr__(self):
    if self.condition is conditions.TRUE:
      return f'Bind[{self.value}]'
    return f'Bind[{self.value} if {self.condition}]'


@_frozen_dataclass
class Variable(Generic[_T]):
  """A collection of bindings, optionally named."""

  bindings: Tuple[Binding[_T], ...]
  name: Optional[str] = None

  @classmethod
  def from_value(
      cls, value: _T2, *, name: Optional[str] = None) -> 'Variable[_T2]':
    return cls(bindings=(Binding(value),), name=name)

  @property
  def values(self) -> Tuple[_T, ...]:
    return tuple(b.value for b in self.bindings)

  def display_name(self) -> str:
    return f'variable {self.name}' if self.name else 'anonymous variable'

  @overload
  def get_atomic_value(self, typ: Type[_T2]) -> _T2: ...

  @overload
  def get_atomic_value(self, typ: None = ...) -> _T: ...

  def get_atomic_value(self, typ=None):
    """Gets this variable's value if there's exactly one, errors otherwise."""
    if len(self.bindings) != 1:
      desc = 'many' if len(self.bindings) > 1 else 'few'
      raise ValueError(
          f'Too {desc} bindings for {self.display_name()}: {self.bindings}')
    value = self.bindings[0].value
    if typ and not isinstance(value, (runtime_type := get_origin(typ) or typ)):
      raise ValueError(
          f'Wrong type for {self.display_name()}: expected '
          f'{runtime_type.__name__}, got {value.__class__.__name__}')
    return value

  def has_atomic_value(self, value: Any) -> bool:
    return len(self.values) == 1 and self.values[0] == value

  def with_condition(self, condition: conditions.Condition) -> 'Variable[_T]':
    """Adds a condition, 'and'-ing it with any existing."""
    if condition is conditions.TRUE:
      return self
    new_bindings = []
    for b in self.bindings:
      new_condition = conditions.And(b.condition, condition)
      new_bindings.append(dataclasses.replace(b, condition=new_condition))
    return dataclasses.replace(self, bindings=tuple(new_bindings))

  def with_name(self, name: Optional[str]) -> 'Variable[_T]':
    return dataclasses.replace(self, name=name)

  def __repr__(self):
    bindings = ' | '.join(repr(b) for b in self.bindings)
    if self.name:
      return f'Var[{self.name} -> {bindings}]'
    return f'Var[{bindings}]'
