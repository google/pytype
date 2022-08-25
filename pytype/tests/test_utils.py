"""Utility class and function for tests."""

import collections
import copy
import dataclasses
import io
import os
import re
import shutil
import sys
import textwrap
import tokenize

from pytype import context
from pytype import load_pytd
from pytype import state as frame_state
from pytype.file_utils import makedirs
from pytype.platform_utils import path_utils
from pytype.platform_utils import tempfile as compatible_tempfile
from pytype.pyc import loadmarshal
from pytype.pyc import opcodes

import unittest


class Tempdir:
  """Context handler for creating temporary directories."""

  def __enter__(self):
    self.path = compatible_tempfile.mkdtemp()
    return self

  def create_directory(self, filename):
    """Create a subdirectory in the temporary directory."""
    path = path_utils.join(self.path, filename)
    makedirs(path)
    return path

  def create_file(self, filename, indented_data=None):
    """Create a file in the temporary directory. Dedents the data if needed."""
    filedir, filename = path_utils.split(filename)
    if filedir:
      self.create_directory(filedir)
    path = path_utils.join(self.path, filedir, filename)
    if isinstance(indented_data, bytes):
      # This is binary data rather than text.
      mode = "wb"
      data = indented_data
    else:
      mode = "w"
      data = textwrap.dedent(indented_data) if indented_data else indented_data
    with open(path, mode) as fi:
      if data:
        fi.write(data)
    return path

  def delete_file(self, filename):
    os.unlink(path_utils.join(self.path, filename))

  def __exit__(self, error_type, value, tb):
    shutil.rmtree(path=self.path)
    return False  # reraise any exceptions

  def __getitem__(self, filename):
    """Get the full path for an entry in this directory."""
    return path_utils.join(self.path, filename)


@dataclasses.dataclass(eq=True, frozen=True)
class FakeCode:
  co_filename: str
  co_name: str


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
    src = f"""
      def f():
        {assignments}
        return {expr}
      f()
    """
    ty = self.Infer(src, deep=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), expected_return)

  def check_binary(self, function_name, op):
    """Check the binary operator."""
    ty = self.Infer(f"""
      class Foo:
        def {function_name}(self, unused_x):
          return 3j
      class Bar:
        pass
      def f():
        return Foo() {op} Bar()
      f()
    """,
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def check_unary(self, function_name, op, ret=None):
    """Check the unary operator."""
    ty = self.Infer(f"""
      class Foo:
        def {function_name}(self):
          return 3j
      def f():
        return {op} Foo()
      f()
    """,
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
    ty = self.Infer(f"""
      class Foo:
        def __{function_name}__(self, x):
          return 3j
      def f():
        x = Foo()
        x {op} None
        return x
      f()
    """,
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)


class InplaceTestMixin:
  """Mixin providing a method to check in-place operators."""

  _HAS_DYNAMIC_ATTRIBUTES = True

  def _check_inplace(self, op, assignments, expected_return):
    """Check the inplace operator."""
    assignments = "; ".join(assignments)
    src = f"""
      def f(x, y):
        {assignments}
        x {op}= y
        return x
      a = f(1, 2)
    """
    ty = self.Infer(src, deep=False)
    self.assertTypeEquals(ty.Lookup("a").type, expected_return)


class TestCollectionsMixin:
  """Mixin providing utils for tests on the collections module."""

  _HAS_DYNAMIC_ATTRIBUTES = True

  def _testCollectionsObject(self, obj, good_arg, bad_arg, error):  # pylint: disable=invalid-name
    result = self.CheckWithErrors(f"""
      import collections
      def f(x: collections.{obj}): ...
      f({good_arg})
      f({bad_arg})  # wrong-arg-types[e]
    """)
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


class RegexMatcher:
  """Match a regex."""

  def __init__(self, regex):
    self.regex = regex

  def match(self, message):
    return re.search(self.regex, message, flags=re.DOTALL)

  def __repr__(self):
    return repr(self.regex)


class SequenceMatcher:
  """Match a sequence of substrings in order."""

  def __init__(self, seq):
    self.seq = seq

  def match(self, message):
    start = 0
    for s in self.seq:
      i = message.find(s, start)
      if i == -1:
        return False
      start = i + len(s)
    return True

  def __repr__(self):
    return repr(self.seq)


class ErrorMatcher:
  """An ErrorLog matcher to help with test assertions.

  Takes the source code as an init argument, and constructs two dictionaries
  holding parsed comment directives.

  Attributes:
    errorlog: The errorlog being matched against
    marks: { mark_name : errors.Error object }
    expected: { line number : sequence of expected error codes and mark names }

  Adds an assertion matcher to match errorlog.errors against a list of expected
  errors of the form [(line number, error code, message regex)].

  See tests/test_base_test.py for usage examples.
  """

  ERROR_RE = re.compile(r"^(?P<code>(\w+-)+\w+)(\[(?P<mark>.+)\])?$")

  def __init__(self, src):
    # errorlog and marks are set by assert_errors_match_expected()
    self.errorlog = None
    self.marks = None
    self.expected = self._parse_comments(src)

  def _fail(self, msg):
    if self.marks:
      self.errorlog.print_to_stderr()
    raise AssertionError(msg)

  def has_error(self):
    return self.errorlog and self.errorlog.has_error()

  def assert_errors_match_expected(self, errorlog):
    """Matches expected errors against the errorlog, populating self.marks."""

    def _format_error(line, code, mark=None):
      formatted = "Line %d: %s" % (line, code)
      if mark:
        formatted += f"[{mark}]"
      return formatted

    self.errorlog = errorlog
    self.marks = {}
    expected = copy.deepcopy(self.expected)

    for error in self.errorlog.unique_sorted_errors():
      errs = expected[error.lineno]
      for i, (code, mark) in enumerate(errs):
        if code == error.name:
          if mark:
            self.marks[mark] = error
          del errs[i]
          break
      else:
        if errs:
          code, mark = errs[0]
          exp = _format_error(error.lineno, code, mark)
          actual = _format_error(error.lineno, error.name)
          self._fail(
              f"Error does not match:\nExpected: {exp}\nActual: {actual}"
          )
        else:
          self._fail(f"Unexpected error:\n{error}")
    leftover_errors = []
    for line in sorted(expected):
      leftover_errors.extend(_format_error(line, code, mark)
                             for code, mark in expected[line])
    if leftover_errors:
      self._fail("Errors not found:\n" + "\n".join(leftover_errors))

  def _assert_error_messages(self, matchers):
    """Assert error messages."""
    assert self.marks is not None
    for mark, error in self.marks.items():
      try:
        matcher = matchers.pop(mark)
      except KeyError:
        self._fail(f"No matcher for mark {mark}")
      if not matcher.match(error.message):
        self._fail("Bad error message for mark %s: expected %r, got %r" %
                   (mark, matcher, error.message))
    if matchers:
      self._fail(f"Marks not found in code: {', '.join(matchers)}")

  def assert_error_regexes(self, expected_regexes):
    matchers = {k: RegexMatcher(v) for k, v in expected_regexes.items()}
    self._assert_error_messages(matchers)

  def assert_error_sequences(self, expected_sequences):
    matchers = {k: SequenceMatcher(v) for k, v in expected_sequences.items()}
    self._assert_error_messages(matchers)

  def _parse_comments(self, src):
    """Parse comments."""
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
              self._fail(f"Mark {mark} already used")
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


def skipOnWin32(reason):
  return unittest.skipIf(sys.platform == "win32", reason)


def make_context(options):
  """Create a minimal context for tests."""
  return context.Context(options=options, loader=load_pytd.Loader(options))

# pylint: enable=invalid-name
