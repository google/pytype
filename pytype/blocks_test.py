"""Tests for blocks.py."""

from pytype import blocks
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.tests import test_base
import unittest


class BaseBlocksTest(unittest.TestCase, test_base.MakeCodeMixin):
  """A base class for implementing tests testing blocks.py."""

  def setUp(self):
    self.python_version = (2, 7)


class OrderingTest(BaseBlocksTest):
  """Tests for order_code in blocks.py."""

  def _order_code(self, code):
    """Helper function to disassemble and then order code."""
    disassembled_code = pyc.visit(code, blocks.DisCodeVisitor())
    return blocks.order_code(disassembled_code)

  def test_trivial(self):
    # Disassembled from:
    # | return None
    co = self.make_code([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=0 (None)
        0x53,  # 3 RETURN_VALUE
    ], name="trivial")
    ordered_code = self._order_code(co)
    b0, = ordered_code.order
    self.assertEqual(2, len(b0.code))
    self.assertItemsEqual([], b0.incoming)
    self.assertItemsEqual([], b0.outgoing)

  def test_has_opcode(self):
    # Disassembled from:
    # | return None
    co = self.make_code([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=0 (None)
        0x53,  # 3 RETURN_VALUE
    ], name="trivial")
    ordered_code = self._order_code(co)
    self.assertTrue(ordered_code.has_opcode(opcodes.LOAD_CONST))
    self.assertTrue(ordered_code.has_opcode(opcodes.RETURN_VALUE))
    self.assertFalse(ordered_code.has_opcode(opcodes.POP_TOP))

  def test_yield(self):
    # Disassembled from:
    # | yield 1
    # | yield None
    co = self.make_code([
        # b0:
        0x64, 1, 0,  # 0 LOAD_CONST, arg=1 (1),
        0x56,  # 3 YIELD_VALUE,
        # b1:
        0x01,  # 4 POP_TOP,
        0x64, 0, 0,  # 15 LOAD_CONST, arg=0 (None),
        0x53,  # 18 RETURN_VALUE
    ], name="yield")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "yield")
    b0, b1 = ordered_code.order
    self.assertItemsEqual(b0.outgoing, [b1])
    self.assertItemsEqual(b1.incoming, [b0])
    self.assertItemsEqual(b0.incoming, [])
    self.assertItemsEqual(b1.outgoing, [])

  def test_triangle(self):
    # Disassembled from:
    # | x = y
    # | if y > 1:
    # |   x -= 2
    # | return x
    co = self.make_code([
        # b0:
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x7d, 1, 0,  # 3 STORE_FAST, arg=1,
        0x7c, 0, 0,  # 6 LOAD_FAST, arg=0,
        0x64, 1, 0,  # 9 LOAD_CONST, arg=1 (1),
        0x6b, 4, 0,  # 12 COMPARE_OP, arg=4,
        0x72, 31, 0,  # 15 POP_JUMP_IF_FALSE, dest=31,
        # b1:
        0x7c, 1, 0,  # 18 LOAD_FAST, arg=1,
        0x64, 2, 0,  # 21 LOAD_CONST, arg=2,
        0x38,  # 24 INPLACE_SUBTRACT,
        0x7d, 1, 0,  # 25 STORE_FAST, arg=1,
        0x6e, 0, 0,  # 28 JUMP_FORWARD, dest=31,
        # b2:
        0x7c, 1, 0,  # 31 LOAD_FAST, arg=1,
        0x53,  # 34 RETURN_VALUE
    ], name="triangle")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "triangle")
    b0, b1, b2 = ordered_code.order
    self.assertItemsEqual(b0.incoming, [])
    self.assertItemsEqual(b0.outgoing, [b1, b2])
    self.assertItemsEqual(b1.incoming, [b0])
    self.assertItemsEqual(b1.outgoing, [b2])
    self.assertItemsEqual(b2.incoming, [b0, b1])
    self.assertItemsEqual(b2.outgoing, [])

  def test_diamond(self):
    # Disassembled from:
    # | x = y
    # | if y > 1:
    # |   x -= 2
    # | else:
    # |   x += 2
    # | return x
    co = self.make_code([
        # b0:
        0x7c, 0, 0,  # 0 LOAD_FAST, arg=0,
        0x7d, 1, 0,  # 3 STORE_FAST, arg=1,
        0x7c, 0, 0,  # 6 LOAD_FAST, arg=0,
        0x64, 1, 0,  # 9 LOAD_CONST, arg=1,
        0x6b, 4, 0,  # 12 COMPARE_OP, arg=4,
        0x72, 31, 0,  # 15 POP_JUMP_IF_FALSE, dest=31,
        # b1:
        0x7c, 1, 0,  # 18 LOAD_FAST, arg=1,
        0x64, 2, 0,  # 21 LOAD_CONST, arg=2,
        0x38,  # 24 INPLACE_SUBTRACT,
        0x7d, 1, 0,  # 25 STORE_FAST, arg=1,
        0x6e, 10, 0,  # 28 JUMP_FORWARD, dest=41,
        # b2:
        0x7c, 1, 0,  # 31 LOAD_FAST, arg=1,
        0x64, 2, 0,  # 34 LOAD_CONST, arg=2,
        0x37,  # 37 INPLACE_ADD,
        0x7d, 1, 0,  # 38 STORE_FAST, arg=1,
        # b3:
        0x7c, 1, 0,  # 41 LOAD_FAST, arg=1,
        0x53,  # 44 RETURN_VALUE
    ], name="diamond")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "diamond")
    b0, b1, b2, b3 = ordered_code.order
    self.assertItemsEqual(b0.incoming, [])
    self.assertItemsEqual(b0.outgoing, [b1, b2])
    self.assertItemsEqual(b1.incoming, [b0])
    self.assertItemsEqual(b1.outgoing, [b3])
    self.assertItemsEqual(b2.incoming, [b0])
    self.assertItemsEqual(b2.outgoing, [b3])
    self.assertItemsEqual(b3.incoming, [b1, b2])
    self.assertItemsEqual(b3.outgoing, [])

  def test_raise(self):
    # Disassembled from:
    # | raise ValueError()
    # | return 1
    co = self.make_code([
        # b0:
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x82, 1, 0,  # 6 RAISE_VARARGS, arg=1,
        0x64, 1, 0,  # 9 LOAD_CONST, arg=1, dead.
        0x53,  # 12 RETURN_VALUE, dead.
    ], name="raise")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "raise")
    b0, = ordered_code.order
    self.assertEqual(2, len(b0.code))
    self.assertItemsEqual(b0.incoming, [])
    self.assertItemsEqual(b0.outgoing, [])

  def test_call(self):
    # Disassembled from:
    # | f()
    co = self.make_code([
        # b0:
        0x74, 0, 0,  # 0 LOAD_GLOBAL, arg=0,
        0x83, 0, 0,  # 3 CALL_FUNCTION, arg=0,
        # b1:
        0x01,  # 6 POP_TOP,
        0x64, 0, 0,  # 7 LOAD_CONST, arg=0,
        0x53,  # 10 RETURN_VALUE
    ], name="call")
    ordered_code = self._order_code(co)
    b0, b1 = ordered_code.order
    self.assertEqual(2, len(b0.code))
    self.assertEqual(3, len(b1.code))
    self.assertItemsEqual(b0.outgoing, [b1])

  def test_finally(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | finally:
    # |   pass
    co = self.make_code([
        # b0:
        0x7a, 4, 0,  # 0 SETUP_FINALLY, dest=7,
        0x57,  # 3 POP_BLOCK,
        # b1:
        0x64, 0, 0,  # 4 LOAD_CONST, arg=0 (None),
        # b2:
        0x58,  # 7 END_FINALLY,
        # b3:
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0 (None),
        0x53,  # 11 RETURN_VALUE
    ], name="finally")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3 = ordered_code.order
    self.assertEqual(2, len(b0.code))
    self.assertEqual(1, len(b1.code))
    self.assertEqual(1, len(b2.code))
    self.assertEqual(2, len(b3.code))
    self.assertItemsEqual(b0.outgoing, [b1, b2])

  def test_except(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | except:
    # |   pass
    co = self.make_code([
        # b0:
        0x79, 4, 0,  # 0 SETUP_EXCEPT, dest=7,
        0x57,        # 3 POP_BLOCK,
        # b1:
        0x6e, 7, 0,  # 4 JUMP_FORWARD, dest=14,
        # b2:
        0x01,        # 7 POP_TOP,
        0x01,        # 8 POP_TOP,
        0x01,        # 9 POP_TOP,
        0x6e, 1, 0,  # 10 JUMP_FORWARD, dest=14,
        # b3:
        0x58,        # 13 END_FINALLY,
        # b4:
        0x64, 0, 0,  # 14 LOAD_CONST, arg=0,
        0x53,        # 17 RETURN_VALUE
    ], name="except")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3 = ordered_code.order
    self.assertEqual(2, len(b0.code))
    self.assertEqual(1, len(b1.code))
    self.assertEqual(4, len(b2.code))
    self.assertEqual(2, len(b3.code))
    self.assertItemsEqual([b1, b2], b0.outgoing)
    self.assertItemsEqual([b3], b1.outgoing)
    self.assertItemsEqual([b3], b2.outgoing)

  def test_return(self):
    # Disassembled from:
    # | return None
    # | return None
    co = self.make_code([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=0 (None)
        0x53,  # 3 RETURN_VALUE, dead.
        0x64, 1, 0,  # 4 LOAD_CONST, arg=0 (None), dead.
        0x53,  # 7 RETURN_VALUE, dead.
    ], name="return")
    ordered_code = self._order_code(co)
    b0, = ordered_code.order
    self.assertEqual(2, len(b0.code))

  def test_with(self):
    # Disassembled from:
    # | with None:
    # |   pass
    co = self.make_code([
        # b0:
        0x64, 0, 0,  # 0 LOAD_CONST, arg=0,
        0x8f, 5, 0,  # 3 SETUP_WITH, dest=11,
        0x01,        # 6 POP_TOP,
        0x57,        # 7 POP_BLOCK,
        # b1:
        0x64, 0, 0,  # 8 LOAD_CONST, arg=0,
        # b2:
        0x51,        # 11 WITH_CLEANUP,
        # b3:
        0x58,        # 12 END_FINALLY,
        # b4:
        0x64, 0, 0,  # 13 LOAD_CONST, arg=0,
        0x53,        # 16 RETURN_VALUE
    ], name="with")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3, b4 = ordered_code.order
    self.assertEqual(4, len(b0.code))
    self.assertEqual(1, len(b1.code))
    self.assertEqual(1, len(b2.code))
    self.assertEqual(1, len(b3.code))
    self.assertEqual(2, len(b4.code))


class BlockStackTest(BaseBlocksTest):
  """Test the add_pop_block_targets function."""

  def test_finally(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | finally:
    # |   pass
    co = self.make_code([
        0x7a, 4, 0,  # [0] 0 SETUP_FINALLY, dest=7 [3],
        0x57,        # [1] 3 POP_BLOCK,
        0x64, 0, 0,  # [2] 4 LOAD_CONST, arg=0 (None),
        0x58,        # [3] 7 END_FINALLY,
        0x64, 0, 0,  # [4] 8 LOAD_CONST, arg=0 (None),
        0x53,        # [5] 11 RETURN_VALUE
    ], name="finally")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode)
    self.assertEqual(bytecode[3], bytecode[0].target)
    self.assertEqual(bytecode[3], bytecode[1].block_target)

  def test_except(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | except:
    # |   pass
    co = self.make_code([
        0x79, 4, 0,  # [ 0] 0 SETUP_EXCEPT, dest=7 [3],
        0x57,        # [ 1] 3 POP_BLOCK,
        0x6e, 7, 0,  # [ 2] 4 JUMP_FORWARD, dest=14 [11],
        0x01,        # [ 3] 7 POP_TOP,
        0x01,        # [ 4] 8 POP_TOP,
        0x01,        # [ 8] 9 POP_TOP,
        0x6e, 1, 0,  # [ 9] 10 JUMP_FORWARD, dest=14 [11],
        0x58,        # [10] 13 END_FINALLY,
        0x64, 0, 0,  # [11] 14 LOAD_CONST, arg=0,
        0x53,        # [12] 17 RETURN_VALUE
    ], name="except")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode)
    self.assertEqual(bytecode[3], bytecode[0].target)
    self.assertEqual(bytecode[3], bytecode[1].block_target)

  def test_with(self):
    # Disassembled from:
    # | with None:
    # |   pass
    co = self.make_code([
        0x64, 0, 0,  # [0] 0 LOAD_CONST, arg=0,
        0x8f, 5, 0,  # [1] 3 SETUP_WITH, dest=11 [5],
        0x01,        # [2] 6 POP_TOP,
        0x57,        # [3] 7 POP_BLOCK,
        0x64, 0, 0,  # [4] 8 LOAD_CONST, arg=0,
        0x51,        # [5] 11 WITH_CLEANUP,
        0x58,        # [6] 12 END_FINALLY,
        0x64, 0, 0,  # [7] 13 LOAD_CONST, arg=0,
        0x53,        # [8] 16 RETURN_VALUE
    ], name="with")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode)
    self.assertEqual(bytecode[5], bytecode[1].target)
    self.assertEqual(bytecode[5], bytecode[3].block_target)

  def test_loop(self):
    # Disassembled from:
    # | while []:
    # |   break
    co = self.make_code([
        0x78, 10, 0,  # [0] 0 SETUP_LOOP, dest=13 [5],
        0x67, 0, 0,   # [1] 3 BUILD_LIST, arg=0,
        0x72, 12, 0,  # [2] 6 POP_JUMP_IF_FALSE, dest=12 [4],
        0x71, 3, 0,   # [3] 9 JUMP_ABSOLUTE, dest=3 [1],
        0x57,         # [4] 12 POP_BLOCK,
        0x64, 0, 0,   # [5] 13 LOAD_CONST, arg=0,
        0x53,         # [6] 16 RETURN_VALUE
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode)
    self.assertEqual(bytecode[5], bytecode[0].target)
    self.assertEqual(bytecode[4], bytecode[2].target)
    self.assertEqual(bytecode[1], bytecode[3].target)
    self.assertEqual(bytecode[5], bytecode[4].block_target)

  def test_break(self):
    # Disassembled from:
    # | while True:
    # |  if []:
    # |    break
    co = self.make_code([
        0x78, 20, 0,  # [0] 0 SETUP_LOOP, dest=23, [9],
        0x74, 0, 0,   # [1] 3 LOAD_GLOBAL, arg=0,
        0x72, 22, 0,  # [2] 6 POP_JUMP_IF_FALSE, dest=22 [8],
        0x67, 0, 0,   # [3] 9 BUILD_LIST, arg=0,
        0x72, 3, 0,   # [4] 12 POP_JUMP_IF_FALSE, dest=3 [1],
        0x50,         # [5] 15 BREAK_LOOP,
        0x71, 3, 0,   # [6] 16 JUMP_ABSOLUTE, dest=3 [1],
        0x71, 3, 0,   # [7] 19 JUMP_ABSOLUTE, dest=3 [1],
        0x57,         # [8] 22 POP_BLOCK,
        0x64, 0, 0,   # [9] 23 LOAD_CONST, arg=0,
        0x53,         # [10] 26 RETURN_VALUE
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode)
    self.assertEqual(bytecode[9], bytecode[0].target)
    self.assertEqual(bytecode[9], bytecode[5].block_target)
    self.assertEqual(bytecode[1], bytecode[6].target)
    self.assertEqual(bytecode[1], bytecode[7].target)

  def test_continue(self):
    # Disassembled from:
    # | while True:
    # |   try:
    # |     continue
    # |   except:
    # |     pass
    co = self.make_code([
        0x78, 27, 0,  # [0] 0 SETUP_LOOP, dest=30 [14],
        0x74, 0, 0,   # [1] 3 LOAD_GLOBAL, arg=0,
        0x72, 29, 0,  # [2] 6 POP_JUMP_IF_FALSE, dest=29 [13],
        0x79, 7, 0,   # [3] 9 SETUP_EXCEPT, dest=19 [7],
        0x77, 3, 0,   # [4] 12 CONTINUE_LOOP, dest=3 [1],
        0x57,         # [5] 15 POP_BLOCK,
        0x71, 3, 0,   # [6] 16 JUMP_ABSOLUTE, dest=3 [1],
        0x01,         # [7] 19 POP_TOP,
        0x01,         # [8] 20 POP_TOP,
        0x01,         # [9] 21 POP_TOP,
        0x71, 3, 0,   # [10] 22 JUMP_ABSOLUTE, dest=3 [1],
        0x58,         # [11] 25 END_FINALLY,
        0x71, 3, 0,   # [12] 26 JUMP_ABSOLUTE, dest=3 [1],
        0x57,         # [13] 29 POP_BLOCK,
        0x64, 0, 0,   # [14] 30 LOAD_CONST, arg=0,
        0x53,         # [15] 33 RETURN_VALUE
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode)
    self.assertEqual(bytecode[14], bytecode[0].target)
    self.assertEqual(bytecode[13], bytecode[2].target)
    self.assertEqual(bytecode[7], bytecode[3].target)
    self.assertEqual(bytecode[1], bytecode[4].target)
    self.assertEqual(bytecode[1], bytecode[6].target)
    self.assertEqual(bytecode[1], bytecode[10].target)
    self.assertEqual(bytecode[1], bytecode[12].target)

  def test_apply_typecomments(self):
    # Disassembly + type comment map from
    #   a = 1; b = 2  # type: float
    # The type comment should only apply to b.
    co = self.make_code([
        0x64, 0, 0,     # [0]  0 LOAD_CONST, arg=0 (1)
        0x5a, 0, 0,     # [1]  3 STORE_NAME, arg=0 (a)
        0x64, 1, 0,     # [2]  6 LOAD_CONST, arg=1 (2)
        0x5a, 1, 0,     # [3]  9 STORE_NAME, arg=1 (b)
        0x64, 2, 0,     # [4] 12 LOAD_CONST, arg=2 (None)
        0x53            # [5] 15 RETURN_VALUE
    ])
    ordered_code = blocks.process_code(co, {1: ("a = 1; b = 2", "float")})
    bytecode = ordered_code.order[0].code
    self.assertEqual(bytecode[1].type_comment, None)
    self.assertEqual(bytecode[3].type_comment, "float")


if __name__ == "__main__":
  unittest.main()
