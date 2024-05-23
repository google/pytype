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

import pycnite.mapping
import pycnite.types

from pytype import config
from pytype import context
from pytype import file_utils
from pytype import load_pytd
from pytype import pretty_printer_base
from pytype import state as frame_state
from pytype import utils
from pytype.file_utils import makedirs
from pytype.platform_utils import path_utils
from pytype.platform_utils import tempfile as compatible_tempfile
from pytype.pytd import slots

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
  filename: str
  name: str


class FakeOpcode:
  """Util class for generating fake Opcode for testing."""

  def __init__(self, filename, line, endline, col, endcol, methodname):
    self.code = FakeCode(filename, methodname)
    self.line = line
    self.endline = endline
    self.col = col
    self.endcol = endcol
    self.name = "FAKE_OPCODE"

  def to_stack(self):
    return [frame_state.SimpleFrame(self)]


def fake_stack(length):
  return [
      frame_state.SimpleFrame(
          FakeOpcode("foo.py", i, i, i, i, "function%d" % i)
      )
      for i in range(length)
  ]


class FakePrettyPrinter(pretty_printer_base.PrettyPrinterBase):
  """Fake pretty printer for constructing an error log."""

  def __init__(self):
    options = config.Options.create()
    super().__init__(make_context(options))

  def print_generic_type(self, t) -> str:
    return ""

  def print_type_of_instance(self, t, instance=None) -> str:
    return ""

  def print_type(self, t, literal=False) -> str:
    return ""

  def print_function_def(self, fn) -> str:
    return ""

  def print_var_type(self, *args) -> str:
    return ""

  def show_variable(self, var) -> str:
    return ""


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
    ty = self.Infer(src)
    self.assertTypesMatchPytd(ty, f"def f() -> {expected_return}: ...")

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
    """)
    self.assertTypesMatchPytd(ty, f"""
      class Foo:
        def {function_name}(self, unused_x) -> complex: ...
      class Bar: ...
      def f() -> complex: ...
    """)

  def check_unary(self, function_name, op, ret=None):
    """Check the unary operator."""
    ty = self.Infer(f"""
      class Foo:
        def {function_name}(self):
          return 3j
      def f():
        return {op} Foo()
      f()
    """)
    self.assertTypesMatchPytd(ty, f"""
      class Foo:
        def {function_name}(self) -> complex: ...
      def f() -> {ret or "complex"}: ...
    """)

  def check_reverse(self, function_name, op):
    """Check the reverse operator."""
    ty = self.Infer(f"""
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
    """)
    self.assertTypesMatchPytd(ty, f"""
      class Foo:
        def __{function_name}__(self, x) -> complex: ...
      class Bar(Foo):
        def __r{function_name}__(self, x) -> str: ...
      def f() -> complex: ...
      def g() -> str: ...
      def h() -> str: ...
      def i() -> complex: ...
    """)

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
    """)
    self.assertTypesMatchPytd(ty, f"""
      class Foo:
        def __{function_name}__(self, x) -> complex: ...
      def f() -> complex: ...
    """)


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
    """
    ty = self.Infer(src)
    self.assertTypesMatchPytd(ty, f"def f(x, y) -> {expected_return}: ...")


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
    return pycnite.types.CodeType38(
        co_argcount=0, co_posonlyargcount=0, co_kwonlyargcount=0, co_nlocals=2,
        co_stacksize=2, co_flags=0, co_consts=[None, 1, 2], co_names=[],
        co_varnames=["x", "y"], co_filename="", co_name=name, co_firstlineno=1,
        co_lnotab=b"", co_freevars=(), co_cellvars=(),
        co_code=bytes(int_array),
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

  ERROR_RE = re.compile(r"^(?P<code>(\w+-)+\w+)(\[(?P<mark>.+)\])?"
                        r"((?P<cmp>([!=]=|[<>]=?))(?P<version>\d+\.\d+))?$")

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
      errs = expected[error.line]
      for i, (code, mark) in enumerate(errs):
        if code == error.name:
          if mark:
            self.marks[mark] = error
          del errs[i]
          break
      else:
        if errs:
          code, mark = errs[0]
          exp = _format_error(error.line, code, mark)
          actual = _format_error(error.line, error.name)
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

  def _assert_diagnostic_messages(self, matchers):
    """Assert error messages."""
    assert self.marks is not None
    for mark, error in self.marks.items():
      try:
        matcher = matchers.pop(mark)
      except KeyError:
        self._fail(f"No matcher for mark {mark}")
      error_as_string = error.as_string()
      if not matcher.match(error_as_string):
        self._fail("Bad error message for mark %s: expected %r, got %r" %
                   (mark, matcher, error_as_string))
    if matchers:
      self._fail(f"Marks not found in code: {', '.join(matchers)}")

  def assert_error_regexes(self, expected_regexes):
    matchers = {k: RegexMatcher(v) for k, v in expected_regexes.items()}
    self._assert_error_messages(matchers)

  def assert_error_sequences(self, expected_sequences):
    matchers = {k: SequenceMatcher(v) for k, v in expected_sequences.items()}
    self._assert_error_messages(matchers)

  def assert_diagnostic_regexes(self, expected_diagnostic_regexes):
    matchers = {
        k: RegexMatcher(v) for k, v in expected_diagnostic_regexes.items()
    }
    self._assert_diagnostic_messages(matchers)

  def _parse_comment(self, comment):
    comment = comment.strip()
    error_match = self.ERROR_RE.fullmatch(comment)
    if not error_match:
      return None
    version_cmp = error_match.group("cmp")
    if version_cmp:
      version = utils.version_from_string(error_match.group("version"))
      actual_version = sys.version_info[:2]
      if not slots.COMPARES[version_cmp](actual_version, version):
        return None
    return error_match.group("code"), error_match.group("mark")

  def _parse_comments(self, src):
    """Parse comments."""
    src = io.StringIO(src)
    expected = collections.defaultdict(list)
    used_marks = set()
    for tok, s, (line, _), _, _ in tokenize.generate_tokens(src.readline):
      if tok != tokenize.COMMENT:
        continue
      for comment in s.split("#"):
        parsed_comment = self._parse_comment(comment)
        if parsed_comment is None:
          continue
        code, mark = parsed_comment
        if mark:
          if mark in used_marks:
            self._fail(f"Mark {mark} already used")
          used_marks.add(mark)
        expected[line].append((code, mark))
    return expected


class Py310Opcodes:
  """Define constants for Python 3.10 opcodes.

  Note that while our tests typically target the version that pytype is running
  in, blocks_test checks disassembled bytecode, which changes from version to
  version, so we fix the test version.
  """

  for k, v in pycnite.mapping.PYTHON_3_10_MAPPING.items():
    locals()[v] = k
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


def test_data_file(filename):
  pytype_dir = path_utils.dirname(path_utils.dirname(path_utils.__file__))
  code = path_utils.join(
      pytype_dir, file_utils.replace_separator("test_data/"), filename)
  with open(code, "r") as f:
    return f.read()


# pylint: enable=invalid-name
