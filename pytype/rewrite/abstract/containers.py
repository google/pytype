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

  def extend(self, var: _Variable) -> base.BaseValue:
    try:
      val = var.get_atomic_value()
    except ValueError:
      # This list has multiple possible values, so it is no longer a constant.
      return self._ctx.abstract_loader.load_raw_type(list).instantiate()
    if isinstance(val, List):
      new_constant = self.constant + val.constant
    else:
      splat = internal.Splat(self._ctx, val)
      new_constant = self.constant + [splat.to_variable()]
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

  def setitem(self, key: _Variable, val: _Variable) -> 'Dict':
    return Dict(self._ctx, {**self.constant, key: val})

  def update(self, var: _Variable) -> base.BaseValue:
    try:
      val = var.get_atomic_value()
    except ValueError:
      # The update var has multiple possible values, so we cannot merge it into
      # the constant dict. We also don't know if items have been overwritten, so
      # we need to discard self.constant
      return Dict.any_dict(self._ctx)

    if not hasattr(val, 'constant'):
      # This is an object with no concrete python value
      return Dict.any_dict(self._ctx)
    elif isinstance(val, Dict):
      new_items = val.constant
    elif isinstance(val, internal.FunctionArgDict):
      new_items = {
          self._ctx.consts[k].to_variable(): v
          for k, v in val.constant.items()
      }
    else:
      raise ValueError('Unexpected dict update:', val)

    return Dict(
        self._ctx, {**self.constant, **new_items},
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
