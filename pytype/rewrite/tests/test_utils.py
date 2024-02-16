"""Test utilities."""

import sys
import textwrap
from typing import Sequence

from pytype.blocks import blocks
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype_extensions import instrumentation_for_testing as i4t


class FakeOrderedCode(i4t.ProductionType[blocks.OrderedCode]):

  def __init__(self, ops: Sequence[Sequence[opcodes.Opcode]], consts=()):
    self.order = [blocks.Block(block_ops) for block_ops in ops]
    self.consts = consts


def parse(src: str) -> blocks.OrderedCode:
  code = pyc.compile_src(
      src=textwrap.dedent(src),
      python_version=sys.version_info[:2],
      python_exe=None,
      filename='<inline>',
      mode='exec',
  )
  ordered_code, unused_block_graph = blocks.process_code(code)
  return ordered_code
