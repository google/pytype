"""Test utilities."""

import sys
import textwrap
from typing import Sequence

from pytype.blocks import blocks
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.pytd.parse import parser_test_base
from pytype.rewrite import context
from pytype_extensions import instrumentation_for_testing as i4t

import unittest


class ContextfulTestBase(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.ctx = context.Context()


class PytdTestBase(parser_test_base.ParserTest):
  """Base for tests that build pytd objects."""

  def build_pytd(self, src, name=None):
    pytd_tree = self.ParseWithBuiltins(src)
    if name:
      member = pytd_tree.Lookup(name)
    else:
      # Ignore aliases because they may be imports.
      members = (pytd_tree.constants + pytd_tree.type_params +
                 pytd_tree.classes + pytd_tree.functions)
      assert len(members) == 1
      member, = members
      name = member.name
    return member.Replace(name=f'<test>.{name}')


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
