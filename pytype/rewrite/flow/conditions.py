"""Variables, bindings, and conditions."""

import dataclasses
from typing import ClassVar, Tuple

_frozen_dataclass = dataclasses.dataclass(frozen=True)


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
class _Composite(Condition):
  """Composition of conditions."""

  conditions: Tuple[Condition, ...]

  _ACCEPT: ClassVar[Condition]
  _IGNORE: ClassVar[Condition]
  _REPR: ClassVar[str]

  @classmethod
  def make(cls, *args: Condition):
    if any(arg is cls._ACCEPT for arg in args):
      return cls._ACCEPT
    conditions = tuple(arg for arg in args if arg is not cls._IGNORE)
    if not conditions:
      return cls._IGNORE
    if len(conditions) == 1:
      return conditions[0]
    return cls(conditions)

  def __repr__(self):
    conditions = []
    for c in self.conditions:
      if isinstance(c, _Composite):
        conditions.append(f'({repr(c)})')
      else:
        conditions.append(repr(c))
    return f' {self._REPR} '.join(conditions)


@_frozen_dataclass
class _Or(_Composite):

  _ACCEPT: ClassVar[Condition] = TRUE
  _IGNORE: ClassVar[Condition] = FALSE
  _REPR: ClassVar[str] = 'or'


@_frozen_dataclass
class _And(_Composite):

  _ACCEPT: ClassVar[Condition] = FALSE
  _IGNORE: ClassVar[Condition] = TRUE
  _REPR: ClassVar[str] = 'and'


Or = _Or.make
And = _And.make
