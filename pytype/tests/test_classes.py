"""Tests for classes."""
import unittest

from pytype.tests import test_inference


class ClassesTest(test_inference.InferenceTest):
  """Tests for classes."""

  @unittest.skip("fails with NoneType exception")
  def testClassDecorator(self):
    with self.Infer("""
      @__any_object__
      class MyClass(object):
        def method(self, response):
          pass
      def f():
        return MyClass()
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        class MyClass(object):
          def method(self, response) -> NoneType
        def f() -> MyClass
      """)

  def testClassName(self):
    with self.Infer("""
      class MyClass(object):
        def __init__(self, name):
          pass
      def f():
        factory = MyClass
        return factory("name")
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
      class MyClass(object):
        def __init__(self, name: str) -> NoneType

      def f() -> MyClass
      """)

  def testInheritFromUnknown(self):
    with self.Infer("""
      class A(__any_object__):
        pass
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class A(?):
        pass
      """)

if __name__ == "__main__":
  test_inference.main()
