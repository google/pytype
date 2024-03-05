"""Utilities for working with abstract values."""

from typing import Any, Type, TypeVar, get_origin, overload

from pytype.rewrite.abstract import base
from pytype.rewrite.flow import variables

_T = TypeVar('_T')

_AbstractVariable = variables.Variable[base.BaseValue]


@overload
def get_atomic_constant(var: _AbstractVariable, typ: Type[_T]) -> _T: ...


@overload
def get_atomic_constant(var: _AbstractVariable, typ: None = ...) -> Any: ...


def get_atomic_constant(var, typ=None):
  value = var.get_atomic_value(base.PythonConstant)
  constant = value.constant
  if typ and not isinstance(constant, (runtime_type := get_origin(typ) or typ)):
    raise ValueError(
        f'Wrong constant type for {var.display_name()}: expected '
        f'{runtime_type.__name__}, got {constant.__class__.__name__}')
  return constant
