"""Tests for vm.py."""

import textwrap

from pytype import analyze
from pytype import blocks
from pytype import compat
from pytype import errors
from pytype import utils
from pytype import vm
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.tests import test_base
from pytype.tests import test_utils

import six

_PY2_OPMAP = {v.__name__: k for k, v in opcodes.python2_mapping.items()}


class TraceVM(vm.VirtualMachine):
  """Special VM that remembers which instructions it executed."""

  def __init__(self, options, loader):
    super().__init__(errors.ErrorLog(), options, loader=loader)
    # There are multiple possible orderings of the basic blocks of the code, so
    # we collect the instructions in an order-independent way:
    self.instructions_executed = set()
    # Extra stuff that's defined in analyze.CallTracer:
    self._call_trace = set()
    self._functions = set()
    self._classes = set()
    self._unknowns = []

  def run_instruction(self, op, state):
    self.instructions_executed.add(op.index)
    return super().run_instruction(op, state)


class BytecodeTest(test_base.BaseTest, test_utils.MakeCodeMixin):
  """Tests for process_code in blocks.py and VM integration."""

  # We only test Python 2 bytecode.
  PY_MAJOR_VERSIONS = [2]

  def setUp(self):
    super().setUp()
    self.errorlog = errors.ErrorLog()
    self.trace_vm = TraceVM(self.options, self.loader)

  def test_simple(self):
    # Disassembled from:
    # | return None
    code = self.make_code([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=1 (1)
        0x53,  # 3 RETURN_VALUE
    ], name="simple")
    code = blocks.process_code(code, self.python_version)
    v = vm.VirtualMachine(self.errorlog, self.options, loader=self.loader)
    v.run_bytecode(v.program.NewCFGNode(), code)

  def test_diamond(self):
    # Disassembled from:
    # | if []:
    # |   y = 1
    # | elif []:
    # |   y = 2
    # | elif []:
    # |   y = None
    # | return y
    o = test_utils.Py2Opcodes
    code = self.make_code([
        o.BUILD_LIST, 0, 0,
        o.POP_JUMP_IF_FALSE, 15, 0,
        o.LOAD_CONST, 1, 0,
        o.STORE_FAST, 1, 0,
        o.JUMP_FORWARD, 30, 0,
        o.BUILD_LIST, 0, 0,
        o.POP_JUMP_IF_FALSE, 30, 0,
        o.LOAD_CONST, 2, 0,
        o.STORE_FAST, 1, 0,
        o.JUMP_FORWARD, 15, 0,
        o.BUILD_LIST, 0, 0,
        o.POP_JUMP_IF_FALSE, 45, 0,
        o.LOAD_CONST, 0, 0,
        o.STORE_FAST, 1, 0,
        o.JUMP_FORWARD, 0, 0,
        o.LOAD_FAST, 1, 0,
        o.RETURN_VALUE,
    ])
    code = blocks.process_code(code, self.python_version)
    v = vm.VirtualMachine(self.errorlog, self.options, loader=self.loader)
    v.run_bytecode(v.program.NewCFGNode(), code)

  src_nested_loop = textwrap.dedent("""
    y = [1,2,3]
    z = 0
    for x in y:
      for a in y:
        if x:
          z += x*a
    """)
  code_nested_loop = compat.int_array_to_bytes([
      _PY2_OPMAP["LOAD_CONST"], 0, 0,          # [0], 0, arg=0
      _PY2_OPMAP["LOAD_CONST"], 1, 0,          # [1], 3, arg=1
      _PY2_OPMAP["LOAD_CONST"], 2, 0,          # [2], 6, arg=2
      _PY2_OPMAP["BUILD_LIST"], 3, 0,          # [3], 9, arg=3
      _PY2_OPMAP["STORE_NAME"], 0, 0,          # [4], 12, arg=0
      _PY2_OPMAP["LOAD_CONST"], 3, 0,          # [5], 15, arg=3
      _PY2_OPMAP["STORE_NAME"], 1, 0,          # [6], 18, arg=1
      _PY2_OPMAP["SETUP_LOOP"], 54, 0,         # [7], 21, dest=78
      _PY2_OPMAP["LOAD_NAME"], 0, 0,           # [8], 24, arg=0
      _PY2_OPMAP["GET_ITER"],                  # [9], 27
      _PY2_OPMAP["FOR_ITER"], 46, 0,           # [10], 28, dest=77
      _PY2_OPMAP["STORE_NAME"], 2, 0,          # [11], 31, arg=2
      _PY2_OPMAP["SETUP_LOOP"], 37, 0,         # [12], 34, dest=74
      _PY2_OPMAP["LOAD_NAME"], 0, 0,           # [13], 37, arg=0
      _PY2_OPMAP["GET_ITER"],                  # [14], 40
      _PY2_OPMAP["FOR_ITER"], 29, 0,           # [15], 41, dest=73
      _PY2_OPMAP["STORE_NAME"], 3, 0,          # [16], 44, arg=3
      _PY2_OPMAP["LOAD_NAME"], 2, 0,           # [17], 47, arg=2
      _PY2_OPMAP["POP_JUMP_IF_FALSE"], 41, 0,  # [18], 50, dest=41
      _PY2_OPMAP["LOAD_NAME"], 1, 0,           # [19], 53, arg=1
      _PY2_OPMAP["LOAD_NAME"], 2, 0,           # [20], 56, arg=2
      _PY2_OPMAP["LOAD_NAME"], 3, 0,           # [21], 59, arg=3
      _PY2_OPMAP["BINARY_MULTIPLY"],           # [22], 62
      _PY2_OPMAP["INPLACE_ADD"],               # [23], 63
      _PY2_OPMAP["STORE_NAME"], 1, 0,          # [24], 64, arg=1
      _PY2_OPMAP["JUMP_ABSOLUTE"], 41, 0,      # [25], 67, dest=41
      _PY2_OPMAP["JUMP_ABSOLUTE"], 41, 0,      # [26], 70 (unreachable), dest=41
      _PY2_OPMAP["POP_BLOCK"],                 # [27], 73
      _PY2_OPMAP["JUMP_ABSOLUTE"], 28, 0,      # [28], 74, dest=28
      _PY2_OPMAP["POP_BLOCK"],                 # [29], 77
      _PY2_OPMAP["LOAD_CONST"], 4, 0,          # [30], 78, arg=4
      _PY2_OPMAP["RETURN_VALUE"],              # [31], 81
  ])

  def test_each_instruction_once_loops(self):
    code_nested_loop = pyc.compile_src(
        src=self.src_nested_loop,
        python_version=self.python_version,
        python_exe=utils.get_python_exe(self.python_version),
        filename="<>")
    self.assertEqual(code_nested_loop.co_code,
                     self.code_nested_loop)
    self.trace_vm.run_program(self.src_nested_loop, "", maximum_depth=10)
    # We expect all instructions, except 26, in the above to execute.
    six.assertCountEqual(self, self.trace_vm.instructions_executed,
                         set(range(32)) - {26})

  src_deadcode = textwrap.dedent("""
    if False:
      x = 2
    raise RuntimeError
    x = 42
    """)
  code_deadcode = compat.int_array_to_bytes([
      _PY2_OPMAP["LOAD_NAME"], 0, 0,           # [0] 0, arg=0
      _PY2_OPMAP["POP_JUMP_IF_FALSE"], 15, 0,  # [1] 3, dest=15
      _PY2_OPMAP["LOAD_CONST"], 0, 0,          # [2] 6, arg=0
      _PY2_OPMAP["STORE_NAME"], 1, 0,          # [3] 9, arg=1
      _PY2_OPMAP["JUMP_FORWARD"], 0, 0,        # [4] 12, dest=15
      _PY2_OPMAP["LOAD_NAME"], 2, 0,           # [5] 15, arg=2
      _PY2_OPMAP["RAISE_VARARGS"], 1, 0,       # [6] 18, arg=1
      _PY2_OPMAP["LOAD_CONST"], 1, 0,          # [7] 21 (unreachable), arg=1
      _PY2_OPMAP["STORE_NAME"], 1, 0,          # [8] 24 (unreachable), arg=1
      _PY2_OPMAP["LOAD_CONST"], 2, 0,          # [9] 27 (unreachable), arg=2
      _PY2_OPMAP["RETURN_VALUE"],              # [10] 30 (unreachable)
  ])

  def test_each_instruction_once_dead_code(self):
    code_deadcode = pyc.compile_src(
        src=self.src_deadcode,
        python_version=self.python_version,
        python_exe=utils.get_python_exe(self.python_version),
        filename="<>")
    self.assertEqual(code_deadcode.co_code,
                     self.code_deadcode)
    try:
      self.trace_vm.run_program(self.src_deadcode, "", maximum_depth=10)
    except vm.VirtualMachineError:
      pass  # The code we test throws an exception. Ignore it.
    six.assertCountEqual(self,
                         self.trace_vm.instructions_executed, [0, 1, 5, 6])


class TraceTest(test_base.BaseTest, test_utils.MakeCodeMixin):
  """Tests for opcode tracing in the VM."""

  def setUp(self):
    super().setUp()
    self.errorlog = errors.ErrorLog()
    self.trace_vm = TraceVM(self.options, self.loader)

  def test_empty_data(self):
    """Test that we can trace values without data."""
    op = test_utils.FakeOpcode("foo.py", 123, "foo")
    self.trace_vm.trace_opcode(op, "x", 42)
    self.assertEqual(self.trace_vm.opcode_traces, [(op, "x", (None,))])

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
    self.trace_vm.run_program(src, "", maximum_depth=10)
    expected = [
        # (opcode, line number, symbol)
        ("LOAD_CONST", 1, 1),
        ("STORE_NAME", 1, "x"),
        ("LOAD_NAME", 2, "x"),
        ("STORE_NAME", 2, "y"),
        ("LOAD_CONST", 2, None)
    ]
    actual = [(op.name, op.line, symbol)
              for op, symbol, _ in self.trace_vm.opcode_traces]
    self.assertEqual(actual, expected)


@test_utils.skipBeforePy((3, 6), reason="Variable annotations are 3.6+.")
class AnnotationsTest(test_base.BaseTest, test_utils.MakeCodeMixin):
  """Tests for recording annotations."""

  def setUp(self):
    super().setUp()
    self.errorlog = errors.ErrorLog()
    self.vm = analyze.CallTracer(self.errorlog, self.options, self.loader)

  def test_record_local_ops(self):
    self.vm.run_program("v: int = None", "", maximum_depth=10)
    self.assertEqual(self.vm.local_ops, {
        "<module>": [vm.LocalOp(name="v", op=vm.LocalOp.ASSIGN),
                     vm.LocalOp(name="v", op=vm.LocalOp.ANNOTATE)]})


class DirectorLineNumbersTest(test_base.BaseTest, test_utils.MakeCodeMixin):

  def setUp(self):
    super().setUp()
    self.errorlog = errors.ErrorLog()
    self.vm = analyze.CallTracer(self.errorlog, self.options, self.loader)

  def run_program(self, src):
    return self.vm.run_program(textwrap.dedent(src), "", maximum_depth=10)

  def test_type_comment_on_multiline_value(self):
    self.run_program("""
      v = [
        ("hello",
         "world",  # type: should_be_ignored

        )
      ]  # type: dict
    """)
    # The line number of STORE_NAME v changes between versions.
    if self.python_version >= (3, 8):
      lineno = 2
    elif self.python_version >= (3, 7):
      lineno = 3
    else:
      lineno = 4
    self.assertEqual({lineno: "dict"}, self.vm.director.type_comments)

  def test_type_comment_with_trailing_comma(self):
    self.run_program("""
      v = [
        ("hello",
         "world"
        ),
      ]  # type: dict
      w = [
        ["hello",
         "world"
        ],  # some comment
      ]  # type: dict
    """)
    # The line numbers of STORE_NAME change between versions.
    if self.python_version >= (3, 8):
      v_lineno = 2
      w_lineno = 7
    elif self.python_version >= (3, 7):
      v_lineno = 3
      w_lineno = 9
    else:
      v_lineno = 4
      w_lineno = 9
    self.assertEqual({v_lineno: "dict", w_lineno: "dict"},
                     self.vm.director.type_comments)

  def test_decorators(self):
    self.run_program("""
      class A:
        '''
        @decorator in a docstring
        '''
        @real_decorator
        def f(x):
          x = foo @ bar @ baz

        @decorator(
            x, y
        )

        def bar():
          pass
    """)
    if self.python_version >= (3, 8):
      real_decorator_lineno = 7
      decorator_lineno = 14
    else:
      real_decorator_lineno = 6
      decorator_lineno = 11
    self.assertEqual(
        self.vm.director.decorators, {real_decorator_lineno, decorator_lineno})

  def test_stacked_decorators(self):
    self.run_program("""
      @decorator(
          x, y
      )

      @foo

      class A:
          pass
    """)
    lineno = 8 if self.python_version >= (3, 8) else 6
    self.assertEqual(self.vm.director.decorators, {lineno})

  def test_overload(self):
    self.run_program("""
      from typing import overload

      @overload
      def f() -> int: ...

      @overload
      def f(x: str) -> str: ...

      def f(x=None):
        return 0 if x is None else x
    """)
    self.assertEqual(self.vm.director.decorators, {5, 8})


test_base.main(globals(), __name__ == "__main__")
