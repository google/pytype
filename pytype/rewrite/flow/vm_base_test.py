from pytype.pyc import opcodes
from pytype.rewrite.flow import conditions
from pytype.rewrite.flow import vm_base
from pytype.rewrite.tests import test_utils

import unittest


class BlockStateTest(unittest.TestCase):

  def test_merge_into_none(self):
    b1 = vm_base._BlockState({})
    b2 = b1.merge_into(None)
    self.assertIsNot(b1, b2)
    self.assertFalse(b2.locals_)
    self.assertIs(b2.condition, conditions.TRUE)

  def test_merge_into_other(self):
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    b1 = vm_base._BlockState({}, c1)
    b2 = vm_base._BlockState({}, c2)
    b3 = b1.merge_into(b2)
    self.assertIs(b2, b3)
    self.assertEqual(b3.condition, conditions.Or(c1, c2))


# pylint: disable=invalid-name
class FAKE_OP(opcodes.Opcode):

  def __init__(self, index):
    super().__init__(index=index, line=0)


class FAKE_OP_NO_NEXT(opcodes.Opcode):

  _FLAGS = opcodes.NO_NEXT

  def __init__(self, index):
    super().__init__(index=index, line=0)
# pylint: enable=invalid-name


class TestVM(vm_base.VmBase):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.seen_opcodes = []

  # pylint: disable=invalid-name
  def byte_FAKE_OP(self, op):
    self.seen_opcodes.append(('FAKE_OP', op.index))

  def byte_FAKE_OP_NO_NEXT(self, op):
    self.seen_opcodes.append(('FAKE_OP_NO_NEXT', op.index))
  # pylint: enable=invalid-name


class VmBaseTest(unittest.TestCase):

  def test_one_block(self):
    op0 = FAKE_OP_NO_NEXT(0)
    code = test_utils.FakeOrderedCode([[op0]])
    vm = TestVM(code.Seal(), {})
    vm.step()
    self.assertEqual(vm.seen_opcodes, [('FAKE_OP_NO_NEXT', 0)])

  def test_two_blocks(self):
    op0 = FAKE_OP(0)
    op1 = FAKE_OP_NO_NEXT(1)
    op0.next = op1
    code = test_utils.FakeOrderedCode([[op0], [op1]])
    vm = TestVM(code.Seal(), {})
    vm.step()
    vm.step()
    self.assertEqual(vm.seen_opcodes, [('FAKE_OP', 0), ('FAKE_OP_NO_NEXT', 1)])

  def test_vm_consumed(self):
    op0 = FAKE_OP_NO_NEXT(0)
    code = test_utils.FakeOrderedCode([[op0]])
    vm = TestVM(code.Seal(), {})
    vm.step()
    with self.assertRaises(vm_base.VmConsumedError):
      vm.step()

  def test_merge_conditions(self):
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    op0 = FAKE_OP(0)
    op1 = FAKE_OP_NO_NEXT(1)
    op0.next = op1
    code = test_utils.FakeOrderedCode([[op0], [op1]])
    vm = TestVM(code.Seal(), {})
    vm._states[0] = vm_base._BlockState({}, c1)
    vm._states[1] = vm_base._BlockState({}, c2)
    vm.step()
    # Since FAKE_OP merges into the next op, the condition on the second block
    # should have been updated to (c1 or c2).
    condition = vm._states[1].condition
    self.assertEqual(condition, conditions.Or(c1, c2))

  def test_nomerge_conditions(self):
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    op0 = FAKE_OP_NO_NEXT(0)
    op1 = FAKE_OP_NO_NEXT(1)
    code = test_utils.FakeOrderedCode([[op0], [op1]])
    vm = TestVM(code.Seal(), {})
    vm._states[0] = vm_base._BlockState({}, c1)
    vm._states[1] = vm_base._BlockState({}, c2)
    vm.step()
    # Since FAKE_OP_NO_NEXT does not merge into the next op, the condition on
    # the second block should remain as c2.
    condition = vm._states[1].condition
    self.assertIs(condition, c2)


if __name__ == '__main__':
  unittest.main()
