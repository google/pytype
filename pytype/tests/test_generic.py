"""Tests for handling GenericType."""

import unittest


from pytype import utils
from pytype.tests import test_inference


class GenericTest(test_inference.InferenceTest):
  """Tests for GenericType."""

  def testBasic(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]): pass
        def f() -> A[int]
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.f()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[int]
      """)

  def testBinop(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]): pass
      """)
      ty = self.Infer("""
        from a import A
        def f():
          return A() + [42]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import List, Type
        A = ...  # type: Type[a.A]
        def f() -> List[int]
      """)

  def testSpecialized(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, TypeVar
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
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def foo() -> a.B
        def bar() -> dict[str, int]
      """)

  def testSpecializedMutation(self):
    with utils.Tempdir() as d1:
      with utils.Tempdir() as d2:
        d1.create_file("a.pyi", """
          from typing import List, TypeVar
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
        """, pythonpath=[d1.path, d2.path], deep=True)
        self.assertTypesMatchPytd(ty, """
          b = ...  # type: module
          def foo() -> b.B
          def bar() -> int or str
        """)

  def testSpecializedPartial(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, TypeVar
        V = TypeVar("V")
        class A(Dict[str, V]): pass
        class B(A[int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.A()
        def bar():
          return foo().keys()
        def baz():
          return a.B()
        def qux():
          return baz().items()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import List, Tuple
        a = ...  # type: module
        def foo() -> a.A[nothing]
        def bar() -> List[str]
        def baz() -> a.B
        def qux() -> List[Tuple[str, int]]
      """)

  def testTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def bar(self) -> T: ...
        class B(A[int]): ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.B().bar()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> int
      """)

  def testTypeParameterRenaming(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        U = TypeVar("U")
        class A(List[U]): pass
        class B(A[int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.A()
        def bar():
          return a.B()[0]
        def baz():
          x = a.B()
          x.extend(["str"])
          return x[0]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def foo() -> a.A[nothing]
        def bar() -> int
        def baz() -> int or str
      """)

  def testTypeParameterRenamingChain(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, Set, TypeVar
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
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> int or float or complex or str
      """)

  def testTypeParameterRenamingConflict1(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Tuple, TypeVar
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        T3 = TypeVar("T3")
        class A(Generic[T1]):
          def f(self) -> T1: ...
        class B(Generic[T1]):
          def g(self) -> T1: ...
        class C(A[T2], B[T3]):
          def __init__(self):
            self := C[int, str]
          def h(self) -> Tuple[T2, T3]
      """)
      ty = self.Infer("""
        import a
        v1 = a.C().f()
        v2 = a.C().g()
        v3 = a.C().h()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Tuple
        a = ...  # type: module
        v1 = ...  # type: Any
        v2 = ...  # type: Any
        v3 = ...  # type: Tuple[Any, Any]
      """)

  def testTypeParameterRenamingConflict2(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        T3 = TypeVar("T3")
        class A(Generic[T1]):
          def f(self) -> T1: ...
        class B(Generic[T2]):
          def g(self) -> T2: ...
        class C(A[T3], B[T3]):
          def __init__(self):
            self := C[str]
      """)
      ty = self.Infer("""
        import a
        v = a.C().f()
        w = a.C().g()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: str
        w = ...  # type: str
      """)

  def testChangeMultiplyRenamedTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        T3 = TypeVar("T3")
        class A(Generic[T1]):
          def f(self):
            self := A[str]
        class B(Generic[T1]): ...
        class C(A[T2], B[T3]):
          def g(self):
            self:= C[int, float]
      """)
      ty = self.Infer("""
        import a
        v = a.C()
        v.f()
        v.g()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: a.C[int, int or float]
      """)

  def testTypeParameterDeep(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        U = TypeVar("U")
        V = TypeVar("V")
        class A(Generic[U]):
          def bar(self) -> U: ...
        class B(A[V], Generic[V]): ...
        def baz() -> B[int]
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.baz().bar()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> int
      """)

  def testTypeParameterImport(self):
    with utils.Tempdir() as d1:
      d1.create_file("a.pyi", """
        T = TypeVar("T")
      """)
      with utils.Tempdir() as d2:
        d2.create_file("b.pyi", """
          from typing import Generic
          from a import T
          class A(Generic[T]):
            def __init__(self, x: T) -> None:
              self := A[int or T]
            def a(self) -> T
        """)
        ty = self.Infer("""
          import b
          def f():
            return b.A("hello world")
          def g():
            return b.A(3.14).a()
        """, pythonpath=[d1.path, d2.path], deep=True)
        self.assertTypesMatchPytd(ty, """
          b = ...  # type: module
          def f() -> b.A[int or str]
          def g() -> int or float
        """)

  def testTypeParameterConflict(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        K = TypeVar("K")
        V = TypeVar("V")
        class MyIterable(Generic[T]): pass
        class MyList(MyIterable[T]): pass
        class MyDict(MyIterable[K], Generic[K, V]): pass
        class Custom(MyDict[K, V], MyList[V]): pass
      """)
      ty = self.Infer("""
        import a
        x = a.Custom()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: a.Custom
      """)

  def testTypeParameterAmbiguous(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List
        T = TypeVar("T")
        class A(Generic[T]): pass
        class B(A[int]): pass
        class C(List[T], B): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.C()
          return x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.C[int]
      """)

  def testUnion(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List
        class A(List[int or str]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()
        def g():
          return f()[0]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A
        def g() -> int or str
      """)

  def testMultipleTemplates(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class MyDict(Generic[K, V]): pass
        class A(MyDict[K, V], List[V]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.extend([42])
          return x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[nothing, int]
      """)

  def testMultipleTemplatesFlipped(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, Generic, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class MyList(Generic[V]):
          def __getitem__(self, x: int) -> V
        class A(MyList[V], Dict[K, V]):
          def a(self) -> K
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.update({"hello": 0})
          return x
        def g():
          return f().a()
        def h():
          return f()[0]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A[str, int]
        def g() -> str
        def h() -> int
      """)

  def testTypeParameterEmpty(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def f(self) -> List[T]
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A().f()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import List
        a = ...  # type: module
        def f() -> List[nothing]
      """)

  @unittest.skip("Needs better GenericType support")
  def testTypeParameterLimits(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr, Generic
        class A(Generic[AnyStr]):
          def f(self) -> AnyStr
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A().f()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> str or unicode
      """)

  def testPreventInfiniteLoopOnTypeParamCollision(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class Foo(List[T]): pass
      """)
      self.assertNoCrash("""
        import a
        def f():
          x = a.Foo()
          x.append(42)
          return x
        g = lambda y: y+1
      """, pythonpath=[d.path])

  def testTemplateConstruction(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, Generic, List, TypeVar
        T = TypeVar("T")
        U = TypeVar("U")
        class A(Dict[int, U], List[T], Generic[T, U]):
          def f(self) -> None:
            self := A[int, str]
          def g(self) -> T
          def h(self) -> U
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.f()
          return x
        def g():
          return f().g()
        def h():
          return f().h()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f() -> a.A[int, str]
        def g() -> Any  # T was made unsolvable by an AliasingDictConflictError
        def h() -> str
      """)

  def testRecursiveContainer(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List
        class A(List[A]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()[0]
        def g():
          return a.A()[0][0]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> a.A
        def g() -> a.A
      """)

  def testPyTDSubclass(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          def __init__(self) -> None:
            self := A[str]
          def f(self) -> T
        class B(A): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.B().f()
        def bar():
          return a.B()[0]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def foo() -> str
        def bar() -> str
      """)

  def testInterpreterSubclass(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          def __init__(self) -> None:
            self := A[str]
          def f(self) -> T
      """)
      ty = self.Infer("""
        import a
        class B(a.A): pass
        def foo():
          return B().f()
        def bar():
          return B()[0]
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        class B(a.A): pass
        def foo() -> str
        def bar() -> str
      """)

  def testInstanceAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T", int, float)
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A().x
        def g():
          return a.A([42]).x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f() -> int or float
        def g() -> int
      """)

  def testInstanceAttributeVisible(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class MyPattern(Generic[T]):
          pattern = ...  # type: T
          def __init__(self, x: T):
            self := MyPattern[T]
      """)
      ty = self.Infer("""
        import a
        RE = a.MyPattern("")
        def f(x):
          if x:
            raise ValueError(RE.pattern)
        def g():
          return RE.pattern
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        RE = ...  # type: a.MyPattern[str]
        def f(x) -> None
        def g() -> str
      """)

  def testInstanceAttributeChange(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        N = TypeVar("N")
        class A(Generic[T]):
          x = ...  # type: T
          def f(self, x: N) -> None:
            self := A[N]
      """)
      ty = self.Infer("""
        import a
        def f():
          inst = a.A()
          inst.f(0)
          inst.x
          inst.f("")
          return inst.x
        def g():
          inst = a.A()
          inst.f(0)
          inst.x = True
          inst.f("")
          return inst.x
        def h():
          inst = a.A()
          inst.f(0)
          x = inst.x
          inst.f("")
          return x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> str
        def g() -> bool
        def h() -> int
      """)

  def testInstanceAttributeInherited(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T", int, float)
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        import a
        class B(a.A): pass
        def f():
          return B().x
        def g():
          return B([42]).x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        class B(a.A):
          x = ...  # type: int or float
        def f() -> int or float
        def g() -> int
      """)

  def testInstanceAttributeSet(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def f(self) -> T
      """)
      ty = self.Infer("""
        import a
        def f():
          inst = a.A()
          inst.x = inst.f()
          return inst.x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f() -> Any
      """)

  def testInstanceAttributeConditional(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        import a
        def f(x):
          inst = a.A([42])
          if x:
            inst.x = 4.2
          return inst.x
        def g(x):
          inst = a.A([42])
          if x:
            inst.x = 4.2
          else:
            return inst.x
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f(x) -> int or float
        def g(x) -> None or int
      """)

  def testInstanceAttributeMethod(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        import a
        def f():
          return abs(a.A([42]).x)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f() -> int
      """)

  @unittest.skip("Why do we get a.A1[object] instead of a.A1[str]?")
  def testUnknown(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, Generic, TypeVar
        T = TypeVar("T")
        class A1(Generic[T]):
          def f(self, x: T) -> T
        class A2(A1[Any]): pass
      """)
      ty = self.Infer("""
        import a
        def f(x):
          return x.f("")
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f(x: a.A1[str] or a.A2) -> Any
      """)

  def testInheritedTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A1(Generic[T]):
          def f(self) -> T
        class A2(A1): pass
      """)
      ty = self.Infer("""
        import a
        def f(x):
          return x.f()
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f(x) -> Any
      """)

  def testAttributeOnAnythingTypeParameter(self):
    """Test that we can access an attribute on "Any"."""
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, List
        class A(List[Any]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()[0].someproperty
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f() -> Any
      """)

  def testMatchAnythingTypeParameter(self):
    """Test that we can match "Any" against a formal function argument."""
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, List
        class A(List[Any]): pass
      """)
      ty = self.Infer("""
        import a
        n = len(a.A()[0])
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        n = ...  # type: int
      """)

  def testRenamedTypeParameterMatch(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Iterable, TypeVar
        Q = TypeVar("Q")
        def f(x: Iterable[Q]) -> Q
      """)
      ty = self.Infer("""
        import a
        x = a.f({True: "false"})
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: bool
      """)

  def testTypeParameterUnion(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class Foo(List[K or V]):
          def __init__(self):
            self := Foo[int, str]
      """)
      ty = self.Infer("""
        import foo
        v = list(foo.Foo())
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        v = ...  # type: list[int or str]
      """)

  def test_mutate_call(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        _T = TypeVar("_T")
        class A(Generic[_T]):
          def to_str(self):
            self := A[str]
          def to_int(self):
            self := A[int]
      """)
      ty = self.Infer("""
        import foo
        a = foo.A()
        a.to_str()
        a.to_int()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        a = ...  # type: foo.A[int]
      """)


if __name__ == "__main__":
  test_inference.main()
