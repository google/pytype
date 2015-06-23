"""Tests for classes."""

from pytype.tests import test_inference


class ClassesTest(test_inference.InferenceTest):
  """Tests for classes."""

  def testClassDecorator(self):
    with self.Infer("""
      @__any_object__
      class MyClass(object):
        def method(self, response):
          pass
      def f():
        return MyClass()
    """, deep=True, solve_unknowns=True, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        MyClass: function  # "function" because it gets called in f()
        def f() -> ?
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

  def testInheritFromUnknownAndCall(self):
    with self.Infer("""
      x = __any_object__
      class A(x):
        def __init__(self):
          x.__init__(self)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      x: ?
      class A(?):
        def __init__(self) -> NoneType
      """)

  def testInheritFromUnknownAndSetAttr(self):
    with self.Infer("""
      class Foo(__any_object__):
        def __init__(self):
          setattr(self, "test", True)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Foo(?):
        def __init__(self) -> NoneType
      """)

  def testClassMethod(self):
    with self.Infer("""
      module = __any_object__
      class Foo(object):
        @classmethod
        def bar(cls):
          module.bar("", '%Y-%m-%d')
      def f():
        return Foo.bar()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      module: ?
      def f() -> NoneType
      class Foo:
        # TODO(kramm): pytd needs better syntax for classmethods
        bar: classmethod
      """)


if __name__ == "__main__":
  test_inference.main()
