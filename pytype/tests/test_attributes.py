"""Test instance and class attributes."""

from pytype.tests import test_inference


class TestAttributes(test_inference.InferenceTest):
  """Tests for attributes."""

  def testSimpleAttribute(self):
    with self.Infer("""
      class A(object):
        def method1(self):
          self.a = 3
        def method2(self):
          self.a = 3j
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class A:
          a: complex or int
          def method1(self) -> NoneType
          def method2(self) -> NoneType
      """)

  def testOutsideAttributeAccess(self):
    with self.Infer("""
      class A(object):
        pass
      def f1():
        A().a = 3
      def f2():
        A().a = 3j
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class A:
          a: complex or int
        def f1() -> NoneType
        def f2() -> NoneType
      """)

  def testPrivate(self):
    with self.Infer("""
      class C:
        def __init__(self):
          self._x = 3
        def foo(self):
          return self._x
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class C:
          _x: int
          def __init__(self) -> NoneType
          def foo(self) -> int
      """)

  def testPublic(self):
    with self.Infer("""
      class C:
        def __init__(self):
          self.x = 3
        def foo(self):
          return self.x
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class C:
          x: int
          def __init__(self) -> NoneType
          def foo(self) -> int
      """)

  def testCrosswise(self):
    with self.Infer("""
      class A(object):
        def __init__(self):
          if id(self):
            self.b = B()
        def set_on_b(self):
          self.b.x = 3
      class B(object):
        def __init__(self):
          if id(self):
            self.a = A()
        def set_on_a(self):
          self.a.x = 3j
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class A:
          b: B
          x: complex
          def __init__(self) -> NoneType
          def set_on_b(self) -> NoneType
        class B:
          a: A
          x: int
          def __init__(self) -> NoneType
          def set_on_a(self) -> NoneType
      """)


if __name__ == "__main__":
  test_inference.main()
