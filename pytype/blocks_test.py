"""Tests for blocks.py.

To create test cases, you can disassemble source code with the help of the dis
module. For example, in Python 3.7, this snippet:

  import dis
  import opcode
  def f(): return None
  bytecode = dis.Bytecode(f)
  for x in bytecode.codeobj.co_code:
    print(f'{x} ({opcode.opname[x]})')

prints:

  100 (LOAD_CONST)
  0 (<0>)
  83 (RETURN_VALUE)
  0 (<0>)
"""

from pytype import blocks
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.tests import test_utils

import unittest


class BaseBlocksTest(unittest.TestCase, test_utils.MakeCodeMixin):
  """A base class for implementing tests testing blocks.py."""

  # These tests check disassembled bytecode, which varies from version to
  # version, so we fix the test version.
  python_version = (3, 7)


class OrderingTest(BaseBlocksTest):
  """Tests for order_code in blocks.py."""

  def _order_code(self, code):
    """Helper function to disassemble and then order code."""
    disassembled_code = pyc.visit(code, blocks.DisCodeVisitor())
    return blocks.order_code(disassembled_code, self.python_version)

  def test_trivial(self):
    # Disassembled from:
    # | return None
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="trivial")
    ordered_code = self._order_code(co)
    b0, = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertCountEqual([], b0.incoming)
    self.assertCountEqual([], b0.outgoing)

  def test_has_opcode(self):
    # Disassembled from:
    # | return None
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="trivial")
    ordered_code = self._order_code(co)
    self.assertTrue(ordered_code.has_opcode(opcodes.LOAD_CONST))
    self.assertTrue(ordered_code.has_opcode(opcodes.RETURN_VALUE))
    self.assertFalse(ordered_code.has_opcode(opcodes.POP_TOP))

  def test_yield(self):
    # Disassembled from:
    # | yield 1
    # | yield None
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_CONST, 0,
        o.YIELD_VALUE, 0,
        # b1:
        o.POP_TOP, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="yield")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "yield")
    b0, b1 = ordered_code.order
    self.assertCountEqual(b0.outgoing, [b1])
    self.assertCountEqual(b1.incoming, [b0])
    self.assertCountEqual(b0.incoming, [])
    self.assertCountEqual(b1.outgoing, [])

  def test_triangle(self):
    # Disassembled from:
    # | x = y
    # | if y > 1:
    # |   x -= 2
    # | return x
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_GLOBAL, 0,
        o.STORE_FAST, 0,
        o.LOAD_GLOBAL, 0,
        o.LOAD_CONST, 1,
        o.COMPARE_OP, 4,
        o.POP_JUMP_IF_FALSE, 20,
        # b1:
        o.LOAD_FAST, 0,
        o.LOAD_CONST, 2,
        o.INPLACE_SUBTRACT, 0,
        o.STORE_FAST, 0,
        # b2:
        o.LOAD_FAST, 0,
        o.RETURN_VALUE, 0,
    ], name="triangle")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "triangle")
    b0, b1, b2 = ordered_code.order
    self.assertCountEqual(b0.incoming, [])
    self.assertCountEqual(b0.outgoing, [b1, b2])
    self.assertCountEqual(b1.incoming, [b0])
    self.assertCountEqual(b1.outgoing, [b2])
    self.assertCountEqual(b2.incoming, [b0, b1])
    self.assertCountEqual(b2.outgoing, [])

  def test_diamond(self):
    # Disassembled from:
    # | x = y
    # | if y > 1:
    # |   x -= 2
    # | else:
    # |   x += 2
    # | return x
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_GLOBAL, 0,
        o.STORE_FAST, 0,
        o.LOAD_GLOBAL, 0,
        o.LOAD_CONST, 1,
        o.COMPARE_OP, 4,
        o.POP_JUMP_IF_FALSE, 22,
        # b1:
        o.LOAD_FAST, 0,
        o.LOAD_CONST, 2,
        o.INPLACE_SUBTRACT, 0,
        o.STORE_FAST, 0,
        o.JUMP_FORWARD, 8,
        # b2:
        o.LOAD_FAST, 0,
        o.LOAD_CONST, 2,
        o.INPLACE_ADD, 0,
        o.STORE_FAST, 0,
        # b3:
        o.LOAD_FAST, 0,
        o.RETURN_VALUE, 0,
    ], name="diamond")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "diamond")
    b0, b1, b2, b3 = ordered_code.order
    self.assertCountEqual(b0.incoming, [])
    self.assertCountEqual(b0.outgoing, [b1, b2])
    self.assertCountEqual(b1.incoming, [b0])
    self.assertCountEqual(b1.outgoing, [b3])
    self.assertCountEqual(b2.incoming, [b0])
    self.assertCountEqual(b2.outgoing, [b3])
    self.assertCountEqual(b3.incoming, [b1, b2])
    self.assertCountEqual(b3.outgoing, [])

  def test_raise(self):
    # Disassembled from:
    # | raise ValueError()
    # | return 1
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_GLOBAL, 0,
        o.CALL_FUNCTION, 0,
        o.RAISE_VARARGS, 1,
        o.LOAD_CONST, 1,
        o.RETURN_VALUE, 0,  # dead.
    ], name="raise")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "raise")
    b0, b1 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertCountEqual(b0.incoming, [])
    self.assertCountEqual(b0.outgoing, [b1])
    self.assertCountEqual(b1.incoming, [b0])
    self.assertCountEqual(b1.outgoing, [])

  def test_call(self):
    # Disassembled from:
    # | f()
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_GLOBAL, 0,
        o.CALL_FUNCTION, 0,
        # b1:
        o.POP_TOP, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="call")
    ordered_code = self._order_code(co)
    b0, b1 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertEqual(len(b1.code), 3)
    self.assertCountEqual(b0.outgoing, [b1])

  def test_finally(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | finally:
    # |   pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.SETUP_FINALLY, 4,
        o.POP_BLOCK, 0,
        # b1:
        o.LOAD_CONST, 0,
        # b2:
        o.END_FINALLY, 0,
        # b3:
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="finally")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertEqual(len(b1.code), 1)
    self.assertEqual(len(b2.code), 1)
    self.assertEqual(len(b3.code), 2)
    self.assertCountEqual(b0.outgoing, [b1, b2])

  def test_except(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | except:
    # |   pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.SETUP_EXCEPT, 4,
        o.POP_BLOCK, 0,
        # b1:
        o.JUMP_FORWARD, 12,
        # b2:
        o.POP_TOP, 0,
        o.POP_TOP, 0,
        o.POP_TOP, 0,
        o.POP_EXCEPT, 0,
        o.JUMP_FORWARD, 2,
        # b3:
        o.END_FINALLY, 0,
        # b4:
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="except")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertEqual(len(b1.code), 1)
    self.assertEqual(len(b2.code), 5)
    self.assertEqual(len(b3.code), 2)
    self.assertCountEqual([b1, b2], b0.outgoing)
    self.assertCountEqual([b3], b1.outgoing)
    self.assertCountEqual([b3], b2.outgoing)

  def test_return(self):
    # Disassembled from:
    # | return None
    # | return None
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,  # dead.
        o.LOAD_CONST, 1,  # dead.
        o.RETURN_VALUE, 0,  # dead.
    ], name="return")
    ordered_code = self._order_code(co)
    b0, = ordered_code.order
    self.assertEqual(len(b0.code), 2)

  def test_with(self):
    # Disassembled from:
    # | with None:
    # |   pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_CONST, 0,
        o.SETUP_WITH, 6,
        o.POP_TOP, 0,
        o.POP_BLOCK, 0,
        # b1:
        o.LOAD_CONST, 0,
        # b2:
        o.WITH_CLEANUP_START, 0,
        # b3:
        o.WITH_CLEANUP_FINISH, 0,
        o.END_FINALLY, 0,
        # b4:
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="with")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3, b4 = ordered_code.order
    self.assertEqual(len(b0.code), 4)
    self.assertEqual(len(b1.code), 1)
    self.assertEqual(len(b2.code), 1)
    self.assertEqual(len(b3.code), 2)
    self.assertEqual(len(b4.code), 2)


class BlockStackTest(BaseBlocksTest):
  """Test the add_pop_block_targets function."""

  def test_finally(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | finally:
    # |   pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.SETUP_FINALLY, 4,
        o.POP_BLOCK, 0,
        o.LOAD_CONST, 0,
        o.END_FINALLY, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="finally")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    # END_FINALLY == SETUP_FINALLY.target
    self.assertEqual(bytecode[3], bytecode[0].target)
    # END_FINALLY == POP_BLOCK.block_target
    self.assertEqual(bytecode[3], bytecode[1].block_target)

  def test_except(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | except:
    # |   pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.SETUP_EXCEPT, 4,
        o.POP_BLOCK, 0,
        o.JUMP_FORWARD, 12,
        o.POP_TOP, 0,
        o.POP_TOP, 0,
        o.POP_TOP, 0,
        o.JUMP_FORWARD, 2,
        o.END_FINALLY, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="except")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    # POP_TOP == SETUP_EXCEPT.target
    self.assertEqual(bytecode[3], bytecode[0].target)
    # POP_TOP == POP_BLOCK.block_target
    self.assertEqual(bytecode[3], bytecode[1].block_target)

  def test_with(self):
    # Disassembled from:
    # | with None:
    # |   pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.LOAD_CONST, 0,
        o.SETUP_WITH, 6,
        o.POP_TOP, 0,
        o.POP_BLOCK, 0,
        o.LOAD_CONST, 0,
        o.WITH_CLEANUP_START, 0,
        o.WITH_CLEANUP_FINISH, 0,
        o.END_FINALLY, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ], name="with")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    # WITH_CLEANUP_START == SETUP_WITH.target
    self.assertEqual(bytecode[5], bytecode[1].target)
    # WITH_CLEANUP_START == POP_BLOCK.block_target
    self.assertEqual(bytecode[5], bytecode[3].block_target)

  def test_loop(self):
    # Disassembled from:
    # | while []:
    # |   break
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.SETUP_LOOP, 10,
        o.BUILD_LIST, 0,
        o.POP_JUMP_IF_FALSE, 10,
        o.BREAK_LOOP, 0,
        o.JUMP_ABSOLUTE, 2,
        o.POP_BLOCK, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    # LOAD_CONST == SETUP_LOOP.target
    self.assertEqual(bytecode[6], bytecode[0].target)
    # POP_BLOCK == POP_JUMP_IF_FALSE.target
    self.assertEqual(bytecode[5], bytecode[2].target)
    # BUILD_LIST == JUMP_ABSOLUTE.target
    self.assertEqual(bytecode[1], bytecode[4].target)
    # LOAD_CONST == POP_BLOCK.block_target
    self.assertEqual(bytecode[6], bytecode[5].block_target)

  def test_break(self):
    # Disassembled from:
    # | while True:
    # |  if []:
    # |    break
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.SETUP_LOOP, 10,
        o.BUILD_LIST, 0,
        o.POP_JUMP_IF_FALSE, 2,
        o.BREAK_LOOP, 0,
        o.JUMP_ABSOLUTE, 2,
        o.POP_BLOCK, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    # LOAD_CONST == SETUP_LOOP.target
    self.assertEqual(bytecode[6], bytecode[0].target)
    # LOAD_CONST == BREAK_LOOP.block_target
    self.assertEqual(bytecode[6], bytecode[3].block_target)
    # BUILD_LIST == POP_JUMP_IF_FALSE.target
    self.assertEqual(bytecode[1], bytecode[2].target)
    # BUILD_LIST == JUMP_ABSOLUTE.target
    self.assertEqual(bytecode[1], bytecode[4].target)

  def test_continue(self):
    # Disassembled from:
    # | while True:
    # |   try:
    # |     continue
    # |   except:
    # |     pass
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.SETUP_LOOP, 24,
        o.SETUP_EXCEPT, 6,
        o.CONTINUE_LOOP, 2,
        o.POP_BLOCK, 0,
        o.JUMP_ABSOLUTE, 2,
        o.POP_TOP, 0,
        o.POP_TOP, 0,
        o.POP_TOP, 0,
        o.POP_EXCEPT, 0,
        o.JUMP_ABSOLUTE, 2,
        o.END_FINALLY, 0,
        o.JUMP_ABSOLUTE, 2,
        o.POP_BLOCK, 0,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    # LOAD_CONST == SETUP_LOOP.target
    self.assertEqual(bytecode[13], bytecode[0].target)
    # POP_TOP == SETUP_EXCEPT.target
    self.assertEqual(bytecode[5], bytecode[1].target)
    # SETUP_EXCEPT == CONTINUE_LOOP.target
    self.assertEqual(bytecode[1], bytecode[2].target)
    # SETUP_EXCEPT == JUMP_ABSOLUTE.target
    self.assertEqual(bytecode[1], bytecode[4].target)
    # SETUP_EXCEPT == JUMP_ABSOLUTE.target
    self.assertEqual(bytecode[1], bytecode[9].target)
    # SETUP_EXCEPT == JUMP_ABSOLUTE.target
    self.assertEqual(bytecode[1], bytecode[11].target)

  def test_apply_typecomments(self):
    # Disassembly + type comment map from
    #   a = 1; b = 2  # type: float
    # The type comment should only apply to b.
    o = test_utils.Py37Opcodes
    co = self.make_code([
        o.LOAD_CONST, 1,
        o.STORE_FAST, 0,
        o.LOAD_CONST, 2,
        o.STORE_FAST, 1,
        o.LOAD_CONST, 0,
        o.RETURN_VALUE, 0,
    ])
    ordered_code = blocks.merge_annotations(
        blocks.process_code(co, self.python_version), {1: "float"})
    bytecode = ordered_code.order[0].code
    self.assertIsNone(bytecode[1].annotation)
    self.assertEqual(bytecode[3].annotation, "float")


if __name__ == "__main__":
  unittest.main()
