"""Tests for handling GenericType."""

import unittest


from pytype import utils
from pytype.tests import test_inference


class GenericTest(test_inference.InferenceTest):
  """Tests for GenericType."""

  def testBasic(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        class A(List[T]): pass
        def f() -> A[int]
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.f()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[int]
      """)

  def testBinop(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        class A(List[T]): pass
      """)
      ty = self.Infer("""
        from a import A
        def f():
          return A() + [42]
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        A = ...  # type: type
        def f() -> List[int]
      """)

  def testSpecialized(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Dict[K, V]): pass
        class B(A[str, int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.B()
        def bar():
          x = foo()
          return {x.keys()[0]: x.values()[0]}
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def foo() -> a.B[str, int]
        def bar() -> dict[str, int]
      """)

  def testSpecializedMutation(self):
    with utils.Tempdir() as d1:
      with utils.Tempdir() as d2:
        d1.create_file("a.pyi", """
          T = TypeVar("T")
          class A(List[T]): pass
        """)
        d2.create_file("b.pyi", """
          import a
          class B(a.A[int]): pass
        """)
        ty = self.Infer("""
          import b
          def foo():
            x = b.B()
            x.extend(["str"])
            return x
          def bar():
            return foo()[0]
        """, pythonpath=[d1.path, d2.path], deep=True, solve_unknowns=True)
        self.assertTypesMatchPytd(ty, """
          b = ...  # type: module
          def foo() -> b.B[int or str]
          def bar() -> int or str
        """)

  def testTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class A(Generic[T]):
          def bar(self) -> T: ...
        class B(A[int]): ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.B().bar()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> int
      """)

  def testTypeParameterRenaming(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        U = TypeVar("U")
        class A(List[U]): pass
        class B(A[int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.A()
        def bar():
          return a.B()
        def baz():
          x = bar()
          x.extend(["str"])
          return x
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def foo() -> a.A[nothing]
        def bar() -> a.B[int]
        def baz() -> a.B[int or str]
      """)

  def testTypeParameterRenamingChain(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        A = TypeVar("A")
        B = TypeVar("B")
        class Foo(List[A]):
          def foo(self) -> None:
            self := Foo[A or complex]
        class Bar(Foo[B], Set[B]):
          def bar(self) -> B
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.Bar([42])
          x.foo()
          x.extend(["str"])
          x.add(float(3))
          return x.bar()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> int or float or complex or str
      """)

  def testTypeParameterDeep(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        U = TypeVar("U")
        V = TypeVar("V")
        class A(Generic[U]):
          def bar(self) -> U: ...
        class B(Generic[V], A[V]): ...
        def baz() -> B[int]
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.baz().bar()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> int
      """)

  @unittest.skip("Needs better GenericType support")
  def testUnion(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(List[int or str]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[int or str]
      """)

  @unittest.skip("Needs better GenericType support")
  def testMultipleTemplates(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Dict[K, int], Dict[str, V]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[str, int]
      """)

  @unittest.skip("Needs better GenericType support")
  def testMultipleTemplatesDifferent(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Dict[K, V], List[V]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.extend([42])
          return x
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[nothing, int]
      """)


if __name__ == "__main__":
  test_inference.main()
