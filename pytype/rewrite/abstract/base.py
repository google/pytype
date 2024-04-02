"""Base abstract representation of Python values."""

import abc
import dataclasses
from typing import Any, Dict, Optional, Protocol, Sequence, Tuple

from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import pytd
from pytype.rewrite.flow import variables
from pytype.types import types
from typing_extensions import Self


@dataclasses.dataclass(init=False)
class Singletons:
  """Singleton abstract values."""

  # For readability, we give these the same name as the value they represent.
  # pylint: disable=invalid-name
  Any: 'Singleton'
  __build_class__: 'Singleton'
  Never: 'Singleton'
  NULL: 'Singleton'
  # pylint: enable=invalid-name

  def __init__(self, ctx: 'ContextType'):
    for field in dataclasses.fields(self):
      setattr(self, field.name, Singleton(ctx, field.name))


class ContextType(Protocol):

  options: config.Options
  pytd_loader: load_pytd.Loader

  singles: Singletons
  errorlog: Any
  abstract_converter: Any
  abstract_loader: Any
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

  def instantiate(self) -> 'BaseValue':
    """Creates an instance of this value."""
    raise ValueError(f'{self!r} is not instantiable')

  def to_pytd_def(self) -> pytd.Node:
    return self._ctx.pytd_converter.to_pytd_def(self)

  def to_pytd_type(self) -> pytd.Type:
    return self._ctx.pytd_converter.to_pytd_type(self)

  def to_pytd_type_of_instance(self) -> pytd.Type:
    return self._ctx.pytd_converter.to_pytd_type_of_instance(self)


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

  def instantiate(self) -> 'Singleton':
    return self


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

  def instantiate(self):
    return Union(self._ctx, tuple(o.instantiate() for o in self.options))

AbstractVariableType = variables.Variable[BaseValue]
