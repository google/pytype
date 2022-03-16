"""Tests for vm.py.

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

import textwrap

from pytype import blocks
from pytype import context
from pytype import utils
from pytype import vm
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.tests import test_base
from pytype.tests import test_utils


# The tests in this file check disassembled bytecode, which varies from version
# to version, so we fix the test version.
_OPMAP = {v.__name__: k for k, v in opcodes.python_3_7_mapping.items()}


class TraceVM(vm.VirtualMachine):
  """Special VM that remembers which instructions it executed."""

  def __init__(self, ctx):
    super().__init__(ctx)
    # There are multiple possible orderings of the basic blocks of the code, so
    # we collect the instructions in an order-independent way:
    self.instructions_executed = set()
    # Extra stuff that's defined in tracer_vm.CallTracer:
    self._call_trace = set()
    self._functions = set()
    self._classes = set()
    self._unknowns = []

  def run_instruction(self, op, state):
    self.instructions_executed.add(op.index)
    return super().run_instruction(op, state)


class VmTestBase(test_base.BaseTest, test_utils.MakeCodeMixin):
  """Base for VM tests."""

  def setUp(self):
    super().setUp()
    self.ctx = self.make_context()

  def make_context(self):
    return context.Context(options=self.options, loader=self.loader)


class TraceVmTestBase(VmTestBase):
  """Base for VM tests with a tracer vm."""

  def setUp(self):
    super().setUp()
    self.ctx.vm = TraceVM(self.ctx)


class BytecodeTest(TraceVmTestBase):
  """Tests for process_code in blocks.py and VM integration."""

  # We only test Python 3.7 bytecode (see setUpClass()), since the bytecode
  # changes from version to version.
  python_version = (3, 7)

  @test_utils.skipUnlessPy((3, 7), reason="Only testing one version.")
  def test_simple(self):
    # Disassembled from:
    # | return None
    code = self.make_code([
        0x64, 1,  # 0 LOAD_CONST, arg=1 (1)
        0x53, 0,  # 3 RETURN_VALUE (0)
    ], name="simple")
    code = blocks.process_code(code, self.python_version)
    ctx = self.make_context()
    ctx.vm = vm.VirtualMachine(ctx)
    ctx.vm.run_bytecode(ctx.program.NewCFGNode(), code)

  @test_utils.skipUnlessPy((3, 7), reason="Only testing one version.")
  def test_diamond(self):
    # Disassembled from:
    # | if []:
    # |   y = 1
    # | elif []:
    # |   y = 2
    # | elif []:
    # |   y = None
    # | return y
    o = test_utils.Py37Opcodes
    code = self.make_code([
        o.BUILD_LIST, 0,
        o.POP_JUMP_IF_FALSE, 10,
        o.LOAD_CONST, 1,
        o.STORE_FAST, 0,
        o.JUMP_FORWARD, 18,
        o.BUILD_LIST, 0,
        o.POP_JUMP_IF_FALSE, 20,
        o.LOAD_CONST, 2,
        o.STORE_FAST, 0,
        o.JUMP_FORWARD, 8,
        o.BUILD_LIST, 0,
        o.POP_JUMP_IF_FALSE, 28,
        o.LOAD_CONST, 0,
        o.STORE_FAST, 0,
        o.LOAD_FAST, 0,
        o.RETURN_VALUE, 0,
    ])
    code = blocks.process_code(code, self.python_version)
    ctx = self.make_context()
    ctx.vm = vm.VirtualMachine(ctx)
    ctx.vm.run_bytecode(ctx.program.NewCFGNode(), code)

  src_nested_loop = textwrap.dedent("""
    y = [1,2,3]
    z = 0
    for x in y:
      for a in y:
        if x:
          z += x*a
    """)
  code_nested_loop = bytes([
      _OPMAP["LOAD_CONST"], 0,
      _OPMAP["LOAD_CONST"], 1,
      _OPMAP["LOAD_CONST"], 2,
      _OPMAP["BUILD_LIST"], 3,
      _OPMAP["STORE_NAME"], 0,
      _OPMAP["LOAD_CONST"], 3,
      _OPMAP["STORE_NAME"], 1,
      _OPMAP["SETUP_LOOP"], 42,
      _OPMAP["LOAD_NAME"], 0,
      _OPMAP["GET_ITER"], 0,
      _OPMAP["FOR_ITER"], 34,
      _OPMAP["STORE_NAME"], 2,
      _OPMAP["SETUP_LOOP"], 28,
      _OPMAP["LOAD_NAME"], 0,
      _OPMAP["GET_ITER"], 0,
      _OPMAP["FOR_ITER"], 20,
      _OPMAP["STORE_NAME"], 3,
      _OPMAP["LOAD_NAME"], 2,
      _OPMAP["POP_JUMP_IF_FALSE"], 30,
      _OPMAP["LOAD_NAME"], 1,
      _OPMAP["LOAD_NAME"], 2,
      _OPMAP["LOAD_NAME"], 3,
      _OPMAP["BINARY_MULTIPLY"], 0,
      _OPMAP["INPLACE_ADD"], 0,
      _OPMAP["STORE_NAME"], 1,
      _OPMAP["JUMP_ABSOLUTE"], 30,
      _OPMAP["POP_BLOCK"], 0,
      _OPMAP["JUMP_ABSOLUTE"], 20,
      _OPMAP["POP_BLOCK"], 0,
      _OPMAP["LOAD_CONST"], 4,
      _OPMAP["RETURN_VALUE"], 0,
  ])

  @test_utils.skipUnlessPy((3, 7), reason="Only testing one version.")
  def test_each_instruction_once_loops(self):
    code_nested_loop = pyc.compile_src(
        src=self.src_nested_loop,
        python_version=self.python_version,
        python_exe=next(utils.get_python_exes(self.python_version)),
        filename="<>")
    self.assertEqual(code_nested_loop.co_code,
                     self.code_nested_loop)
    self.ctx.vm.run_program(self.src_nested_loop, "", maximum_depth=10)
    # TODO(b/175443170): find a way to keep this test in sync with constant
    # folding (which removes some opcodes)
    # We expect all instructions in the above to execute.
    # self.assertCountEqual(self.ctx.vm.instructions_executed,
    #                       set(range(31)))

  src_deadcode = textwrap.dedent("""
    if False:
      x = 2
    raise RuntimeError
    x = 42
    """)
  code_deadcode = bytes([
      _OPMAP["LOAD_NAME"], 0,
      _OPMAP["RAISE_VARARGS"], 1,
      _OPMAP["LOAD_CONST"], 0,
      _OPMAP["STORE_NAME"], 1,
      _OPMAP["LOAD_CONST"], 1,
      _OPMAP["RETURN_VALUE"], 0,
  ])

  @test_utils.skipUnlessPy((3, 7), reason="Only testing one version.")
  def test_each_instruction_once_dead_code(self):
    code_deadcode = pyc.compile_src(
        src=self.src_deadcode,
        python_version=self.python_version,
        python_exe=next(utils.get_python_exes(self.python_version)),
        filename="<>")
    self.assertEqual(code_deadcode.co_code,
                     self.code_deadcode)
    self.ctx.vm.run_program(self.src_deadcode, "", maximum_depth=10)
    self.assertCountEqual(self.ctx.vm.instructions_executed, [0, 1])


class TraceTest(TraceVmTestBase):
  """Tests for opcode tracing in the VM."""

  def test_empty_data(self):
    """Test that we can trace values without data."""
    op = test_utils.FakeOpcode("foo.py", 123, "foo")
    self.ctx.vm.trace_opcode(op, "x", 42)
    self.assertEqual(self.ctx.vm.opcode_traces, [(op, "x", (None,))])

  def test_const(self):
    src = textwrap.dedent("""
      x = 1  # line 1
      y = x  # line 2
    """).lstrip()
    # Compiles to:
    #     0 LOAD_CONST     0 (1)
    #     3 STORE_NAME     0 (x)
    #
    #     6 LOAD_NAME      0 (x)
    #     9 STORE_NAME     1 (y)
    #    12 LOAD_CONST     1 (None)
    #    15 RETURN_VALUE
    self.ctx.vm.run_program(src, "", maximum_depth=10)
    expected = [
        # (opcode, line number, symbol)
        ("LOAD_CONST", 1, 1),
        ("STORE_NAME", 1, "x"),
        ("LOAD_NAME", 2, "x"),
        ("STORE_NAME", 2, "y"),
        ("LOAD_CONST", 2, None)
    ]
    actual = [(op.name, op.line, symbol)
              for op, symbol, _ in self.ctx.vm.opcode_traces]
    self.assertEqual(actual, expected)


class AnnotationsTest(VmTestBase):
  """Tests for recording annotations."""

  def test_record_local_ops(self):
    self.ctx.vm.run_program("v: int = None", "", maximum_depth=10)
    self.assertEqual(
        self.ctx.vm.local_ops, {
            "<module>": [
                vm.LocalOp(name="v", op=vm.LocalOp.ASSIGN),
                vm.LocalOp(name="v", op=vm.LocalOp.ANNOTATE)
            ]
        })


if __name__ == "__main__":
  test_base.main()
