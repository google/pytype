"""Tests for pytype.abstractvm."""

import dis
import textwrap
import unittest


from pytype import pycfg
from pytype import vm
from pytype.pyc import pyc
from pytype.tests import test_inference

# It does not accept any styling for several different members for some reason.
# pylint: disable=invalid-name


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

  def run_instruction(self):
    self.instructions_executed.add(self.frame.f_lasti)
    return super(TraceVM, self).run_instruction()


class AncestorTraversalVirtualMachineTest(unittest.TestCase):

  def setUp(self):
    self.python_version = (2, 7)  # used to generate the bytecode below
    self.vm = TraceVM(self.python_version)

  srcNestedLoops = textwrap.dedent("""
    y = [1,2,3]
    z = 0
    for x in y:
      for a in y:
        if x:
          z += x*a
    """)
  codeNestedLoopsBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_CONST"], 0, 0,  # 0, arg=0
      dis.opmap["LOAD_CONST"], 1, 0,  # 3, arg=1
      dis.opmap["LOAD_CONST"], 2, 0,  # 6, arg=2
      dis.opmap["BUILD_LIST"], 3, 0,  # 9, arg=3
      dis.opmap["STORE_NAME"], 0, 0,  # 12, arg=0
      dis.opmap["LOAD_CONST"], 3, 0,  # 15, arg=3
      dis.opmap["STORE_NAME"], 1, 0,  # 18, arg=1
      dis.opmap["SETUP_LOOP"], 54, 0,  # 21, dest=78
      dis.opmap["LOAD_NAME"], 0, 0,  # 24, arg=0
      dis.opmap["GET_ITER"],  # 27
      dis.opmap["FOR_ITER"], 46, 0,  # 28, dest=77
      dis.opmap["STORE_NAME"], 2, 0,  # 31, arg=2
      dis.opmap["SETUP_LOOP"], 37, 0,  # 34, dest=74
      dis.opmap["LOAD_NAME"], 0, 0,  # 37, arg=0
      dis.opmap["GET_ITER"],  # 40
      dis.opmap["FOR_ITER"], 29, 0,  # 41, dest=73
      dis.opmap["STORE_NAME"], 3, 0,  # 44, arg=3
      dis.opmap["LOAD_NAME"], 2, 0,  # 47, arg=2
      dis.opmap["POP_JUMP_IF_FALSE"], 41, 0,  # 50, dest=41
      dis.opmap["LOAD_NAME"], 1, 0,  # 53, arg=1
      dis.opmap["LOAD_NAME"], 2, 0,  # 56, arg=2
      dis.opmap["LOAD_NAME"], 3, 0,  # 59, arg=3
      dis.opmap["BINARY_MULTIPLY"],  # 62
      dis.opmap["INPLACE_ADD"],  # 63
      dis.opmap["STORE_NAME"], 1, 0,  # 64, arg=1
      dis.opmap["JUMP_ABSOLUTE"], 41, 0,  # 67, dest=41
      dis.opmap["JUMP_ABSOLUTE"], 41, 0,  # 70 (unreachable), dest=41
      dis.opmap["POP_BLOCK"],  # 73
      dis.opmap["JUMP_ABSOLUTE"], 28, 0,  # 74, dest=28
      dis.opmap["POP_BLOCK"],  # 77
      dis.opmap["LOAD_CONST"], 4, 0,  # 78, arg=4
      dis.opmap["RETURN_VALUE"],  # 81
  ])

  def testEachInstructionOnceLoops(self):
    codeNestedLoops = pyc.compile_and_load(src=self.srcNestedLoops,
                                           python_version=self.python_version,
                                           filename="<>")
    self.assertEqual(codeNestedLoops.co_code,
                     self.codeNestedLoopsBytecode)
    self.vm.run_code(codeNestedLoops, run_builtins=False)
    # The numbers below are the instruction offsets in the above bytecode.
    self.assertItemsEqual(self.vm.instructions_executed,
                          [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 28, 31, 34, 37,
                           40, 41, 44, 47, 50, 53, 56, 59, 62, 63, 64, 67, 73,
                           74, 77, 78, 81])

  srcDeadCode = textwrap.dedent("""
    if False:
      x = 2
    raise RuntimeError
    x = 42
    """)
  codeDeadCodeBytecode = pycfg._list_to_string([
      dis.opmap["LOAD_NAME"], 0, 0,  # 0, arg=0
      dis.opmap["POP_JUMP_IF_FALSE"], 15, 0,  # 3, dest=15
      dis.opmap["LOAD_CONST"], 0, 0,  # 6, arg=0
      dis.opmap["STORE_NAME"], 1, 0,  # 9, arg=1
      dis.opmap["JUMP_FORWARD"], 0, 0,  # 12, dest=15
      dis.opmap["LOAD_NAME"], 2, 0,  # 15, arg=2
      dis.opmap["RAISE_VARARGS"], 1, 0,  # 18, arg=1
      dis.opmap["LOAD_CONST"], 1, 0,  # 21 (unreachable), arg=1
      dis.opmap["STORE_NAME"], 1, 0,  # 24 (unreachable), arg=1
      dis.opmap["LOAD_CONST"], 2, 0,  # 27 (unreachable), arg=2
      dis.opmap["RETURN_VALUE"],  # 30 (unreachable)
  ])

  def testEachInstructionOnceDeadCode(self):
    codeDeadCode = pyc.compile_and_load(src=self.srcDeadCode,
                                        python_version=self.python_version,
                                        filename="<>")
    self.assertEqual(codeDeadCode.co_code,
                     self.codeDeadCodeBytecode)
    try:
      self.vm.run_code(codeDeadCode, run_builtins=False)
    except RuntimeError:
      pass  # Ignore the exception that gets out.
    #              (it changed in CL 87770045)
    self.assertItemsEqual(self.vm.instructions_executed,
                          [0, 3, 6, 9, 12, 15, 18])


if __name__ == "__main__":
  test_inference.main()
