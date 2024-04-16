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
      self, ctx: base.ContextType, constant: _Dict[_Variable, _Variable]
  ):
    assert isinstance(constant, dict), constant
    super().__init__(ctx, constant)
    self.indefinite = False

  def __repr__(self):
    return f'Dict({self.constant!r})'

  def setitem(self, key: _Variable, val: _Variable) -> 'Dict':
    return Dict(self._ctx, {**self.constant, key: val})

  def update(self, var: _Variable) -> base.BaseValue:
    try:
      val = utils.get_atomic_constant(var, dict)
    except ValueError:
      # This dict has multiple possible values, so it is no longer a constant.
      return self._ctx.abstract_loader.load_raw_type(dict).instantiate()
    return Dict(self._ctx, {**self.constant, **val})


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
