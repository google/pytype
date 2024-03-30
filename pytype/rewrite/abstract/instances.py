"""Abstract representations of class instances."""

import logging

from typing import Dict as _Dict, List as _List

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import classes

log = logging.getLogger(__name__)

# Type aliases
_Variable = base.AbstractVariableType


class List(classes.PythonConstant[_List[_Variable]]):
  """Representation of a Python list."""

  def __init__(self, ctx: base.ContextType, constant: _List[_Variable]):
    assert isinstance(constant, list), constant
    super().__init__(ctx, constant)


class Dict(classes.PythonConstant[_Dict[_Variable, _Variable]]):
  """Representation of a Python dict."""

  def __init__(
      self, ctx: base.ContextType, constant: _Dict[_Variable, _Variable]
  ):
    assert isinstance(constant, dict), constant
    super().__init__(ctx, constant)
