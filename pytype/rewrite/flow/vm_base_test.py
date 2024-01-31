from typing import Sequence

from pytype.blocks import blocks
from pytype.pyc import opcodes
from pytype.rewrite.flow import conditions
from pytype.rewrite.flow import vm_base
from pytype_extensions import instrumentation_for_testing as i4t

import unittest


class BlockStateTest(unittest.TestCase):

  def test_merge_into_none(self):
    b1 = vm_base.BlockState({})
    b2 = b1.merge_into(None)
    self.assertIsNot(b1, b2)
    self.assertEmpty(b2.locals_)
    self.assertIs(b2.condition, conditions.TRUE)

  def test_merge_into_other(self):
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    b1 = vm_base.BlockState({}, c1)
    b2 = vm_base.BlockState({}, c2)
    b3 = b1.merge_into(b2)
    self.assertIs(b2, b3)
    self.assertEqual(b3.condition, conditions.Or(c1, c2))


# pylint: disable=invalid-name
class FAKE_OP1(opcodes.Opcode):

  def __init__(self, index):
    super().__init__(index=index, line=0)


class FAKE_OP2(opcodes.Opcode):

  _FLAGS = opcodes.NO_NEXT

  def __init__(self, index):
    super().__init__(index=index, line=0)


class FAKE_JUMP(opcodes.Opcode):

  _FLAGS = opcodes.NO_NEXT

  def __init__(self, index, next_, target):
    super().__init__(index=index, line=0)
    self.next = next_
    self.target = target
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

  def byte_FAKE_JUMP(self, op):
    for idx, condition in (op.next, op.target):
      assert idx not in self._states
      self._states[idx] = vm_base.BlockState({}, condition)


class VmBaseTest(unittest.TestCase):

  def test_one_block(self):
    op0 = FAKE_OP1(0)
    op1 = FAKE_OP2(1)
    op0.next = op1
    code = FakeOrderedCode([[op0, op1]])
    vm = TestVM(code.Seal(), {})
    vm.run()
    self.assertEqual(vm.seen_opcodes, [('OP1', 0), ('OP2', 1)])

  def test_two_blocks(self):
    op0 = FAKE_OP1(0)
    op1 = FAKE_OP2(1)
    op0.next = op1
    code = FakeOrderedCode([[op0], [op1]])
    vm = TestVM(code.Seal(), {})
    vm.run()
    self.assertEqual(vm.seen_opcodes, [('OP1', 0), ('OP2', 1)])

  def test_merge_conditions(self):
    # FAKE_JUMP(0) sets condition c1 on the block starting with FAKE_OP1(1) and
    # condition c2 on the block starting with FAKE_OP2(2). Since FAKE_OP1 merges
    # into the next op, the block starting with FAKE_OP2(2) should have
    # condition (c1 or c2).
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    op0 = FAKE_JUMP(0, (1, c1), (2, c2))
    op1 = FAKE_OP1(1)
    op2 = FAKE_OP2(2)
    op1.next = op2
    code = FakeOrderedCode([[op0], [op1], [op2]])
    vm = TestVM(code.Seal(), {})
    vm.run()
    condition = vm._states[2].condition
    self.assertEqual(condition, conditions.Or(c1, c2))

  def test_nomerge_conditions(self):
    # FAKE_JUMP(0) sets condition c1 on the block starting with FAKE_OP2(1) and
    # condition c2 on the block starting with FAKE_OP2(2). Since FAKE_OP2 does
    # not merge into the next op, the block starting with FAKE_OP2(2) should
    # have condition c2.
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    op0 = FAKE_JUMP(0, (1, c1), (2, c2))
    op1 = FAKE_OP2(1)
    op2 = FAKE_OP2(2)
    code = FakeOrderedCode([[op0], [op1], [op2]])
    vm = TestVM(code.Seal(), {})
    vm.run()
    condition = vm._states[2].condition
    self.assertIs(condition, c2)


if __name__ == '__main__':
  unittest.main()
