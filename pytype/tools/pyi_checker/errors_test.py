"""Tests for pyi_checker errors.

These are sanity checks to make sure error messages are correct.
"""

import textwrap

from pytype.tools.pyi_checker import definitions
from pytype.tools.pyi_checker import errors
from pytype.tools.pyi_checker import test_utils as utils
from typed_ast import ast3
import unittest


class ErrorTest(unittest.TestCase):

  def test_missing_type_hint(self):
    src = utils.func_from_source("def test(a, b): return a + b")
    err = errors.MissingTypeHint(src)
    self.assertRegex(
        err.message,
        "No type hint found for function test.")

  def test_extra_type_hint(self):
    src = utils.func_from_source("def test(a, b) -> int: ...")
    err = errors.ExtraTypeHint(src)
    self.assertRegex(
        err.message,
        "Type hint for function test has no corresponding source definition.")

  def test_wrong_type_hint(self):
    src = utils.func_from_source("def test(a, b) -> int: ...")
    hint = utils.class_from_source("class test: ...")
    err = errors.WrongTypeHint(src, hint)
    self.assertRegex(
        err.message,
        r"^Type hint kind does not match source definition.\n.*"
        r"function test.*\n.*class test$")

  def test_wrong_decorators(self):
    src = utils.func_from_source(
        """
        @dec1
        @dec2
        @dec3
        def test(): ...
        """)
    hint = utils.func_from_source(
        """
        @dec1
        @decZ
        def test(): ...
        """)
    err = errors.WrongDecorators(src, hint)
    self.assertRegex(
        err.message,
        r"^Type hint for function test has incorrect decorators.\n"
        r".*Missing.*: dec2, dec3\n.*Extras.*: decZ$")

  def test_wrong_arg_count(self):
    src = utils.func_from_source("def test(a, b, *c, d, e, f, **g): pass")
    hint = utils.func_from_source("def test(a, *c, d, e, f, **g): ...")
    err = errors.WrongArgCount(src, hint)
    self.assertRegex(
        err.message,
        r"^Type hint for function test has the wrong number of arguments.\n"
        r".*Source:\s*def test\(a, b, \.\.\.\)\n"
        r".*Type hint:\s*def test\(a, \.\.\.\)$")

  def test_no_source_arg_count(self):
    src = utils.func_from_source("def test(*c): pass")
    hint = utils.func_from_source("def test(a, b): ...")
    err = errors.WrongArgCount(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has the wrong number of arguments.\n"
        r".*Source:\s*def test\(\.\.\.\)\n"
        r".*Type hint:\s*def test\(a, b\)$")

  def test_no_hint_arg_count(self):
    src = utils.func_from_source("def test(a, b): pass")
    hint = utils.func_from_source("def test(*c): ...")
    err = errors.WrongArgCount(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has the wrong number of arguments.\n"
        r".*Source:\s*def test\(a, b\)\n"
        r".*Type hint:\s*def test\(\.\.\.\)$")

  def test_wrong_kwonly_count(self):
    src = utils.func_from_source("def test(a, b, *c, d, e, f, **g): pass")
    hint = utils.func_from_source("def test(a, b, *c, d, e, f, h, **g): ...")
    err = errors.WrongKwonlyCount(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has the wrong number "
        r"of keyword-only arguments.\n"
        r".*Source:\s*def test\(\.\.\., \*c, d, e, f, \.\.\.\)\n",
        r".*Type hint:\s*def test\(\.\.\., \*c, d, e, f, h, \.\.\.\)$")

  def test_no_source_kwonly_count(self):
    src = utils.func_from_source("def test(): pass")
    hint = utils.func_from_source("def test(*, a, b,): ...")
    err = errors.WrongKwonlyCount(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has the wrong number "
        r"of keyword-only arguments.\n"
        r".*Source:\s*def test\(\)\n"
        r".*Type hint:\s*def test\(\*, a, b\)$")

  def test_no_hint_kwonly_count(self):
    src = utils.func_from_source("def test(*c, d, e, f, **g): pass")
    hint = utils.func_from_source("def test(*c): ...")
    err = errors.WrongKwonlyCount(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has the wrong number "
        r"of keyword-only arguments.\n"
        r".*Source:\s*def test\(\*c, d, e, f, ...\)\n"
        r".*Type hint:\s*def test\(...\)$")

  def test_wrong_arg_name(self):
    src = utils.func_from_source("def test(a, b, e): pass")
    hint = utils.func_from_source("def test(a, b, c): ...")
    err = errors.WrongArgName(src, hint, "c")
    self.assertRegex(
        err.message,
        r"Function test has no argument named 'c'.\n"
        r".*Source:\s*def test\(a, b, e\)\n",
        r".*Type hint:\s*def test\(a, b, c\)\n")

  def test_wrong_kwonly_name(self):
    src = utils.func_from_source("def test(*, d, e, f): pass")
    hint = utils.func_from_source("def test(*, d, c, f): ...")
    err = errors.WrongKwonlyName(src, hint, "c")
    self.assertRegex(
        err.message,
        r"Function test has no keyword-only argument named 'c'.\n"
        r".*Source:\s*def test\(\*, d, e, f\)\n"
        r".*Type hint:\s*def test\(\*, d, c, f\)$")

  def test_no_source_vararg(self):
    src = utils.func_from_source("def test(a, b, **g): pass")
    hint = utils.func_from_source("def test(*a, **g): ...")
    err = errors.WrongVararg(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test should not have vararg '\*a'.")

  def test_no_hint_vararg(self):
    src = utils.func_from_source("def test(*c): pass")
    hint = utils.func_from_source("def test(a, b): ...")
    err = errors.WrongVararg(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test is missing the vararg '\*c'.")

  def test_wrong_vararg_name(self):
    src = utils.func_from_source("def test(a, b, *c, d, e): pass")
    hint = utils.func_from_source("def test(a, b, *z, d, e): ...")
    err = errors.WrongVararg(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has wrong vararg name.\n"
        r".*Source:\s*def test\(\.\.\., \*c, \.\.\.\)\n"
        r".*Type hint:\s*def test\(\.\.\., \*z, \.\.\.\)$")

  def test_no_source_kwarg(self):
    src = utils.func_from_source("def test(): pass")
    hint = utils.func_from_source("def test(**a): ...")
    err = errors.WrongKwarg(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test should not have "
        r"keyword argument '\*\*a'\.")

  def test_no_hint_kwarg(self):
    src = utils.func_from_source("def test(**a): pass")
    hint = utils.func_from_source("def test(): pass")
    err = errors.WrongKwarg(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test is missing keyword argument '\*\*a'\.")

  def test_wrong_kwarg_name(self):
    src = utils.func_from_source("def test(a, b, **e): pass")
    hint = utils.func_from_source("def test(a, b, **c): ...")
    err = errors.WrongKwarg(src, hint)
    self.assertRegex(
        err.message,
        r"Type hint for function test has wrong keyword argument name.\n"
        r".*Source:\s*def test\(\.\.\., \*\*e\)\n"
        r".*Type hint:\s*def test\(\.\.\., \*\*c\)$")


if __name__ == "__main__":
  unittest.main()

