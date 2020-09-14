"""Tests for blocks.py."""

from pytype import blocks
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.tests import test_utils
import six

import unittest


class BaseBlocksTest(unittest.TestCase, test_utils.MakeCodeMixin):
  """A base class for implementing tests testing blocks.py."""

  python_version = (2, 7)


class OrderingTest(BaseBlocksTest):
  """Tests for order_code in blocks.py."""

  def _order_code(self, code):
    """Helper function to disassemble and then order code."""
    disassembled_code = pyc.visit(code, blocks.DisCodeVisitor())
    return blocks.order_code(disassembled_code, self.python_version)

  def test_trivial(self):
    # Disassembled from:
    # | return None
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.LOAD_CONST, 1, 0,
        o.RETURN_VALUE,
    ], name="trivial")
    ordered_code = self._order_code(co)
    b0, = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    six.assertCountEqual(self, [], b0.incoming)
    six.assertCountEqual(self, [], b0.outgoing)

  def test_has_opcode(self):
    # Disassembled from:
    # | return None
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.LOAD_CONST, 1, 0,
        o.RETURN_VALUE,
    ], name="trivial")
    ordered_code = self._order_code(co)
    self.assertTrue(ordered_code.has_opcode(opcodes.LOAD_CONST))
    self.assertTrue(ordered_code.has_opcode(opcodes.RETURN_VALUE))
    self.assertFalse(ordered_code.has_opcode(opcodes.POP_TOP))

  def test_yield(self):
    # Disassembled from:
    # | yield 1
    # | yield None
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_CONST, 1, 0,
        o.YIELD_VALUE,
        # b1:
        o.POP_TOP,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="yield")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "yield")
    b0, b1 = ordered_code.order
    six.assertCountEqual(self, b0.outgoing, [b1])
    six.assertCountEqual(self, b1.incoming, [b0])
    six.assertCountEqual(self, b0.incoming, [])
    six.assertCountEqual(self, b1.outgoing, [])

  def test_triangle(self):
    # Disassembled from:
    # | x = y
    # | if y > 1:
    # |   x -= 2
    # | return x
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_FAST, 0, 0,
        o.STORE_FAST, 1, 0,
        o.LOAD_FAST, 0, 0,
        o.LOAD_CONST, 1, 0,
        o.COMPARE_OP, 4, 0,
        o.POP_JUMP_IF_FALSE, 31, 0,  # dest=31
        # b1:
        o.LOAD_FAST, 1, 0,
        o.LOAD_CONST, 2, 0,
        o.INPLACE_SUBTRACT,
        o.STORE_FAST, 1, 0,
        o.JUMP_FORWARD, 0, 0,   # dest=31
        # b2:
        o.LOAD_FAST, 1, 0,
        o.RETURN_VALUE,
    ], name="triangle")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "triangle")
    b0, b1, b2 = ordered_code.order
    six.assertCountEqual(self, b0.incoming, [])
    six.assertCountEqual(self, b0.outgoing, [b1, b2])
    six.assertCountEqual(self, b1.incoming, [b0])
    six.assertCountEqual(self, b1.outgoing, [b2])
    six.assertCountEqual(self, b2.incoming, [b0, b1])
    six.assertCountEqual(self, b2.outgoing, [])

  def test_diamond(self):
    # Disassembled from:
    # | x = y
    # | if y > 1:
    # |   x -= 2
    # | else:
    # |   x += 2
    # | return x
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_FAST, 0, 0,
        o.STORE_FAST, 1, 0,
        o.LOAD_FAST, 0, 0,
        o.LOAD_CONST, 1, 0,
        o.COMPARE_OP, 4, 0,
        o.POP_JUMP_IF_FALSE, 31, 0,  # dest=31
        # b1:
        o.LOAD_FAST, 1, 0,
        o.LOAD_CONST, 2, 0,
        o.INPLACE_SUBTRACT,
        o.STORE_FAST, 1, 0,
        o.JUMP_FORWARD, 10, 0,  # dest=41
        # b2:
        o.LOAD_FAST, 1, 0,
        o.LOAD_CONST, 2, 0,
        o.INPLACE_ADD,
        o.STORE_FAST, 1, 0,
        # b3:
        o.LOAD_FAST, 1, 0,
        o.RETURN_VALUE,
    ], name="diamond")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "diamond")
    b0, b1, b2, b3 = ordered_code.order
    six.assertCountEqual(self, b0.incoming, [])
    six.assertCountEqual(self, b0.outgoing, [b1, b2])
    six.assertCountEqual(self, b1.incoming, [b0])
    six.assertCountEqual(self, b1.outgoing, [b3])
    six.assertCountEqual(self, b2.incoming, [b0])
    six.assertCountEqual(self, b2.outgoing, [b3])
    six.assertCountEqual(self, b3.incoming, [b1, b2])
    six.assertCountEqual(self, b3.outgoing, [])

  def test_raise(self):
    # Disassembled from:
    # | raise ValueError()
    # | return 1
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_GLOBAL, 0, 0,
        o.RAISE_VARARGS, 1, 0,
        o.LOAD_CONST, 1, 0,
        o.RETURN_VALUE,  # dead.
    ], name="raise")
    ordered_code = self._order_code(co)
    self.assertEqual(ordered_code.co_name, "raise")
    b0, = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    six.assertCountEqual(self, b0.incoming, [])
    six.assertCountEqual(self, b0.outgoing, [])

  def test_call(self):
    # Disassembled from:
    # | f()
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_GLOBAL, 0, 0,
        o.CALL_FUNCTION, 0, 0,
        # b1:
        o.POP_TOP,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="call")
    ordered_code = self._order_code(co)
    b0, b1 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertEqual(len(b1.code), 3)
    six.assertCountEqual(self, b0.outgoing, [b1])

  def test_finally(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | finally:
    # |   pass
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.SETUP_FINALLY, 4, 0,  # dest=7
        o.POP_BLOCK,
        # b1:
        o.LOAD_CONST, 0, 0,
        # b2:
        o.END_FINALLY,
        # b3:
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="finally")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertEqual(len(b1.code), 1)
    self.assertEqual(len(b2.code), 1)
    self.assertEqual(len(b3.code), 2)
    six.assertCountEqual(self, b0.outgoing, [b1, b2])

  def test_except(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | except:
    # |   pass
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.SETUP_EXCEPT, 4, 0,  # dest=7,
        o.POP_BLOCK,
        # b1:
        o.JUMP_FORWARD, 7, 0,  # dest=14,
        # b2:
        o.POP_TOP,
        o.POP_TOP,
        o.POP_TOP,
        o.JUMP_FORWARD, 1, 0,  # dest=14,
        # b3:
        o.END_FINALLY,
        # b4:
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="except")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3 = ordered_code.order
    self.assertEqual(len(b0.code), 2)
    self.assertEqual(len(b1.code), 1)
    self.assertEqual(len(b2.code), 4)
    self.assertEqual(len(b3.code), 2)
    six.assertCountEqual(self, [b1, b2], b0.outgoing)
    six.assertCountEqual(self, [b3], b1.outgoing)
    six.assertCountEqual(self, [b3], b2.outgoing)

  def test_return(self):
    # Disassembled from:
    # | return None
    # | return None
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.LOAD_CONST, 1, 0,
        o.RETURN_VALUE,  # dead.
        o.LOAD_CONST, 1, 0,  # dead.
        o.RETURN_VALUE,  # dead.
    ], name="return")
    ordered_code = self._order_code(co)
    b0, = ordered_code.order
    self.assertEqual(len(b0.code), 2)

  def test_with(self):
    # Disassembled from:
    # | with None:
    # |   pass
    o = test_utils.Py2Opcodes
    co = self.make_code([
        # b0:
        o.LOAD_CONST, 0, 0,
        o.SETUP_WITH, 5, 0,  # dest=11,
        o.POP_TOP,
        o.POP_BLOCK,
        # b1:
        o.LOAD_CONST, 0, 0,
        # b2:
        o.WITH_CLEANUP,
        # b3:
        o.END_FINALLY,
        # b4:
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="with")
    ordered_code = self._order_code(co)
    b0, b1, b2, b3, b4 = ordered_code.order
    self.assertEqual(len(b0.code), 4)
    self.assertEqual(len(b1.code), 1)
    self.assertEqual(len(b2.code), 1)
    self.assertEqual(len(b3.code), 1)
    self.assertEqual(len(b4.code), 2)


class BlockStackTest(BaseBlocksTest):
  """Test the add_pop_block_targets function."""

  def test_finally(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | finally:
    # |   pass
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.SETUP_FINALLY, 4, 0,  # dest=7 [3],
        o.POP_BLOCK,
        o.LOAD_CONST, 0, 0,
        o.END_FINALLY,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="finally")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    self.assertEqual(bytecode[3], bytecode[0].target)
    self.assertEqual(bytecode[3], bytecode[1].block_target)

  def test_except(self):
    # Disassembled from:
    # | try:
    # |   pass
    # | except:
    # |   pass
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.SETUP_EXCEPT, 4, 0,  # dest=7 [3],
        o.POP_BLOCK,
        o.JUMP_FORWARD, 7, 0,  # dest=14 [11],
        o.POP_TOP,
        o.POP_TOP,
        o.POP_TOP,
        o.JUMP_FORWARD, 1, 0,  # dest=14 [11],
        o.END_FINALLY,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="except")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    self.assertEqual(bytecode[3], bytecode[0].target)
    self.assertEqual(bytecode[3], bytecode[1].block_target)

  def test_with(self):
    # Disassembled from:
    # | with None:
    # |   pass
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.LOAD_CONST, 0, 0,
        o.SETUP_WITH, 5, 0,  # dest=11 [5],
        o.POP_TOP,
        o.POP_BLOCK,
        o.LOAD_CONST, 0, 0,
        o.WITH_CLEANUP,
        o.END_FINALLY,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ], name="with")
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    self.assertEqual(bytecode[5], bytecode[1].target)
    self.assertEqual(bytecode[5], bytecode[3].block_target)

  def test_loop(self):
    # Disassembled from:
    # | while []:
    # |   break
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.SETUP_LOOP, 10, 0,  # dest=13 [5],
        o.BUILD_LIST, 0, 0,
        o.POP_JUMP_IF_FALSE, 12, 0,  # dest=12 [4],
        o.JUMP_ABSOLUTE, 3, 0,   # dest=3 [1],
        o.POP_BLOCK,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
    self.assertEqual(bytecode[5], bytecode[0].target)
    self.assertEqual(bytecode[4], bytecode[2].target)
    self.assertEqual(bytecode[1], bytecode[3].target)
    self.assertEqual(bytecode[5], bytecode[4].block_target)

  def test_break(self):
    # Disassembled from:
    # | while True:
    # |  if []:
    # |    break
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.SETUP_LOOP, 20, 0,  # dest=23, [9],
        o.LOAD_GLOBAL, 0, 0,
        o.POP_JUMP_IF_FALSE, 22, 0,  # dest=22 [8],
        o.BUILD_LIST, 0, 0,
        o.POP_JUMP_IF_FALSE, 3, 0,   # dest=3 [1],
        o.BREAK_LOOP,
        o.JUMP_ABSOLUTE, 3, 0,   # dest=3 [1],
        o.JUMP_ABSOLUTE, 3, 0,   # dest=3 [1],
        o.POP_BLOCK,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
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
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.SETUP_LOOP, 27, 0,  # dest=30 [14],
        o.LOAD_GLOBAL, 0, 0,
        o.POP_JUMP_IF_FALSE, 29, 0,  # dest=29 [13],
        o.SETUP_EXCEPT, 7, 0,   # dest=19 [7],
        o.CONTINUE_LOOP, 3, 0,   # dest=3 [1],
        o.POP_BLOCK,
        o.JUMP_ABSOLUTE, 3, 0,   # dest=3 [1],
        o.POP_TOP,
        o.POP_TOP,
        o.POP_TOP,
        o.JUMP_ABSOLUTE, 3, 0,   # dest=3 [1],
        o.END_FINALLY,
        o.JUMP_ABSOLUTE, 3, 0,   # dest=3 [1],
        o.POP_BLOCK,
        o.LOAD_CONST, 0, 0,
        o.RETURN_VALUE,
    ])
    bytecode = opcodes.dis(co.co_code, python_version=self.python_version)
    blocks.add_pop_block_targets(bytecode, self.python_version)
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
    o = test_utils.Py2Opcodes
    co = self.make_code([
        o.LOAD_CONST, 0, 0,
        o.STORE_NAME, 0, 0,
        o.LOAD_CONST, 1, 0,
        o.STORE_NAME, 1, 0,
        o.LOAD_CONST, 2, 0,
        o.RETURN_VALUE
    ])
    ordered_code = blocks.merge_annotations(
        blocks.process_code(co, self.python_version), {1: "float"}, [])
    bytecode = ordered_code.order[0].code
    self.assertIsNone(bytecode[1].annotation)
    self.assertEqual(bytecode[3].annotation, "float")


if __name__ == "__main__":
  unittest.main()
