"""Tests for the error format itself."""

import textwrap

from pytype.tests import test_base


class ErrorTest(test_base.BaseTest):
  """Tests for errors."""

  def test_error_format(self):
    _, errors = self.InferWithErrors("""
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

  def test_error_format_with_source(self):
    _, errors = self.InferWithErrors("""
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
    _, errors = self.InferWithErrors("""
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
