"""Tests for pytype.abstractvm."""

import dis
import textwrap
import unittest


from pytype import vm
from pytype.pyc import pyc
from pytype.tests import test_inference


class TraceVM(vm.VirtualMachine):

  def __init__(self, python_version):
    super(TraceVM, self).__init__(python_version)
    # There are multiple possible orderings of the basic blocks of the code, so
    # we collect the instructions in an order-independent way:
    self.instructions_executed = set()
    # Extra stuff that's defined in infer.CallTracer:
    # TODO(pludemann): refactor the classes?
    self._call_trace = set()
    self._functions = set()
    self._classes = set()
    self._unknowns = []

  def run_instruction(self, op, state):
    self.instructions_executed.add(op.index)
    return super(TraceVM, self).run_instruction(op, state)


def ListToString(lst):
  return "".join(chr(c) for c in lst)


class AncestorTraversalVirtualMachineTest(unittest.TestCase):

  def setUp(self):
    self.python_version = (2, 7)  # used to generate the bytecode below
    self.vm = TraceVM(self.python_version)

  src_nested_loop = textwrap.dedent("""
    y = [1,2,3]
    z = 0
    for x in y:
      for a in y:
        if x:
          z += x*a
    """)
  code_nested_loop = ListToString([
      dis.opmap["LOAD_CONST"], 0, 0,          # [0], 0, arg=0
      dis.opmap["LOAD_CONST"], 1, 0,          # [1], 3, arg=1
      dis.opmap["LOAD_CONST"], 2, 0,          # [2], 6, arg=2
      dis.opmap["BUILD_LIST"], 3, 0,          # [3], 9, arg=3
      dis.opmap["STORE_NAME"], 0, 0,          # [4], 12, arg=0
      dis.opmap["LOAD_CONST"], 3, 0,          # [5], 15, arg=3
      dis.opmap["STORE_NAME"], 1, 0,          # [6], 18, arg=1
      dis.opmap["SETUP_LOOP"], 54, 0,         # [7], 21, dest=78
      dis.opmap["LOAD_NAME"], 0, 0,           # [8], 24, arg=0
      dis.opmap["GET_ITER"],                  # [9], 27
      dis.opmap["FOR_ITER"], 46, 0,           # [10], 28, dest=77
      dis.opmap["STORE_NAME"], 2, 0,          # [11], 31, arg=2
      dis.opmap["SETUP_LOOP"], 37, 0,         # [12], 34, dest=74
      dis.opmap["LOAD_NAME"], 0, 0,           # [13], 37, arg=0
      dis.opmap["GET_ITER"],                  # [14], 40
      dis.opmap["FOR_ITER"], 29, 0,           # [15], 41, dest=73
      dis.opmap["STORE_NAME"], 3, 0,          # [16], 44, arg=3
      dis.opmap["LOAD_NAME"], 2, 0,           # [17], 47, arg=2
      dis.opmap["POP_JUMP_IF_FALSE"], 41, 0,  # [18], 50, dest=41
      dis.opmap["LOAD_NAME"], 1, 0,           # [19], 53, arg=1
      dis.opmap["LOAD_NAME"], 2, 0,           # [20], 56, arg=2
      dis.opmap["LOAD_NAME"], 3, 0,           # [21], 59, arg=3
      dis.opmap["BINARY_MULTIPLY"],           # [22], 62
      dis.opmap["INPLACE_ADD"],               # [23], 63
      dis.opmap["STORE_NAME"], 1, 0,          # [24], 64, arg=1
      dis.opmap["JUMP_ABSOLUTE"], 41, 0,      # [25], 67, dest=41
      dis.opmap["JUMP_ABSOLUTE"], 41, 0,      # [26], 70 (unreachable), dest=41
      dis.opmap["POP_BLOCK"],                 # [27], 73
      dis.opmap["JUMP_ABSOLUTE"], 28, 0,      # [28], 74, dest=28
      dis.opmap["POP_BLOCK"],                 # [29], 77
      dis.opmap["LOAD_CONST"], 4, 0,          # [30], 78, arg=4
      dis.opmap["RETURN_VALUE"],              # [31], 81
  ])

  def testEachInstructionOnceLoops(self):
    code_nested_loop = pyc.compile_src(src=self.src_nested_loop,
                                       python_version=self.python_version,
                                       filename="<>")
    self.assertEqual(code_nested_loop.co_code,
                     self.code_nested_loop)
    self.vm.run_program(self.src_nested_loop, run_builtins=False)
    # We expect all instructions, except 26, in the above to execute.
    self.assertItemsEqual(self.vm.instructions_executed,
                          set(range(32)) - {26})

  src_deadcode = textwrap.dedent("""
    if False:
      x = 2
    raise RuntimeError
    x = 42
    """)
  code_deadcode = ListToString([
      dis.opmap["LOAD_NAME"], 0, 0,           # [0] 0, arg=0
      dis.opmap["POP_JUMP_IF_FALSE"], 15, 0,  # [1] 3, dest=15
      dis.opmap["LOAD_CONST"], 0, 0,          # [2] 6, arg=0
      dis.opmap["STORE_NAME"], 1, 0,          # [3] 9, arg=1
      dis.opmap["JUMP_FORWARD"], 0, 0,        # [4] 12, dest=15
      dis.opmap["LOAD_NAME"], 2, 0,           # [5] 15, arg=2
      dis.opmap["RAISE_VARARGS"], 1, 0,       # [6] 18, arg=1
      dis.opmap["LOAD_CONST"], 1, 0,          # [7] 21 (unreachable), arg=1
      dis.opmap["STORE_NAME"], 1, 0,          # [8] 24 (unreachable), arg=1
      dis.opmap["LOAD_CONST"], 2, 0,          # [9] 27 (unreachable), arg=2
      dis.opmap["RETURN_VALUE"],              # [10] 30 (unreachable)
  ])

  def testEachInstructionOnceDeadCode(self):
    code_deadcode = pyc.compile_src(src=self.src_deadcode,
                                    python_version=self.python_version,
                                    filename="<>")
    self.assertEqual(code_deadcode.co_code,
                     self.code_deadcode)
    try:
      self.vm.run_program(self.src_deadcode, run_builtins=False)
    except vm.VirtualMachineError:
      pass  # The code we test throws an exception. Ignore it.
    self.assertItemsEqual(self.vm.instructions_executed, range(7))


if __name__ == "__main__":
  test_inference.main()
