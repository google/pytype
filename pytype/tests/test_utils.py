"""Utility class and function for tests."""

import collections
import io
import itertools
import re
import sys
import tokenize

from pytype import errors
from pytype import state as frame_state
from pytype.pyc import loadmarshal
from pytype.pyc import opcodes

import unittest


FakeCode = collections.namedtuple("FakeCode", "co_filename co_name")


class FakeOpcode:
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


class OperatorsTestMixin:
  """Mixin providing utilities for operators tests."""

  _HAS_DYNAMIC_ATTRIBUTES = True

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
      class Foo:
        def {function_name}(self, unused_x):
          return 3j
      class Bar:
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
      class Foo:
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
      class Foo:
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
      class Foo:
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


class InplaceTestMixin:
  """Mixin providing a method to check in-place operators."""

  _HAS_DYNAMIC_ATTRIBUTES = True

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


class TestCollectionsMixin:
  """Mixin providing utils for tests on the collections module."""

  _HAS_DYNAMIC_ATTRIBUTES = True

  def _testCollectionsObject(self, obj, good_arg, bad_arg, error):  # pylint: disable=invalid-name
    result = self.CheckWithErrors("""
      import collections
      def f(x: collections.{obj}): ...
      f({good_arg})
      f({bad_arg})  # wrong-arg-types[e]
    """.format(obj=obj, good_arg=good_arg, bad_arg=bad_arg))
    self.assertErrorRegexes(result, {"e": error})


class MakeCodeMixin:
  """Mixin providing a method to make a code object from bytecode."""

  _HAS_DYNAMIC_ATTRIBUTES = True

  def make_code(self, int_array, name="testcode"):
    """Utility method for creating CodeType objects."""
    return loadmarshal.CodeType(
        argcount=0, posonlyargcount=0, kwonlyargcount=0, nlocals=2,
        stacksize=2, flags=0, consts=[None, 1, 2], names=[],
        varnames=["x", "y"], filename="", name=name, firstlineno=1,
        lnotab=[], freevars=[], cellvars=[],
        code=bytes(int_array),
        python_version=self.python_version)


class TestErrorLog(errors.ErrorLog):
  """A subclass of ErrorLog that holds extra information for tests.

  Takes the source code as an init argument, and constructs two dictionaries
  holding parsed comment directives.

  Attributes:
    marks: { mark_name : errors.Error object }
    expected: { line number : sequence of expected error codes and mark names }

  Also adds an assertion matcher to match self.errors against a list of expected
  errors of the form [(line number, error code, message regex)].

  See tests/test_base_test.py for usage examples.
  """

  ERROR_RE = re.compile(r"^(?P<code>(\w+-)+\w+)(\[(?P<mark>.+)\])?$")

  def __init__(self, src):
    super().__init__()
    self.marks = None  # set by assert_errors_match_expected()
    self.expected = self._parse_comments(src)

  def _fail(self, msg):
    if self.marks:
      self.print_to_stderr()
    raise AssertionError(msg)

  def assert_errors_match_expected(self):
    expected_errors = itertools.chain.from_iterable(
        [(line, code, mark) for (code, mark) in errors]
        for line, errors in self.expected.items())
    self.marks = {}

    def _format_error(line, code, mark=None):
      formatted = "Line %d: %s" % (line, code)
      if mark:
        formatted += "[%s]" % mark
      return formatted

    for error in self.unique_sorted_errors():
      try:
        line, code, mark = next(expected_errors)
      except StopIteration:
        self._fail("Unexpected error:\n%s" % error)
      if line != error.lineno or code != error.name:
        self._fail("Error does not match:\nExpected: %s\nActual: %s" %
                   (_format_error(line, code, mark),
                    _format_error(error.lineno, error.name)))
      elif mark:
        self.marks[mark] = error
    leftover_errors = [_format_error(*error) for error in expected_errors]
    if leftover_errors:
      self._fail("Errors not found:\n" + "\n".join(leftover_errors))

  def assert_error_regexes(self, expected_regexes):
    if self.marks is None:
      self.assert_errors_match_expected()  # populates self.marks
    for mark, error in self.marks.items():
      try:
        regex = expected_regexes.pop(mark)
      except KeyError:
        self._fail("No regex for mark %s" % mark)
      if not re.search(regex, error.message, flags=re.DOTALL):
        self._fail("Bad error message for mark %s: expected %r, got %r" %
                   (mark, regex, error.message))
    if expected_regexes:
      self._fail("Marks not found in code: %s" % ", ".join(expected_regexes))

  def _parse_comments(self, src):
    src = io.StringIO(src)
    expected = collections.defaultdict(list)
    used_marks = set()
    for tok, s, (line, _), _, _ in tokenize.generate_tokens(src.readline):
      if tok == tokenize.COMMENT:
        for comment in s.split("#"):
          comment = comment.strip()
          match = self.ERROR_RE.match(comment)
          if not match:
            continue
          mark = match.group("mark")
          if mark:
            if mark in used_marks:
              self._fail("Mark %s already used" % mark)
            used_marks.add(mark)
          expected[line].append((match.group("code"), mark))
    return expected


class Py37Opcodes:
  """Define constants for Python 3.7 opcodes.

  Note that while our tests typically target the version that pytype is running
  in, blocks_test and vm_test check disassembled bytecode, which changes from
  version to version, so we fix the test version.
  """

  for k, v in opcodes.python_3_7_mapping.items():
    locals()[v.__name__] = k
  del k, v  # remove from the class namespace  # pylint: disable=undefined-loop-variable


# pylint: disable=invalid-name
# Use camel-case to match the unittest.skip* methods.
def skipIfPy(*versions, reason):
  return unittest.skipIf(sys.version_info[:2] in versions, reason)


def skipUnlessPy(*versions, reason):
  return unittest.skipUnless(sys.version_info[:2] in versions, reason)


def skipBeforePy(version, reason):
  return unittest.skipIf(sys.version_info[:2] < version, reason)


def skipFromPy(version, reason):
  return unittest.skipUnless(sys.version_info[:2] < version, reason)
# pylint: enable=invalid-name
