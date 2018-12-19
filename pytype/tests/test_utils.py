"""Utility class and function for tests."""

import collections
import subprocess

from pytype import compat
from pytype import state as frame_state
from pytype.pyc import loadmarshal

import unittest


FakeCode = collections.namedtuple("FakeCode", "co_filename co_name")


class FakeOpcode(object):
  """Util class for generating fake Opcode for testing."""

  def __init__(self, filename, line, methodname):
    self.code = FakeCode(filename, methodname)
    self.line = line
    self.name = "FAKE_OPCODE"

  def to_stack(self):
    return [frame_state.SimpleFrame(self)]


def fake_stack(length):
  return [frame_state.SimpleFrame(FakeOpcode("foo.py", i, "function%d" % i))
          for i in range(length)]


class OperatorsTestMixin(object):
  """Mixin providing utilities for operators tests."""

  def check_expr(self, expr, assignments, expected_return):
    """Check the expression."""
    # Note that testing "1+2" as opposed to "x=1; y=2; x+y" doesn't really test
    # anything because the peephole optimizer converts "1+2" to "3" and __add__
    # isn't called. So, need to defeat the optimizer by replacing the constants
    # by variables, which will result in calling __add__ et al.

    # Join the assignments with ";" to avoid figuring out the exact indentation:
    assignments = "; ".join(assignments)
    src = """
      def f():
        {assignments}
        return {expr}
      f()
    """.format(expr=expr, assignments=assignments)
    ty = self.Infer(src, deep=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), expected_return)

  def check_binary(self, function_name, op):
    """Check the binary operator."""
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self, unused_x):
          return 3j
      class Bar(object):
        pass
      def f():
        return Foo() {op} Bar()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def check_unary(self, function_name, op, ret=None):
    """Check the unary operator."""
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self):
          return 3j
      def f():
        return {op} Foo()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), ret or self.complex)

  def check_reverse(self, function_name, op):
    """Check the reverse operator."""
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      class Bar(Foo):
        def __r{function_name}__(self, x):
          return "foo"
      def f():
        return Foo() {op} 1  # use Foo.__{function_name}__
      def g():
        return 1 {op} Bar()  # use Bar.__r{function_name}__
      def h():
        return Foo() {op} Bar()  # use Bar.__r{function_name}__
      def i():
        return Foo() {op} Foo()  # use Foo.__{function_name}__
      f(); g(); h(); i()
    """.format(op=op, function_name=function_name),
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)
    self.assertHasReturnType(ty.Lookup("g"), self.str)
    self.assertHasReturnType(ty.Lookup("h"), self.str)
    self.assertHasReturnType(ty.Lookup("i"), self.complex)

  def check_inplace(self, function_name, op):
    """Check the inplace operator."""
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      def f():
        x = Foo()
        x {op} None
        return x
      f()
    """.format(op=op, function_name=function_name),
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)


# TODO(sivachandra): Remove this class in favor of the class OperatorsTestMixin.
# It is not a drop-in-replacement currently, but there is no reason why it
# cannot be made one.
class InplaceTestMixin(object):
  """Mixin providing a method to check in-place operators."""

  def _check_inplace(self, op, assignments, expected_return):
    """Check the inplace operator."""
    assignments = "; ".join(assignments)
    src = """
      def f(x, y):
        {assignments}
        x {op}= y
        return x
      a = f(1, 2)
    """.format(assignments=assignments, op=op)
    ty = self.Infer(src, deep=False)
    self.assertTypeEquals(ty.Lookup("a").type, expected_return)


class TestCollectionsMixin(object):
  """Mixin providing utils for tests on the collections module."""

  def _testCollectionsObject(self, obj, good_arg, bad_arg, error):  # pylint: disable=invalid-name
    result = self.CheckWithErrors("""\
      import collections
      def f(x: collections.{obj}): ...
      f({good_arg})
      f({bad_arg})  # line 5
    """.format(obj=obj, good_arg=good_arg, bad_arg=bad_arg))
    self.assertErrorLogIs(result, [(4, "wrong-arg-types", error)])


class MakeCodeMixin(object):
  """Mixin providing a method to make a code object from bytecode."""

  def make_code(self, int_array, name="testcode"):
    """Utility method for creating CodeType objects."""
    return loadmarshal.CodeType(
        argcount=0, kwonlyargcount=0, nlocals=2, stacksize=2, flags=0,
        consts=[None, 1, 2], names=[], varnames=["x", "y"], filename="",
        name=name, firstlineno=1, lnotab=[], freevars=[], cellvars=[],
        code=compat.int_array_to_bytes(int_array),
        python_version=self.python_version)


class Py2Opcodes(object):
  """Define constants for PY2 opcodes."""

  STOP_CODE = 0
  POP_TOP = 1
  ROT_TWO = 2
  ROT_THREE = 3
  DUP_TOP = 4
  ROT_FOUR = 5
  NOP = 9
  UNARY_POSITIVE = 10
  UNARY_NEGATIVE = 11
  UNARY_NOT = 12
  UNARY_CONVERT = 13
  UNARY_INVERT = 15
  BINARY_POWER = 19
  BINARY_MULTIPLY = 20
  BINARY_DIVIDE = 21
  BINARY_MODULO = 22
  BINARY_ADD = 23
  BINARY_SUBTRACT = 24
  BINARY_SUBSCR = 25
  BINARY_FLOOR_DIVIDE = 26
  BINARY_TRUE_DIVIDE = 27
  INPLACE_FLOOR_DIVIDE = 28
  INPLACE_TRUE_DIVIDE = 29
  SLICE_0 = 30
  SLICE_1 = 31
  SLICE_2 = 32
  SLICE_3 = 33
  STORE_SLICE_0 = 40
  STORE_SLICE_1 = 41
  STORE_SLICE_2 = 42
  STORE_SLICE_3 = 43
  DELETE_SLICE_0 = 50
  DELETE_SLICE_1 = 51
  DELETE_SLICE_2 = 52
  DELETE_SLICE_3 = 53
  STORE_MAP = 54
  INPLACE_ADD = 55
  INPLACE_SUBTRACT = 56
  INPLACE_MULTIPLY = 57
  INPLACE_DIVIDE = 58
  INPLACE_MODULO = 59
  STORE_SUBSCR = 60
  DELETE_SUBSCR = 61
  BINARY_LSHIFT = 62
  BINARY_RSHIFT = 63
  BINARY_AND = 64
  BINARY_XOR = 65
  BINARY_OR = 66
  INPLACE_POWER = 67
  GET_ITER = 68
  PRINT_EXPR = 70
  PRINT_ITEM = 71
  PRINT_NEWLINE = 72
  PRINT_ITEM_TO = 73
  PRINT_NEWLINE_TO = 74
  INPLACE_LSHIFT = 75
  INPLACE_RSHIFT = 76
  INPLACE_AND = 77
  INPLACE_XOR = 78
  INPLACE_OR = 79
  BREAK_LOOP = 80
  WITH_CLEANUP = 81
  LOAD_LOCALS = 82
  RETURN_VALUE = 83
  IMPORT_STAR = 84
  EXEC_STMT = 85
  YIELD_VALUE = 86
  POP_BLOCK = 87
  END_FINALLY = 88
  BUILD_CLASS = 89
  STORE_NAME = 90
  DELETE_NAME = 91
  UNPACK_SEQUENCE = 92
  FOR_ITER = 93
  LIST_APPEND = 94
  STORE_ATTR = 95
  DELETE_ATTR = 96
  STORE_GLOBAL = 97
  DELETE_GLOBAL = 98
  DUP_TOPX = 99
  LOAD_CONST = 100
  LOAD_NAME = 101
  BUILD_TUPLE = 102
  BUILD_LIST = 103
  BUILD_SET = 104
  BUILD_MAP = 105
  LOAD_ATTR = 106
  COMPARE_OP = 107
  IMPORT_NAME = 108
  IMPORT_FROM = 109
  JUMP_FORWARD = 110
  JUMP_IF_FALSE_OR_POP = 111
  JUMP_IF_TRUE_OR_POP = 112
  JUMP_ABSOLUTE = 113
  POP_JUMP_IF_FALSE = 114
  POP_JUMP_IF_TRUE = 115
  LOAD_GLOBAL = 116
  CONTINUE_LOOP = 119
  SETUP_LOOP = 120
  SETUP_EXCEPT = 121
  SETUP_FINALLY = 122
  LOAD_FAST = 124
  STORE_FAST = 125
  DELETE_FAST = 126
  RAISE_VARARGS = 130
  CALL_FUNCTION = 131
  MAKE_FUNCTION = 132
  BUILD_SLICE = 133
  MAKE_CLOSURE = 134
  LOAD_CLOSURE = 135
  LOAD_DEREF = 136
  STORE_DEREF = 137
  CALL_FUNCTION_VAR = 140
  CALL_FUNCTION_KW = 141
  CALL_FUNCTION_VAR_KW = 142
  SETUP_WITH = 143
  EXTENDED_ARG = 145
  SET_ADD = 146
  MAP_ADD = 147


class Py3Opcodes(object):
  """Define constants for PY3 opcodes."""

  POP_TOP = 1
  ROT_TWO = 2
  ROT_THREE = 3
  DUP_TOP = 4
  DUP_TOP_TWO = 5
  NOP = 9
  UNARY_POSITIVE = 10
  UNARY_NEGATIVE = 11
  UNARY_NOT = 12
  UNARY_INVERT = 15
  BINARY_MATRIX_MULTIPLY = 16
  INPLACE_MATRIX_MULTIPLY = 17
  BINARY_POWER = 19
  BINARY_MULTIPLY = 20
  BINARY_MODULO = 22
  BINARY_ADD = 23
  BINARY_SUBTRACT = 24
  BINARY_SUBSCR = 25
  BINARY_FLOOR_DIVIDE = 26
  BINARY_TRUE_DIVIDE = 27
  INPLACE_FLOOR_DIVIDE = 28
  INPLACE_TRUE_DIVIDE = 29
  GET_AITER = 50
  GET_ANEXT = 51
  BEFORE_ASYNC_WITH = 52
  STORE_MAP = 54
  INPLACE_ADD = 55
  INPLACE_SUBTRACT = 56
  INPLACE_MULTIPLY = 57
  INPLACE_MODULO = 59
  STORE_SUBSCR = 60
  DELETE_SUBSCR = 61
  BINARY_LSHIFT = 62
  BINARY_RSHIFT = 63
  BINARY_AND = 64
  BINARY_XOR = 65
  BINARY_OR = 66
  INPLACE_POWER = 67
  GET_ITER = 68
  GET_YIELD_FROM_ITER = 69
  STORE_LOCALS = 69
  PRINT_EXPR = 70
  LOAD_BUILD_CLASS = 71
  YIELD_FROM = 72
  GET_AWAITABLE = 73
  INPLACE_LSHIFT = 75
  INPLACE_RSHIFT = 76
  INPLACE_AND = 77
  INPLACE_XOR = 78
  INPLACE_OR = 79
  BREAK_LOOP = 80
  WITH_CLEANUP = 81
  WITH_CLEANUP_START = 81
  WITH_CLEANUP_FINISH = 82
  RETURN_VALUE = 83
  IMPORT_STAR = 84
  SETUP_ANNOTATIONS = 85
  YIELD_VALUE = 86
  POP_BLOCK = 87
  END_FINALLY = 88
  POP_EXCEPT = 89
  STORE_NAME = 90
  DELETE_NAME = 91
  UNPACK_SEQUENCE = 92
  FOR_ITER = 93
  UNPACK_EX = 94
  STORE_ATTR = 95
  DELETE_ATTR = 96
  STORE_GLOBAL = 97
  DELETE_GLOBAL = 98
  LOAD_CONST = 100
  LOAD_NAME = 101
  BUILD_TUPLE = 102
  BUILD_LIST = 103
  BUILD_SET = 104
  BUILD_MAP = 105
  LOAD_ATTR = 106
  COMPARE_OP = 107
  IMPORT_NAME = 108
  IMPORT_FROM = 109
  JUMP_FORWARD = 110
  JUMP_IF_FALSE_OR_POP = 111
  JUMP_IF_TRUE_OR_POP = 112
  JUMP_ABSOLUTE = 113
  POP_JUMP_IF_FALSE = 114
  POP_JUMP_IF_TRUE = 115
  LOAD_GLOBAL = 116
  CONTINUE_LOOP = 119
  SETUP_LOOP = 120
  SETUP_EXCEPT = 121
  SETUP_FINALLY = 122
  LOAD_FAST = 124
  STORE_FAST = 125
  DELETE_FAST = 126
  STORE_ANNOTATION = 127
  RAISE_VARARGS = 130
  CALL_FUNCTION = 131
  MAKE_FUNCTION = 132
  BUILD_SLICE = 133
  MAKE_CLOSURE = 134
  LOAD_CLOSURE = 135
  LOAD_DEREF = 136
  STORE_DEREF = 137
  DELETE_DEREF = 138
  CALL_FUNCTION_VAR = 140
  CALL_FUNCTION_KW = 141
  CALL_FUNCTION_EX = 142
  CALL_FUNCTION_VAR_KW = 142
  SETUP_WITH = 143
  EXTENDED_ARG = 144
  LIST_APPEND = 145
  SET_ADD = 146
  MAP_ADD = 147
  LOAD_CLASSDEREF = 148
  BUILD_LIST_UNPACK = 149
  BUILD_MAP_UNPACK = 150
  BUILD_MAP_UNPACK_WITH_CALL = 151
  BUILD_TUPLE_UNPACK = 152
  BUILD_SET_UNPACK = 153
  SETUP_ASYNC_WITH = 154
  FORMAT_VALUE = 155
  BUILD_CONST_KEY_MAP = 156
  BUILD_STRING = 157
  BUILD_TUPLE_UNPACK_WITH_CALL = 158


# We compute the availability of python3.7 with subprocess, which is slow, so
# the result is cached.
_IS_37_AVAILABLE = None


# pylint: disable=invalid-name
# Use camel-case to match the unittest.skip* methods.
# TODO(rechen): Remove skipUnless37Available once python3.7 is available in all
# of pytype's testing environments.
def skipUnless37Available(f):
  """Skip the test unless Python 3.7 is available."""
  global _IS_37_AVAILABLE
  if _IS_37_AVAILABLE is None:
    try:
      subprocess.call(["python3.7", "-V"])
    except OSError:
      _IS_37_AVAILABLE = False
    else:
      _IS_37_AVAILABLE = True
  return unittest.skipUnless(_IS_37_AVAILABLE, "no python3.7")(f)


def skipIn37(reason):
  """Skip the test in Python 3.7."""
  def decorate(f):
    # See test_base.main for how this attribute is used to skip the test.
    f.__pytype_skip__ = reason
    return f
  return decorate
# pylint: enable=invalid-name
