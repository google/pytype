"""Tests for classes, MROs, inheritance etc."""

from pytype.tests import test_base


class InheritanceTest(test_base.BaseTest):
  """Tests for class inheritance."""

  @test_base.skip("needs (re-)analyzing methods on subclasses")
  def test_subclass_attributes(self):
    ty = self.Infer("""
      class Base:
        def get_lineno(self):
          return self.lineno
      class Leaf(Base):
        lineno = 0
    """, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      class Base:
        pass
      class Leaf(Base):
        lineno: int
        def get_lineno(self) -> int: ...
    """)

  def test_class_attributes(self):
    ty = self.Infer("""
      class A:
        pass
      class B(A):
        pass
      A.x = 3
      A.y = 3
      B.x = "foo"
      def ax():
        return A.x
      def bx():
        return B.x
      def ay():
        return A.y
      def by():
        return A.y
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
       x: int
       y: int
      class B(A):
        x: str
      def ax() -> int: ...
      def bx() -> str: ...
      def ay() -> int: ...
      def by() -> int: ...
    """)

  def test_multiple_inheritance(self):
    ty = self.Infer("""
      class A:
        x = 1
      class B(A):
        y = 4
      class C(A):
        y = "str"
        z = 3j
      class D(B, C):
        pass
      def x():
        return D.x
      def y():
        return D.y
      def z():
        return D.z
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x: int
      class B(A):
        y: int
      class C(A):
        y: str
        z: complex
      class D(B, C): ...
      def x() -> int: ...
      def y() -> int: ...
      def z() -> complex: ...
    """)

  def test_inherit_from_builtins(self):
    ty = self.Infer("""
      class MyDict(dict):
        def __init__(self):
          dict.__setitem__(self, "abc", "foo")

      def f():
        return MyDict()
      f()
    """)
    self.assertTypesMatchPytd(ty, """
      class MyDict(dict):
        def __init__(self) -> None: ...
      def f() -> MyDict: ...
    """)

  def test_inherit_methods_from_object(self):
    # Test that even in the presence of multi-level inheritance,
    # we can still see attributes from "object".
    ty = self.Infer("""
      class A:
        pass
      class B(A):
        pass
      def f():
        return A().__sizeof__()
      def g():
        return B().__sizeof__()
      def h():
        return "bla".__sizeof__()
      f(); g(); h()
    """)
    self.assertTypesMatchPytd(ty, """
      class A: ...
      class B(A): ...
      def f() -> int: ...
      def g() -> int: ...
      def h() -> int: ...
    """)

  def test_mro(self):
    ty = self.Infer("""
      class A:
        def a(self):
          return 1
      class B(A):
        def b(self):
          return 1.0
      class C(A):
        def b(self):
          # ignored in D, B.b has precedence
          return "foo"
      class D(B, C):
        pass
      def f():
        return A().a()
      def g():
        return B().b()
      def h():
        return C().b()
      def i():
        return D().b()
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        def a(self) -> int: ...
      class B(A):
        def b(self) -> float: ...
      class C(A):
        def b(self) -> str: ...
      class D(B, C): ...
      def f() -> int: ...
      def g() -> float: ...
      def h() -> str: ...
      def i() -> float: ...
    """)

  def test_ambiguous_base_class(self):
    self.Check("""
      class A:
        pass
      class B(A):
        pass
      class Foo(A or B):
        pass
    """)


if __name__ == "__main__":
  test_base.main()
