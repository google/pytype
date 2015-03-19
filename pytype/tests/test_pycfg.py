"""Tests for pycfg.
"""

import dis
import inspect
import unittest


from pytype import pycfg
from pytype.tests import test_inference

# Disable because pylint does not like any name for the nested test_code
# functions used to get the needed bytecode.
# pylint: disable=invalid-name

# The bytecode constants used to check against the generated code are formatted
# as follows. Each line is one instruction. Blank lines separate basic blocks.
#
# dis.opmap["<opcode name>"], <arg low>, <arg high>,  # <offset of inst>, <arg>
#
# The <arg> is a decoded version of the argument. This is more useful for
# relative jumps.


def line_number():
  """Returns the line number of the call site."""
  return inspect.currentframe().f_back.f_lineno


class CFGTest(unittest.TestCase):

  def assertEndsWith(self, actual, expected):
    self.assertTrue(actual.endswith(expected),
                    msg="'%s' does not end with '%s'" % (actual, expected))

  # Copy this line into your test when developing it. It prints the formatted
  # bytecode to use as the expected.
  # print pycfg._bytecode_repr(test_code.func_code.co_code)

  def checkBlocks(self, table, expected):
    self.assertEqual(len(table._blocks), len(expected))
    for block, (expected_begin, expected_end) in zip(table._blocks, expected):
      self.assertEqual(block.begin, expected_begin)
      self.assertEqual(block.end, expected_end)

  @staticmethod
  def codeOneBlock():
    return x + 1  # pylint: disable=undefined-variable

  codeOneBlockBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_GLOBAL"], 0, 0,  # 0
      dis.opmap["LOAD_CONST"], 1, 0,   # 3
      dis.opmap["BINARY_ADD"],         # 6
      dis.opmap["RETURN_VALUE"],       # 7
  ])

  def testOneBlock(self):
    # Check the code to make sure the test will fail if the compilation changes.
    self.assertEqual(self.codeOneBlock.func_code.co_code,
                     self.codeOneBlockBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeOneBlock.func_code)
    # Should all be one basic block.
    self.assertIs(table.get_basic_block(0), table.get_basic_block(3))
    self.assertIs(table.get_basic_block(0), table.get_basic_block(6))
    self.assertIs(table.get_basic_block(0), table.get_basic_block(7))
    # No incoming
    self.assertItemsEqual(table.get_basic_block(0).incoming, [])
    # Outgoing is an unknown return location
    self.assertItemsEqual(table.get_basic_block(0).outgoing,
                          [pycfg.UNKNOWN_TARGET])

  @staticmethod
  def codeTriangle(y):
    x = y
    if y > 10:
      x -= 2
    return x
  codeTriangleLineNumber = line_number() - 4
  # codeTriangleLineNumber is used to compute the correct line numbers for code
  # in codeTriangle. This makes the tests less brittle if other tests in the
  # file are changed. However the "- 4" will need to be changed if codeTriangle
  # is changed or anything is inserted between the line_number() call and the
  # definition of codeTriangle.

  codeTriangleBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_FAST"], 0, 0,           # 0, arg=0
      dis.opmap["STORE_FAST"], 1, 0,          # 3, arg=1
      dis.opmap["LOAD_FAST"], 0, 0,           # 6, arg=0
      dis.opmap["LOAD_CONST"], 1, 0,          # 9, arg=1
      dis.opmap["COMPARE_OP"], 4, 0,          # 12, arg=4
      dis.opmap["POP_JUMP_IF_FALSE"], 31, 0,  # 15, dest=31

      dis.opmap["LOAD_FAST"], 1, 0,           # 18, arg=1
      dis.opmap["LOAD_CONST"], 2, 0,          # 21, arg=2
      dis.opmap["INPLACE_SUBTRACT"],          # 24
      dis.opmap["STORE_FAST"], 1, 0,          # 25, arg=1
      dis.opmap["JUMP_FORWARD"], 0, 0,        # 28, dest=31

      dis.opmap["LOAD_FAST"], 1, 0,           # 31, arg=1
      dis.opmap["RETURN_VALUE"],              # 34
  ])

  def testTriangle(self):
    self.assertEqual(self.codeTriangle.func_code.co_code,
                     self.codeTriangleBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeTriangle.func_code)
    expected = [(0, 15),
                (18, 28),
                (31, 34)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    # Check the POP_JUMP_IF_FALSE conditional jump
    self.assertItemsEqual(bb(0).outgoing, [bb(18), bb(31)])
    # Check the return
    self.assertItemsEqual(bb(44).outgoing, [pycfg.UNKNOWN_TARGET])
    # Check the incoming of the entry block
    self.assertItemsEqual(bb(0).incoming, [])
    # Check incoming of the merge block.
    self.assertItemsEqual(bb(44).incoming, [bb(28), bb(15)])
    self.assertEndsWith(
        bb(21).get_name(),
        "tests/test_pycfg.py:{0}-{0}".format(self.codeTriangleLineNumber + 2))

  def testTriangleOrder(self):
    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeTriangle.func_code)

    bb = table.get_basic_block
    self.assertEqual(table.get_ancestors_first_traversal(),
                     [bb(o) for o in [0, 18, 31]])

  @staticmethod
  def codeDiamond(y):
    x = y
    if y > 10:
      x -= 2
    else:
      x += 2
    return x

  codeDiamondBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_FAST"], 0, 0,             # 0, arg=0
      dis.opmap["STORE_FAST"], 1, 0,            # 3, arg=1
      dis.opmap["LOAD_FAST"], 0, 0,             # 6, arg=0
      dis.opmap["LOAD_CONST"], 1, 0,            # 9, arg=1
      dis.opmap["COMPARE_OP"], 4, 0,            # 12, arg=4
      dis.opmap["POP_JUMP_IF_FALSE"], 31, 0,    # 15, dest=31

      dis.opmap["LOAD_FAST"], 1, 0,             # 18, arg=1
      dis.opmap["LOAD_CONST"], 2, 0,            # 21, arg=2
      dis.opmap["INPLACE_SUBTRACT"],            # 24
      dis.opmap["STORE_FAST"], 1, 0,            # 25, arg=1
      dis.opmap["JUMP_FORWARD"], 10, 0,         # 28, dest=41

      dis.opmap["LOAD_FAST"], 1, 0,             # 31, arg=1
      dis.opmap["LOAD_CONST"], 2, 0,            # 34, arg=2
      dis.opmap["INPLACE_ADD"],                 # 37
      dis.opmap["STORE_FAST"], 1, 0,            # 38, arg=1

      dis.opmap["LOAD_FAST"], 1, 0,             # 41, arg=1
      dis.opmap["RETURN_VALUE"],                # 44
  ])

  def testDiamond(self):
    self.assertEqual(self.codeDiamond.func_code.co_code,
                     self.codeDiamondBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeDiamond.func_code)
    expected = [(0, 15),
                (18, 28),
                (31, 38),
                (41, 44)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    # Check the POP_JUMP_IF_FALSE conditional jump
    self.assertItemsEqual(bb(0).outgoing, [bb(18), bb(31)])
    # Check the jumps at the end of the 2 of branches
    self.assertItemsEqual(bb(18).outgoing, [bb(41)])
    self.assertItemsEqual(bb(38).outgoing, [bb(41)])
    # Check the return
    self.assertItemsEqual(bb(44).outgoing, [pycfg.UNKNOWN_TARGET])
    # Check the incoming of the entry block
    self.assertItemsEqual(bb(0).incoming, [])
    # Check the incoming of the 2 if branches
    self.assertItemsEqual(bb(18).incoming, [bb(15)])
    self.assertItemsEqual(bb(31).incoming, [bb(15)])
    # Check incoming of the merge block.
    self.assertItemsEqual(bb(44).incoming, [bb(28), bb(38)])

  def testDiamondOrder(self):
    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeDiamond.func_code)

    self.assertIn([b.begin for b in table.get_ancestors_first_traversal()],
                  [[0, 18, 31, 41],
                   [0, 31, 18, 41]])

  @staticmethod
  def codeLoop(y):
    z = 0
    for x in y:
      z += x
    return z

  codeLoopBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_CONST"], 1, 0,   # 0, arg=1
      dis.opmap["STORE_FAST"], 1, 0,   # 3, arg=1
      dis.opmap["SETUP_LOOP"], 24, 0,  # 6, dest=33
      dis.opmap["LOAD_FAST"], 0, 0,    # 9, arg=0
      dis.opmap["GET_ITER"],           # 12

      dis.opmap["FOR_ITER"], 16, 0,    # 13, dest=32

      dis.opmap["STORE_FAST"], 2, 0,   # 16, arg=2
      dis.opmap["LOAD_FAST"], 1, 0,    # 19, arg=1
      dis.opmap["LOAD_FAST"], 2, 0,    # 22, arg=2
      dis.opmap["INPLACE_ADD"],        # 25
      dis.opmap["STORE_FAST"], 1, 0,   # 26, arg=1
      dis.opmap["JUMP_ABSOLUTE"], 13, 0,  # 29, dest=13

      dis.opmap["POP_BLOCK"],          # 32

      dis.opmap["LOAD_FAST"], 1, 0,    # 33, arg=1
      dis.opmap["RETURN_VALUE"],       # 36
  ])

  def testLoop(self):
    self.assertEqual(self.codeLoop.func_code.co_code,
                     self.codeLoopBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeLoop.func_code)
    expected = [(0, 12),
                (13, 13),
                (16, 29),
                (32, 32),
                (33, 36)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    # Check outgoing of the loop handler instruction.
    self.assertItemsEqual(bb(13).outgoing, [bb(16), bb(32)])
    self.assertItemsEqual(bb(0).outgoing, [bb(13)])

  def testLoopOrder(self):
    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeLoop.func_code)

    bb = table.get_basic_block
    self.assertEqual(table.get_ancestors_first_traversal(),
                     [bb(o) for o in [0, 13, 16, 32, 33]])

  @staticmethod
  def codeNestedLoops(y):
    z = 0
    for x in y:
      for x in y:
        z += x * x
    return z
  codeNestedLoopsLineNumber = line_number() - 5
  # See comment on codeTriangleLineNumber above.

  codeNestedLoopsBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_CONST"], 1, 0,       # 0, arg=1
      dis.opmap["STORE_FAST"], 1, 0,       # 3, arg=1
      dis.opmap["SETUP_LOOP"], 45, 0,      # 6, dest=54
      dis.opmap["LOAD_FAST"], 0, 0,        # 9, arg=0
      dis.opmap["GET_ITER"],               # 12

      dis.opmap["FOR_ITER"], 37, 0,        # 13, dest=53

      dis.opmap["STORE_FAST"], 2, 0,       # 16, arg=2
      dis.opmap["SETUP_LOOP"], 28, 0,      # 19, dest=50
      dis.opmap["LOAD_FAST"], 0, 0,        # 22, arg=0
      dis.opmap["GET_ITER"],               # 25

      dis.opmap["FOR_ITER"], 20, 0,        # 26, dest=49

      dis.opmap["STORE_FAST"], 2, 0,       # 29, arg=2
      dis.opmap["LOAD_FAST"], 1, 0,        # 32, arg=1
      dis.opmap["LOAD_FAST"], 2, 0,        # 35, arg=2
      dis.opmap["LOAD_FAST"], 2, 0,        # 38, arg=2
      dis.opmap["BINARY_MULTIPLY"],        # 41
      dis.opmap["INPLACE_ADD"],            # 42
      dis.opmap["STORE_FAST"], 1, 0,       # 43, arg=1
      dis.opmap["JUMP_ABSOLUTE"], 26, 0,   # 46, dest=26

      dis.opmap["POP_BLOCK"],              # 49

      dis.opmap["JUMP_ABSOLUTE"], 13, 0,   # 50, dest=13

      dis.opmap["POP_BLOCK"],              # 53

      dis.opmap["LOAD_FAST"], 1, 0,        # 54, arg=1
      dis.opmap["RETURN_VALUE"],           # 57
  ])

  def testNestedLoops(self):
    self.assertEqual(self.codeNestedLoops.func_code.co_code,
                     self.codeNestedLoopsBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeNestedLoops.func_code)
    expected = [(0, 12),
                (13, 13),
                (16, 25),
                (26, 26),
                (29, 46),
                (49, 49),
                (50, 50),
                (53, 53),
                (54, 57)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    self.assertItemsEqual(bb(13).incoming, [bb(12), bb(50)])
    self.assertItemsEqual(bb(13).outgoing, [bb(16), bb(53)])
    self.assertItemsEqual(bb(26).incoming, [bb(25), bb(46)])
    self.assertItemsEqual(bb(26).outgoing, [bb(29), bb(49)])
    self.assertEndsWith(
        bb(43).get_name(),
        "tests/test_pycfg.py:{}-{}".format(self.codeNestedLoopsLineNumber + 2,
                                           self.codeNestedLoopsLineNumber + 3))

  def testNestedLoopsOrder(self):
    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeNestedLoops.func_code)

    # There are multiple options for the traversal, all of which are correct.
    self.assertIn([b.begin for b in table.get_ancestors_first_traversal()],
                  [[0, 13, 16, 26, 29, 49, 50, 53, 54],
                   [0, 13, 16, 26, 49, 29, 50, 53, 54],
                   [0, 13, 16, 26, 49, 50, 29, 53, 54]])

  @staticmethod
  def codeContinue(y):
    z = 0
    for x in y:
      if x == 1:
        continue
      z += x * x
    return z

  codeContinueBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_CONST"], 1, 0,          # 0, arg=1
      dis.opmap["STORE_FAST"], 1, 0,          # 3, arg=1
      dis.opmap["SETUP_LOOP"], 46, 0,         # 6, dest=55
      dis.opmap["LOAD_FAST"], 0, 0,           # 9, arg=0
      dis.opmap["GET_ITER"],                  # 12

      dis.opmap["FOR_ITER"], 38, 0,           # 13, dest=54

      dis.opmap["STORE_FAST"], 2, 0,          # 16, arg=2
      dis.opmap["LOAD_FAST"], 2, 0,           # 19, arg=2
      dis.opmap["LOAD_CONST"], 2, 0,          # 22, arg=2
      dis.opmap["COMPARE_OP"], 2, 0,          # 25, arg=2
      dis.opmap["POP_JUMP_IF_FALSE"], 37, 0,  # 28, dest=37

      dis.opmap["JUMP_ABSOLUTE"], 13, 0,      # 31, dest=13

      dis.opmap["JUMP_FORWARD"], 0, 0,        # 34, dest=37

      dis.opmap["LOAD_FAST"], 1, 0,           # 37, arg=1
      dis.opmap["LOAD_FAST"], 2, 0,           # 40, arg=2
      dis.opmap["LOAD_FAST"], 2, 0,           # 43, arg=2
      dis.opmap["BINARY_MULTIPLY"],           # 46
      dis.opmap["INPLACE_ADD"],               # 47
      dis.opmap["STORE_FAST"], 1, 0,          # 48, arg=1
      dis.opmap["JUMP_ABSOLUTE"], 13, 0,      # 51, dest=13

      dis.opmap["POP_BLOCK"],                 # 54
      dis.opmap["LOAD_FAST"], 1, 0,           # 55, arg=1
      dis.opmap["RETURN_VALUE"],              # 58
  ])

  def testContinue(self):
    self.assertEqual(self.codeContinue.func_code.co_code,
                     self.codeContinueBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeContinue.func_code)
    bb = table.get_basic_block
    self.assertItemsEqual(bb(31).outgoing, [bb(13)])
    self.assertItemsEqual(bb(13).incoming, [bb(12), bb(51), bb(31)])
    self.assertItemsEqual(bb(13).outgoing, [bb(16), bb(54)])

  @staticmethod
  def codeBreak(y):
    z = 0
    for x in y:
      if x == 1:
        break
      z += x * x
    return z

  codeBreakBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_CONST"], 1, 0,           # 0, arg=1
      dis.opmap["STORE_FAST"], 1, 0,           # 3, arg=1
      dis.opmap["SETUP_LOOP"], 44, 0,          # 6, dest=53
      dis.opmap["LOAD_FAST"], 0, 0,            # 9, arg=0
      dis.opmap["GET_ITER"],                   # 12

      dis.opmap["FOR_ITER"], 36, 0,            # 13, dest=52

      dis.opmap["STORE_FAST"], 2, 0,           # 16, arg=2
      dis.opmap["LOAD_FAST"], 2, 0,            # 19, arg=2
      dis.opmap["LOAD_CONST"], 2, 0,           # 22, arg=2
      dis.opmap["COMPARE_OP"], 2, 0,           # 25, arg=2
      dis.opmap["POP_JUMP_IF_FALSE"], 35, 0,   # 28, dest=35

      dis.opmap["BREAK_LOOP"],                 # 31

      dis.opmap["JUMP_FORWARD"], 0, 0,         # 32, dest=35

      dis.opmap["LOAD_FAST"], 1, 0,            # 35, arg=1
      dis.opmap["LOAD_FAST"], 2, 0,            # 38, arg=2
      dis.opmap["LOAD_FAST"], 2, 0,            # 41, arg=2
      dis.opmap["BINARY_MULTIPLY"],            # 44
      dis.opmap["INPLACE_ADD"],                # 45
      dis.opmap["STORE_FAST"], 1, 0,           # 46, arg=1
      dis.opmap["JUMP_ABSOLUTE"], 13, 0,       # 49, dest=13

      dis.opmap["POP_BLOCK"],                  # 52

      dis.opmap["LOAD_FAST"], 1, 0,            # 53, arg=1
      dis.opmap["RETURN_VALUE"],               # 56
  ])

  def testBreak(self):
    self.assertEqual(self.codeBreak.func_code.co_code,
                     self.codeBreakBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeBreak.func_code)
    bb = table.get_basic_block
    self.assertItemsEqual(bb(13).incoming, [bb(12), bb(49)])
    self.assertItemsEqual(bb(31).incoming, [bb(28)])
    self.assertItemsEqual(bb(31).outgoing, [pycfg.UNKNOWN_TARGET])
    # TODO(ampere): This is correct, however more information would make the
    #               following succeed.
    # self.assertItemsEqual(bb(31).incoming, [53])

  @staticmethod
  def codeYield():
    yield 1
    yield 2
    yield 3

  codeYieldBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_CONST"], 1, 0,  # 0, arg=1
      dis.opmap["YIELD_VALUE"],       # 3

      dis.opmap["POP_TOP"],           # 4
      dis.opmap["LOAD_CONST"], 2, 0,  # 5, arg=2
      dis.opmap["YIELD_VALUE"],       # 8

      dis.opmap["POP_TOP"],           # 9
      dis.opmap["LOAD_CONST"], 3, 0,  # 10, arg=3
      dis.opmap["YIELD_VALUE"],       # 13

      dis.opmap["POP_TOP"],           # 14
      dis.opmap["LOAD_CONST"], 0, 0,  # 15, arg=0
      dis.opmap["RETURN_VALUE"],      # 18
  ])

  def testYield(self):
    self.assertEqual(self.codeYield.func_code.co_code,
                     self.codeYieldBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeYield.func_code)
    expected = [(0, 3),
                (4, 8),
                (9, 13),
                (14, 18)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    # We both branch to unknown and to the best instruction for each yield.
    self.assertItemsEqual(bb(0).outgoing, [pycfg.UNKNOWN_TARGET, bb(4)])
    self.assertItemsEqual(bb(4).outgoing, [pycfg.UNKNOWN_TARGET, bb(9)])
    self.assertItemsEqual(bb(9).incoming, [bb(8)])
    self.assertItemsEqual(bb(9).outgoing, [pycfg.UNKNOWN_TARGET, bb(14)])

  @staticmethod
  def codeRaise():
    raise ValueError()
    return 0  # pylint: disable=unreachable

  codeRaiseBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_GLOBAL"], 0, 0,    # 0, arg=0
      dis.opmap["CALL_FUNCTION"], 0, 0,  # 3, arg=0

      dis.opmap["RAISE_VARARGS"], 1, 0,  # 6, arg=1

      dis.opmap["LOAD_CONST"], 1, 0,     # 9, arg=1
      dis.opmap["RETURN_VALUE"],         # 12
  ])

  def testRaise(self):
    self.assertEqual(self.codeRaise.func_code.co_code,
                     self.codeRaiseBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeRaise.func_code)
    expected = [(0, 3),
                (6, 6),
                (9, 12)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    # CALL_FUNCTION always performs the call
    self.assertItemsEqual(bb(0).outgoing, [pycfg.UNKNOWN_TARGET, bb(6)])
    # RAISE_VARARGS always raises
    self.assertItemsEqual(bb(6).outgoing, [pycfg.UNKNOWN_TARGET])
    # This basic block is unreachable
    self.assertItemsEqual(bb(9).incoming, [])
    # We return to an unknown location
    self.assertItemsEqual(bb(9).outgoing, [pycfg.UNKNOWN_TARGET])

  def testRaiseOrder(self):
    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeRaise.func_code)

    bb = table.get_basic_block
    self.assertEqual(table.get_ancestors_first_traversal(),
                     [bb(o) for o in [0, 6]])  # 9 is dead code

  @staticmethod
  def codeFinally():
    try:
      pass
    finally:
      return  # pylint: disable=lost-exception

  codeFinallyBytecode = pycfg._list_to_string([
      dis.opmap["SETUP_FINALLY"], 4, 0,  #  0 (to 7)
      dis.opmap["POP_BLOCK"],            #  3
      dis.opmap["LOAD_CONST"], 0, 0,     #  4 (None)
      dis.opmap["LOAD_CONST"], 0, 0,     #  7 (None)
      dis.opmap["RETURN_VALUE"],         # 10
      dis.opmap["END_FINALLY"],          # 11
  ])

  def testFinally(self):
    self.assertEqual(self.codeFinally.func_code.co_code,
                     self.codeFinallyBytecode)

    cfg = pycfg.CFG()
    table = cfg.get_block_table(self.codeFinally.func_code)
    print table._blocks
    expected = [(0, 0),
                (3, 4),
                (7, 10),
                (11, 11)]
    self.checkBlocks(table, expected)
    bb = table.get_basic_block
    self.assertItemsEqual(bb(0).outgoing, [bb(3), bb(7)])
    self.assertItemsEqual(bb(3).outgoing, [bb(7)])
    self.assertItemsEqual(bb(7).outgoing, [pycfg.UNKNOWN_TARGET])
    self.assertItemsEqual(bb(11).outgoing, [pycfg.UNKNOWN_TARGET])


class InstructionsIndexTest(unittest.TestCase):

  @staticmethod
  def simple_function(x):
    x += 1
    y = 4
    x **= y
    return x + y

  def setUp(self):
    self.index = pycfg.InstructionsIndex(self.simple_function.func_code.co_code)

  def testNext(self):
    self.assertEqual(self.index.next(0), 3)
    self.assertEqual(self.index.next(6), 7)
    self.assertEqual(self.index.next(23), 26)

  def testPrev(self):
    self.assertEqual(self.index.prev(3), 0)
    self.assertEqual(self.index.prev(7), 6)
    self.assertEqual(self.index.prev(26), 23)

  def testRoundTrip(self):
    offset = 3
    while offset < len(self.simple_function.func_code.co_code) - 1:
      self.assertEqual(self.index.prev(self.index.next(offset)), offset)
      self.assertEqual(self.index.next(self.index.prev(offset)), offset)
      offset = self.index.next(offset)


class BytecodeReprTest(unittest.TestCase):

  def checkRoundTrip(self, code):
    # pylint: disable=eval-used
    self.assertEqual(eval(pycfg._bytecode_repr(code)), code)

  def testOtherTestMethods(self):
    for method in CFGTest.__dict__:
      if hasattr(method, "func_code"):
        self.checkRoundTrip(method.func_code.co_code)

  def testThisTestMethods(self):
    for method in BytecodeReprTest.__dict__:
      if hasattr(method, "func_code"):
        self.checkRoundTrip(method.func_code.co_code)

if __name__ == "__main__":
  test_inference.main()
