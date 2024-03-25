"""Base abstract representation of Python values."""

import abc
from typing import Any, Generic, Optional, Sequence, Set, Tuple, TypeVar

from pytype import utils
from pytype.rewrite.flow import variables
from typing_extensions import Self

_T = TypeVar('_T')


class BaseValue(abc.ABC):
  """Base class for abstract values."""

  @abc.abstractmethod
  def __repr__(self): ...

  @property
  @abc.abstractmethod
  def _attrs(self) -> Tuple[Any, ...]:
    """This object's identifying attributes.

    Used for equality comparisons and hashing. Should return a tuple of the
    attributes needed to differentiate this object from others of the same type.
    The attributes must be hashable. Do not include the type of `self`.
    """

  def __eq__(self, other):
    return self.__class__ == other.__class__ and self._attrs == other._attrs

  def __hash__(self):
    return hash((self.__class__,) + self._attrs)

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

  @property
  def _attrs(self):
    return (self.constant,)


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

  @property
  def _attrs(self):
    return (self.name,)


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
    self.options = tuple(utils.unique_list(flattened_options))

  def __repr__(self):
    return ' | '.join(repr(o) for o in self.options)

  @property
  def _attrs(self):
    return (frozenset(self.options),)


ANY = Singleton('ANY')
NULL = Singleton('NULL')

AbstractVariableType = variables.Variable[BaseValue]
