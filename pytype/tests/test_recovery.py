"""Tests for recovering after errors."""

from pytype.tests import test_base


class RecoveryTests(test_base.TargetIndependentTest):
  """Tests for recovering after errors.

  The type inferencer can warn about bad code, but it should never blow up.
  These tests check that we don't faceplant when we encounter difficult code.
  """

  def test_bad_subtract(self):
    ty = self.Infer("""
      def f():
        t = 0.0
        return t - ("bla" - t)
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f() -> Any: ...
    """)

  def test_inherit_from_instance(self):
    ty = self.Infer("""
      class Foo(3):
        pass
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(Any):
        pass
    """)

  def test_name_error(self):
    ty = self.Infer("""
      x = foobar
      class A(x):
        pass
      pow(A(), 2)
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: Any
      class A(Any):
        pass
    """)

  def test_object_attr(self):
    self.assertNoCrash(self.Check, """
      object.bla(int)
    """)

  def test_attr_error(self):
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
      from typing import Any
      class A:
        pass
      x = ...  # type: Any
      class B:
        pass
      y = ...  # type: Any
      class C:
        pass
    """)

  def test_wrong_call(self):
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

  def test_duplicate_identifier(self):
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
        def __init__(self) -> None: ...
    """)

  def test_method_with_unknown_decorator(self):
    self.InferWithErrors("""
      from nowhere import decorator  # import-error
      class Foo(object):
        @decorator
        def f():
          name_error  # name-error
    """, deep=True)

  def test_assert_in_constructor(self):
    self.Check("""
      class Foo(object):
        def __init__(self):
          self._bar = "foo"
          assert False
        def __str__(self):
          return self._bar
    """)

  @test_base.skip("Line 7, in __str__: No attribute '_bar' on Foo'")
  def test_constructor_infinite_loop(self):
    self.Check("""
      class Foo(object):
        def __init__(self):
          self._bar = "foo"
          while True: pass
        def __str__(self):
          return self._bar
    """)

  def test_attribute_access_in_impossible_path(self):
    self.InferWithErrors("""
      x = 3.14 if __random__ else 42
      if isinstance(x, int):
        if isinstance(x, float):
          x.upper  # not reported
          3 in x  # unsupported-operands
    """)

  def test_binary_operator_on_impossible_path(self):
    self.InferWithErrors("""
      x = "" if __random__ else []
      if isinstance(x, list):
        if isinstance(x, str):
          x / x  # unsupported-operands
    """)


test_base.main(globals(), __name__ == "__main__")
