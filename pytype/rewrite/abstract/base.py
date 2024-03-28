"""Base abstract representation of Python values."""

import abc
from typing import Any, Dict, Generic, Optional, Protocol, Sequence, Tuple, TypeVar

from pytype import utils
from pytype.pytd import pytd
from pytype.rewrite.flow import variables
from pytype.types import types
from typing_extensions import Self

_T = TypeVar('_T')


class ContextType(Protocol):

  ANY: 'Singleton'
  BUILD_CLASS: 'Singleton'
  NULL: 'Singleton'

  errorlog: Any
  pytd_converter: Any


class BaseValue(types.BaseValue, abc.ABC):
  """Base class for abstract values."""

  def __init__(self, ctx: ContextType):
    self._ctx = ctx

  @abc.abstractmethod
  def __repr__(self): ...

  @property
  @abc.abstractmethod
  def _attrs(self) -> Tuple[Any, ...]:
    """This object's identifying attributes.

    Used for equality comparisons and hashing. Should return a tuple of the
    attributes needed to differentiate this object from others of the same type.
    The attributes must be hashable. Do not include the type of `self` or
    `self._ctx`.
    """

  def __eq__(self, other):
    return self.__class__ == other.__class__ and self._attrs == other._attrs

  def __hash__(self):
    return hash((self.__class__, self._ctx) + self._attrs)

  def to_variable(self: Self) -> variables.Variable[Self]:
    return variables.Variable.from_value(self)

  def get_attribute(self, name: str) -> Optional['BaseValue']:
    del name  # unused
    return None

  def set_attribute(self, name: str, value: 'BaseValue') -> None:
    del name, value  # unused

  def to_pytd_def(self) -> pytd.Node:
    return self._ctx.pytd_converter.to_pytd_def(self)

  def to_pytd_type(self) -> pytd.Type:
    return self._ctx.pytd_converter.to_pytd_type(self)

  def to_pytd_type_of_instance(self) -> pytd.Type:
    return self._ctx.pytd_converter.to_pytd_type_of_instance(self)


class PythonConstant(BaseValue, Generic[_T]):

  def __init__(self, ctx: ContextType, constant: _T):
    super().__init__(ctx)
    self.constant = constant

  def __repr__(self):
    return f'PythonConstant({self.constant!r})'

  @property
  def _attrs(self):
    return (self.constant,)


class Singleton(BaseValue):
  """Singleton value."""

  _INSTANCES: Dict[Tuple[ContextType, str], 'Singleton'] = {}
  name: str

  def __new__(cls, ctx: ContextType, name: str):
    key = (ctx, name)
    if key in cls._INSTANCES:
      return cls._INSTANCES[key]
    self = super().__new__(cls)
    cls._INSTANCES[key] = self
    return self

  def __init__(self, ctx, name):
    super().__init__(ctx)
    self.name = name

  def __repr__(self):
    return self.name

  @property
  def _attrs(self):
    return (self.name,)


class Union(BaseValue):
  """Union of values."""

  def __init__(self, ctx: ContextType, options: Sequence[BaseValue]):
    super().__init__(ctx)
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

AbstractVariableType = variables.Variable[BaseValue]
