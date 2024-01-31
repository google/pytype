from typing import Sequence

from pytype.blocks import blocks
from pytype.pyc import opcodes
from pytype.rewrite.flow import vm_base
from pytype_extensions import instrumentation_for_testing as i4t

import unittest


# pylint: disable=invalid-name
class FAKE_OP1(opcodes.Opcode):

  def __init__(self, index):
    super().__init__(index=index, line=0)


class FAKE_OP2(opcodes.Opcode):

  _FLAGS = opcodes.NO_NEXT

  def __init__(self, index):
    super().__init__(index=index, line=0)
# pylint: enable=invalid-name


class FakeOrderedCode(i4t.ProductionType[blocks.OrderedCode]):

  def __init__(self, ops: Sequence[Sequence[opcodes.Opcode]]):
    self.order = [blocks.Block(block_ops) for block_ops in ops]


class TestVM(vm_base.VmBase):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.seen_opcodes = []

  def byte_FAKE_OP1(self, op):
    self.seen_opcodes.append(('OP1', op.index))

  def byte_FAKE_OP2(self, op):
    self.seen_opcodes.append(('OP2', op.index))


class VmBaseTest(unittest.TestCase):

  def test_one_block(self):
    op1 = FAKE_OP1(0)
    op2 = FAKE_OP2(1)
    op1.next = op2
    code = FakeOrderedCode([[op1, op2]])
    vm = TestVM(code.Seal(), {})
    vm.run()
    self.assertEqual(vm.seen_opcodes, [('OP1', 0), ('OP2', 1)])

  def test_two_blocks(self):
    op1 = FAKE_OP1(0)
    op2 = FAKE_OP2(1)
    op1.next = op2
    code = FakeOrderedCode([[op1], [op2]])
    vm = TestVM(code.Seal(), {})
    vm.run()
    self.assertEqual(vm.seen_opcodes, [('OP1', 0), ('OP2', 1)])

  # TODO(b/241479600): Test block state merging and not merging


if __name__ == '__main__':
  unittest.main()
