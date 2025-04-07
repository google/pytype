"""Tests for the error format itself."""

import textwrap

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy(
    (3, 11), "py versions lower than 3.11 doesn't have column information "
)
class ErrorTest(test_base.BaseTest):
  """Tests for errors."""

  def test_error_format(self):
    errors = self.CheckWithErrors("""
      def f(x):
        y = 42
        y.foobar  # attribute-error[e]
    """)
    message = textwrap.dedent("""\
      dummy_input_file:3:3: \x1b[1m\x1b[31merror\x1b[39m\x1b[0m: in f: No attribute 'foobar' on int [attribute-error]

        y.foobar  # attribute-error[e]
        \x1b[1m\x1b[31m~~~~~~~~\x1b[39m\x1b[0m
    """)
    self.assertDiagnosticMessages(errors, {"e": message})

  def test_error_format_with_no_end_line_late_directive_error(self):
    errors = self.CheckWithErrors("""
      def f() -> bool:
        # pytype: disable=bad-return-type # late-directive[e]
        return 42
    """)
    message = textwrap.dedent("""\
      dummy_input_file:2:1: \x1b[1m\x1b[31merror\x1b[39m\x1b[0m: : bad-return-type disabled from here to the end of the file [late-directive]
        Consider limiting this directive's scope or moving it to the top of the file.

        # pytype: disable=bad-return-type # late-directive[e]\x1b[1m\x1b[31m~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\x1b[39m\x1b[0m
        # pytype: disable=bad-return-type # late-directive[e]
      \x1b[1m\x1b[31m\x1b[39m\x1b[0m
    """)
    self.assertDiagnosticMessages(errors, {"e": message})

  def test_error_format_with_no_end_line_redundant_function_type_comment_error(
      self,
  ):
    errors = self.CheckWithErrors("""
      def f() -> None:
        # type: () -> None  # redundant-function-type-comment[e]
        pass
    """)
    message = textwrap.dedent("""\
      dummy_input_file:2:1: \x1b[1m\x1b[31merror\x1b[39m\x1b[0m: : Function type comments cannot be used with annotations [redundant-function-type-comment]

        # type: () -> None  # redundant-function-type-comment[e]\x1b[1m\x1b[31m~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\x1b[39m\x1b[0m
        # type: () -> None  # redundant-function-type-comment[e]
      \x1b[1m\x1b[31m\x1b[39m\x1b[0m
    """)
    self.assertDiagnosticMessages(errors, {"e": message})

  def test_error_format_with_source(self):
    errors = self.CheckWithErrors("""
        from typing import List
        def foo(args: List[str]) -> None:
          for arg in args:
            print(arg + 3)  # unsupported-operands[e]
    """)
    message = textwrap.dedent("""\
      dummy_input_file:4:11: \x1b[1m\x1b[31merror\x1b[39m\x1b[0m: in foo: unsupported operand type(s) for +: str and int [unsupported-operands]
        Function __add__ on str expects str

          print(arg + 3)  # unsupported-operands[e]
                \x1b[1m\x1b[31m~~~~~~~\x1b[39m\x1b[0m
    """)
    self.assertDiagnosticMessages(errors, {"e": message})

  def test_error_format_with_source_multiple_lines(self):
    errors = self.CheckWithErrors("""
        from typing import List
        def foo(args: List[str]) -> None:
          for arg in args:
            print(arg  # unsupported-operands[e]
              +
            3)
    """)
    message = textwrap.dedent("""\
      dummy_input_file:4:11: \x1b[1m\x1b[31merror\x1b[39m\x1b[0m: in foo: unsupported operand type(s) for +: str and int [unsupported-operands]
        Function __add__ on str expects str

          print(arg  # unsupported-operands[e]
                \x1b[1m\x1b[31m~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\x1b[39m\x1b[0m
            +
      \x1b[1m\x1b[31m~~~~~~~\x1b[39m\x1b[0m
          3)
      \x1b[1m\x1b[31m~~~~~\x1b[39m\x1b[0m
    """)
    self.assertDiagnosticMessages(errors, {"e": message})

  # TODO: b/338455486 - Add a test case for diagnostic missing a filepath
  # information


if __name__ == "__main__":
  test_base.main()
