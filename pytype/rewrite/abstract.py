"""Abstract representations of Python values."""

from typing import Any, Generic, Tuple, Type, TypeVar, get_origin, overload

from pytype.blocks import blocks
from pytype.rewrite.flow import variables

_T = TypeVar('_T')


class BaseValue:
  pass


class PythonConstant(BaseValue, Generic[_T]):

  def __init__(self, constant: _T):
    self.constant = constant

  def __repr__(self):
    return f'PythonConstant({self.constant!r})'

  def __eq__(self, other):
    return type(self) == type(other) and self.constant == other.constant  # pylint: disable=unidiomatic-typecheck


class Function(BaseValue):
  """Function with a code object."""

  def __init__(
      self,
      name: str,
      code: blocks.OrderedCode,
      enclosing_scope: Tuple[str, ...],
  ):
    self.name = name
    self.code = code
    self.enclosing_scope = enclosing_scope

  def __repr__(self):
    return f'Function({self.name})'


class Class(BaseValue):

  def __init__(self, name: str, body: Function):
    self.name = name
    self.body = body

  def __repr__(self):
    return f'Class({self.name})'


class _Null(BaseValue):

  def __repr__(self):
    return 'NULL'


class _BuildClass(BaseValue):

  def __repr__(self):
    return 'BUILD_CLASS'


NULL = _Null()
BUILD_CLASS = _BuildClass()


@overload
def get_atomic_constant(
    var: variables.Variable[BaseValue], typ: Type[_T]) -> _T: ...


@overload
def get_atomic_constant(
    var: variables.Variable[BaseValue], typ: None = ...) -> Any: ...


def get_atomic_constant(var, typ=None):
  value = var.get_atomic_value(PythonConstant)
  constant = value.constant
  if typ and not isinstance(constant, (runtime_type := get_origin(typ) or typ)):
    raise ValueError(
        f'Wrong constant type for {var.display_name()}: expected '
        f'{runtime_type.__name__}, got {constant.__class__.__name__}')
  return constant
