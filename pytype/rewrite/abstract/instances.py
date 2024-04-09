"""Abstract representations of class instances."""

import logging

from typing import Dict as _Dict, List as _List, Set as _Set, Tuple as _Tuple

from pytype.rewrite.abstract import base

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

  def append(self, val: _Variable):
    self.constant.append(val)


class Dict(base.PythonConstant[_Dict[_Variable, _Variable]]):
  """Representation of a Python dict."""

  def __init__(
      self, ctx: base.ContextType, constant: _Dict[_Variable, _Variable]
  ):
    assert isinstance(constant, dict), constant
    super().__init__(ctx, constant)

  def __repr__(self):
    return f'Dict({self.constant!r})'

  def setitem(self, key, val):
    self.constant[key] = val


class Set(base.PythonConstant[_Set[_Variable]]):
  """Representation of a Python set."""

  def __init__(self, ctx: base.ContextType, constant: _Set[_Variable]):
    assert isinstance(constant, set), constant
    super().__init__(ctx, constant)

  def __repr__(self):
    return f'Set({self.constant!r})'

  def add(self, val: _Variable):
    self.constant.add(val)


class Tuple(base.PythonConstant[_Tuple[_Variable, ...]]):
  """Representation of a Python tuple."""

  def __init__(self, ctx: base.ContextType, constant: _Tuple[_Variable, ...]):
    assert isinstance(constant, tuple), constant
    super().__init__(ctx, constant)

  def __repr__(self):
    return f'Tuple({self.constant!r})'
