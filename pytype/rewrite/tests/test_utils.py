"""Test utilities."""

from typing import Sequence

from pytype.blocks import blocks
from pytype.pyc import opcodes
from pytype_extensions import instrumentation_for_testing as i4t


class FakeOrderedCode(i4t.ProductionType[blocks.OrderedCode]):

  def __init__(self, ops: Sequence[Sequence[opcodes.Opcode]], consts=()):
    self.order = [blocks.Block(block_ops) for block_ops in ops]
    self.consts = consts
