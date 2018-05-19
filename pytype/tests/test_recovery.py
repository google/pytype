"""Tests for recovering after errors."""

import unittest

from pytype.tests import test_base


class RecoveryTests(test_base.TargetIndependentTest):
  """Tests for recovering after errors.

  The type inferencer can warn about bad code, but it should never blow up.
  These tests check that we don't faceplant when we encounter difficult code.
  """

  def testBadSubtract(self):
    ty = self.Infer("""
      def f():
        t = 0.0
        return t - ("bla" - t)
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      def f() -> ?
    """)

  def testInheritFromInstance(self):
    ty = self.Infer("""
      class Foo(3):
        pass
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(?):
        pass
    """)

  def testNameError(self):
    ty = self.Infer("""
      x = foobar
      class A(x):
        pass
      pow(A(), 2)
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: ?
      class A(?):
        pass
    """)

  def testObjectAttr(self):
    self.assertNoCrash(self.Check, """
      object.bla(int)
    """)

  def testAttrError(self):
    ty = self.Infer("""
      class A:
        pass
      x = A.x
      class B:
        pass
      y = "foo".foo()
      object.bar(int)
      class C:
        pass
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      class A:
        pass
      x = ...  # type: ?
      class B:
        pass
      y = ...  # type: ?
      class C:
        pass
    """)

  def testWrongCall(self):
    ty = self.Infer("""
      def f():
        pass
      f("foo")
      x = 3
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      def f() -> None: ...
      x = ...  # type: int
    """)

  def testDuplicateIdentifier(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.foo = 3
        def foo(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        foo = ...  # type: Any
    """)

  def testMethodWithUnknownDecorator(self):
    _, errors = self.InferWithErrors("""\
      from nowhere import decorator
      class Foo(object):
        @decorator
        def f():
          name_error
    """, deep=True)
    self.assertErrorLogIs(errors, [
        (1, "import-error"),
        (5, "name-error"),
    ])

  def testAssertInConstructor(self):
    self.Check("""\
      class Foo(object):
        def __init__(self):
          self._bar = "foo"
          assert False
        def __str__(self):
          return self._bar
    """)

  @unittest.skip("Line 7, in __str__: No attribute '_bar' on Foo'")
  def testConstructorInfiniteLoop(self):
    self.Check("""\
      class Foo(object):
        def __init__(self):
          self._bar = "foo"
          while True: pass
        def __str__(self):
          return self._bar
    """)

  def testAttributeAccessInImpossiblePath(self):
    _, errors = self.InferWithErrors("""\
      x = 3.14 if __random__ else 42
      if isinstance(x, int):
        if isinstance(x, float):
          x.upper  # not reported
          3 in x
    """)
    self.assertErrorLogIs(errors, [
        (5, "unsupported-operands"),
    ])

  def testBinaryOperatorOnImpossiblePath(self):
    _, errors = self.InferWithErrors("""\
      x = "" if __random__ else []
      if isinstance(x, list):
        if isinstance(x, str):
          x / x
    """)
    self.assertErrorLogIs(errors, [
        (4, "unsupported-operands"),
    ])


test_base.main(globals(), __name__ == "__main__")
