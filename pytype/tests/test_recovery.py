"""Tests for recovering after errors."""

import unittest


from pytype.tests import test_base


class RecoveryTests(test_base.BaseTest):
  """Tests for recovering after errors.

  The type inferencer can warn about bad code, but it should never blow up.
  These tests check that we don't faceplant when we encounter difficult code.
  """

  def testBadSubtract(self):
    ty = self.Infer("""
      def f():
        t = 0.0
        return t - ("bla" - t)
    """, deep=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      def f() -> ?
    """)

  def testBadCall(self):
    ty = self.Infer("""
      def f():
        return "%s" % chr("foo")
    """, deep=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      def f() -> str
    """)

  def testBadFunction(self):
    ty = self.Infer("""
      import time
      def f():
        return time.unknown_function(3)
      def g():
        return '%s' % f()
    """, deep=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      time = ...  # type: module
      def f() -> ?
      def g() -> str
    """)

  def testInheritFromInstance(self):
    ty = self.Infer("""
      class Foo(3):
        pass
    """, deep=True, report_errors=False)
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
    """, deep=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: ?
      class A(?):
        pass
    """)

  def testObjectAttr(self):
    self.assertNoCrash("""
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
    """, deep=True, report_errors=False)
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
    """, deep=True, report_errors=False)
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        foo = ...  # type: Any
    """)

  def testFunctionWithUnknownDecorator(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from nowhere import decorator
      @decorator
      def f():
        name_error
      @decorator
      def g(x: int) -> None:
        x.upper()
    """, deep=True)
    self.assertErrorLogIs(errors, [
        (2, "import-error"),
        (5, "name-error"),
        (8, "attribute-error"),
    ])

  def testMethodWithUnknownDecorator(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from nowhere import decorator
      class Foo(object):
        @decorator
        def f():
          name_error
    """, deep=True)
    self.assertErrorLogIs(errors, [
        (2, "import-error"),
        (6, "name-error"),
    ])

  def testAssertInConstructor(self):
    self.Check("""\
      from __future__ import google_type_annotations
      class Foo(object):
        def __init__(self):
          self._bar = "foo"
          assert False
        def __str__(self):
          return self._bar
    """)

  @unittest.skip("Constructor loops forever.")
  def testConstructorInfiniteLoop(self):
    self.Check("""\
      from __future__ import google_type_annotations
      class Foo(object):
        def __init__(self):
          self._bar = "foo"
          while True: pass
        def __str__(self):
          return self._bar
    """)

  def testAttributeAccessInImpossiblePath(self):
    _, errors = self.InferAndCheck("""\
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
    _, errors = self.InferAndCheck("""\
      x = "" if __random__ else u""
      if isinstance(x, unicode):
        if isinstance(x, str):
          x / x
    """)
    self.assertErrorLogIs(errors, [
        (4, "unsupported-operands"),
    ])

  def testComplexInit(self):
    """Test that we recover when __init__ triggers a utils.TooComplexError."""
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import AnyStr
      class X(object):
        def __init__(self,
                     literal: int = None,
                     target_index: int = None,
                     register_range_first: int = None,
                     register_range_last: int = None,
                     method_ref: AnyStr = None,
                     field_ref: AnyStr = None,
                     string_ref: AnyStr = None,
                     type_ref: AnyStr = None) -> None:
          pass
        def foo(self, x: other_module.X) -> None:  # line 14
          pass
    """, deep=True)
    self.assertErrorLogIs(errors, [(14, "name-error", r"other_module")])


if __name__ == "__main__":
  test_base.main()
