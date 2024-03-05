"""Abstract representations of functions."""

from typing import Tuple

from pytype.blocks import blocks
from pytype.rewrite.abstract import base


class Function(base.BaseValue):
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
