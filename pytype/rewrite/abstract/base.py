"""Base abstract representation of Python values."""

from typing import Generic, Optional, Sequence, Set, TypeVar

from pytype.rewrite.flow import variables
from typing_extensions import Self

_T = TypeVar('_T')


class BaseValue:

  def to_variable(self: Self) -> variables.Variable[Self]:
    return variables.Variable.from_value(self)

  def get_attribute(self, name: str) -> Optional['BaseValue']:
    del name  # unused
    return None

  def set_attribute(self, name: str, value: 'BaseValue') -> None:
    del name, value  # unused


class PythonConstant(BaseValue, Generic[_T]):

  def __init__(self, constant: _T):
    self.constant = constant

  def __repr__(self):
    return f'PythonConstant({self.constant!r})'

  def __eq__(self, other):
    return type(self) == type(other) and self.constant == other.constant  # pylint: disable=unidiomatic-typecheck


class Singleton(BaseValue):
  """Singleton value."""

  _INSTANCES: Set[str] = set()
  name: str

  def __new__(cls, name: str):
    if name in cls._INSTANCES:
      raise ValueError(f'Duplicate singleton: {name}')
    cls._INSTANCES.add(name)
    self = super().__new__(cls)
    self.name = name
    return self

  def __repr__(self):
    return self.name


class Union(BaseValue):
  """Union of values."""

  def __init__(self, options: Sequence[BaseValue]):
    assert len(options) > 1
    flattened_options = []
    for o in options:
      if isinstance(o, Union):
        flattened_options.extend(o.options)
      else:
        flattened_options.append(o)
    # TODO(b/324464329): Deduplicate options.
    self.options = tuple(flattened_options)

  def __repr__(self):
    return ' | '.join(repr(o) for o in self.options)


ANY = Singleton('ANY')
NULL = Singleton('NULL')

AbstractVariableType = variables.Variable[BaseValue]
