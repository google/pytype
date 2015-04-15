"""Tests for blocks.py."""


from pytype import blocks
from pytype import vm
from pytype.tests import test_inference


class BytecodeTest(test_inference.InferenceTest):
  """Tests for process_code in blocks.py and VM integration."""

  def test_simple(self):
    # Disassembled from:
    # | return None
    code = self.make_code([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=1 (1)
        0x53,  # 3 RETURN_VALUE
    ], name="simple")
    code = blocks.process_code(code)
    v = vm.VirtualMachine(self.PYTHON_VERSION)
    v.run_bytecode(code, v.program.NewCFGNode("init"))

  def test_diamond(self):
    # Disassembled from:
    # | if []:
    # |   y = 1
    # | elif []:
    # |   y = 2
    # | elif []:
    # |   y = None
    # | return y
    code = self.make_code([
        0x67, 0, 0,   #  0 BUILD_LIST, arg=0,
        0x72, 15, 0,  #  3 POP_JUMP_IF_FALSE, dest=15,
        0x64, 1, 0,   #  6 LOAD_CONST, arg=1 (1),
        0x7d, 1, 0,   #  9 STORE_FAST, arg=1 "y",
        0x6e, 30, 0,  # 12 JUMP_FORWARD, dest=45,
        0x67, 0, 0,   # 15 BUILD_LIST, arg=0,
        0x72, 30, 0,  # 18 POP_JUMP_IF_FALSE, dest=30,
        0x64, 2, 0,   # 21 LOAD_CONST, arg=2 (2),
        0x7d, 1, 0,   # 24 STORE_FAST, arg=1 "y",
        0x6e, 15, 0,  # 27 JUMP_FORWARD, dest=45,
        0x67, 0, 0,   # 30 BUILD_LIST, arg=0,
        0x72, 45, 0,  # 33 POP_JUMP_IF_FALSE, dest=45,
        0x64, 0, 0,   # 36 LOAD_CONST, arg=0 (None),
        0x7d, 1, 0,   # 39 STORE_FAST, arg=1 "y",
        0x6e, 0, 0,   # 42 JUMP_FORWARD, dest=45,
        0x7c, 1, 0,   # 45 LOAD_FAST, arg=1,
        0x53,         # 48 RETURN_VALUE
    ])
    code = blocks.process_code(code)
    v = vm.VirtualMachine(self.PYTHON_VERSION)
    v.run_bytecode(code, v.program.NewCFGNode("init"))

if __name__ == "__main__":
  test_inference.main()
