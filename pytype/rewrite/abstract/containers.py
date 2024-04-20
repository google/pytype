"""Abstract representations of builtin containers."""

import logging

from typing import Dict as _Dict, List as _List, Set as _Set, Tuple as _Tuple

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import internal
from pytype.rewrite.abstract import utils

log = logging.getLogger(__name__)

# Type aliases
_Variable = base.AbstractVariableType


class List(base.PythonConstant[_List[_Variable]]):
  """Representation of a Python list."""

  def __init__(self, ctx: base.ContextType, constant: _List[_Variable]):
    assert isinstance(constant, list), constant
    super().__init__(ctx, constant)

  def __repr__(self):
    return f'List({self.constant!r})'

  def append(self, var: _Variable) -> 'List':
    return List(self._ctx, self.constant + [var])

  def extend(self, val: 'List') -> 'List':
    new_constant = self.constant + val.constant
    return List(self._ctx, new_constant)


class Dict(base.PythonConstant[_Dict[_Variable, _Variable]]):
  """Representation of a Python dict."""

  def __init__(
      self, ctx: base.ContextType, constant: _Dict[_Variable, _Variable],
      indefinite: bool = False
  ):
    assert isinstance(constant, dict), constant
    super().__init__(ctx, constant)
    self.indefinite = indefinite

  def __repr__(self):
    indef = '+' if self.indefinite else ''
    return f'Dict({indef}{self.constant!r})'

  @classmethod
  def any_dict(cls, ctx):
    return cls(ctx, {}, indefinite=True)

  @classmethod
  def from_function_arg_dict(
      cls, ctx: base.ContextType, val: internal.FunctionArgDict
  ) -> 'Dict':
    new_constant = {
        ctx.consts[k].to_variable(): v
        for k, v in val.constant.items()
    }
    return cls(ctx, new_constant, val.indefinite)

  def setitem(self, key: _Variable, val: _Variable) -> 'Dict':
    return Dict(self._ctx, {**self.constant, key: val})

  def update(self, val: 'Dict') -> base.BaseValue:
    return Dict(
        self._ctx, {**self.constant, **val.constant},
        self.indefinite or val.indefinite
    )

  def to_function_arg_dict(self) -> internal.FunctionArgDict:
    new_const = {
        utils.get_atomic_constant(k, str): v
        for k, v in self.constant.items()
    }
    return internal.FunctionArgDict(self._ctx, new_const, self.indefinite)


class Set(base.PythonConstant[_Set[_Variable]]):
  """Representation of a Python set."""

  def __init__(self, ctx: base.ContextType, constant: _Set[_Variable]):
    assert isinstance(constant, set), constant
    super().__init__(ctx, constant)

  def __repr__(self):
    return f'Set({self.constant!r})'

  def add(self, val: _Variable) -> 'Set':
    return Set(self._ctx, self.constant | {val})


class Tuple(base.PythonConstant[_Tuple[_Variable, ...]]):
  """Representation of a Python tuple."""

  def __init__(self, ctx: base.ContextType, constant: _Tuple[_Variable, ...]):
    assert isinstance(constant, tuple), constant
    super().__init__(ctx, constant)

  def __repr__(self):
    return f'Tuple({self.constant!r})'
