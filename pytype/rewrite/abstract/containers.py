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

  def append(self, val: _Variable):
    self.constant.append(val)

  def extend(self, val: _Variable):
    try:
      const = utils.get_atomic_constant(val)
      if not isinstance(const, list):
        const = None
    except ValueError:
      const = None

    if const:
      self.constant.extend(const)
    else:
      self.constant.append(internal.Splat(self._ctx, val).to_variable())


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

  def setitem(self, key, val):
    self.constant[key] = val

  def update(self, val: _Variable):
    try:
      const = utils.get_atomic_constant(val)
      if not isinstance(const, dict):
        const = None
    except ValueError:
      const = None

    if const:
      self.constant.update(const)
    else:
      self.indefinite = True


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
