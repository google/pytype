"""Tests for handling PYI code."""


from pytype import utils
from pytype.tests import test_inference


class PYITest(test_inference.InferenceTest):
  """Tests for PYI."""

  def testModuleParameter(self):
    """This test that types.ModuleType works."""
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        import types
        def f(x: types.ModuleType = ...) -> None
      """)
      self.assertNoErrors("""
        import os
        import mod

        mod.f(os)
        """, pythonpath=[d.path])

  def testOptional(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def f(x: int = ...) -> None
      """)
      ty = self.Infer("""\
        import mod
        def f():
          return mod.f()
        def g():
          return mod.f(3)
      """, deep=True, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mod = ...  # type: module
        def f() -> NoneType
        def g() -> NoneType
      """)

  def testSolve(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def f(node: int, *args, **kwargs) -> str
      """)
      ty = self.Infer("""\
        import mod
        def g(x):
          return mod.f(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mod = ...  # type: module
        def g(x: int) -> str
      """)

  def testTyping(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        from typing import Any, IO, List, Optional
        def split(s: Optional[int]) -> List[str, ...]: ...
      """)
      ty = self.Infer("""\
        import mod
        def g(x):
          return mod.split(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        mod = ...  # type: module
        def g(x: NoneType or int) -> List[str, ...]
      """)

  def testClasses(self):
    with utils.Tempdir() as d:
      d.create_file("classes.pyi", """
        class A(object):
          def foo(self) -> A
        class B(A):
          pass
      """)
      ty = self.Infer("""\
        import classes
        x = classes.B().foo()
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        classes = ...  # type: module
        x = ...  # type: classes.A
      """)

  def testEmptyModule(self):
    with utils.Tempdir() as d:
      d.create_file("vague.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      ty = self.Infer("""\
        import vague
        x = vague.foo + vague.bar
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        vague = ...  # type: module
        x = ...  # type: Any
      """)

  def testDecorators(self):
    with utils.Tempdir() as d:
      d.create_file("decorated.pyi", """
        class A(object):
          @staticmethod
          def u(a, b) -> int: ...
          @classmethod
          def v(cls, a, b) -> int: ...
          def w(self, a, b) -> int: ...
      """)
      ty = self.Infer("""\
        import decorated
        u = decorated.A.u(1, 2)
        v = decorated.A.v(1, 2)
        a = decorated.A()
        x = a.u(1, 2)
        y = a.v(1, 2)
        z = a.w(1, 2)
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        decorated = ...  # type: module
        a = ...  # type: decorated.A
        u = ...  # type: int
        v = ...  # type: int
        x = ...  # type: int
        y = ...  # type: int
        z = ...  # type: int
      """)

  def testPassPyiClassmethod(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          @classmethod
          def v(cls) -> float: ...
          def w(self, x: classmethod) -> int: ...
      """)
      ty = self.Infer("""\
        import a
        u = a.A().w(a.A.v)
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        u = ...  # type: int
      """)

  def testOptionalParameters(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def parse(source, filename = ..., mode = ..., *args, **kwargs) -> int: ...
      """)
      ty = self.Infer("""\
        import a
        u = a.parse("True")
      """, deep=False, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        u = ...  # type: int
      """)

  def testOptimize(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class Bar(dict[?, int]): ...
      """)
      ty = self.Infer("""\
      import a
      def f(foo, bar):
        return __any_object__[1]
      def g():
        out = f('foo', 'bar')
        out = out.split()
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f(foo, bar) -> Any
        def g() -> NoneType: ...
      """)

  def testIterable(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Iterable
        def f(l: Iterable[int]) -> int: ...
      """)
      ty = self.Infer("""\
        import a
        u = a.f([1, 2, 3])
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        u = ...  # type: int
      """)

  def testObject(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def make_object() -> object
      """)
      ty = self.Infer("""\
        import a
        def f(x=None):
          x = a.make_object()
          z = x - __any_object__  # type: ignore
          z + __any_object__
          return True
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f(x=...) -> bool: ...
      """)

  def testCallable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        from typing import Callable
        def process_function(func: Callable[..., Any]) -> None: ...
      """)
      ty = self.Infer("""\
        import foo
        def bar():
          pass
        x = foo.process_function(bar)
      """, deep=False, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def bar() -> Any: ...   # 'Any' because deep=False
        x = ...  # type: NoneType
      """)

  def testHex(self):
    ty = self.Infer("""\
      x = hex(4)
    """, deep=False, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: str
    """)

  def testBaseClass(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        S = TypeVar('S')
        T = TypeVar('T')
        class A(Generic[S]):
          def bar(self, s: S) -> S: ...
        class B(Generic[T], A[T]): ...
        class C(A[int]): ...
        class D(object):
          def baz(self) -> int
      """)
      ty = self.Infer("""\
        import foo
        def f(x):
          return x.bar("foo")
        def g(x):
          return x.bar(3)
        def h(x):
          return x.baz()
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        foo = ...  # type: module
        def f(x: Union[foo.A[str], foo.B[str]]) -> str
        def g(x: Union[foo.A[int], foo.B[int], foo.C]) -> int
        def h(x: foo.D) -> int
      """)

  def testAnonymousProperty(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo:
          x = ...  # type: property
      """)
      ty = self.Infer("""\
        import foo
        x = foo.Foo().x
        x.bar()
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: ?
      """)

  def testOldStyleClassObjectMatch(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        def f(x) -> Any
        class Foo: pass
      """)
      ty = self.Infer("""
        import foo
        def g():
          return foo.f(foo.Foo())
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def g() -> Any
      """)

  def testBytes(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f() -> bytes
      """)
      ty = self.Infer("""
        import foo
        x = foo.f()
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: str
      """)

  def testIdentity(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f(3)
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: int
      """)

  def testImportFunctionTemplate(self):
    with utils.Tempdir() as d1:
      d1.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T
      """)
      with utils.Tempdir() as d2:
        d2.create_file("bar.pyi", """
          import foo
          f = foo.f
        """)
        ty = self.Infer("""
          import bar
          x = bar.f("")
        """, pythonpath=[d1.path, d2.path], deep=True, solve_unknowns=True)
        self.assertTypesMatchPytd(ty, """
          bar = ...  # type: module
          x = ...  # type: str
        """)

  def testMultipleGetAttr(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      ty, errors = self.InferAndCheck("""
        from foo import *
        from bar import *  # Nonsense import generates a top-level __getattr__
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      self.assertErrorLogIs(errors, [(3, "import-error", r"bar")])

  def testPyiListItem(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        lst = ...  # type: list
        def f(x: int) -> str
      """)
      ty = self.Infer("""
        import a
        x = a.f(a.lst[0])
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: str
      """)

  def testSketchyFunctionReference(self):
    with utils.Tempdir() as d:
      # TODO(kramm): visitors._ToType() currently allows this. Should it?
      d.create_file("a.pyi", """
        def SketchyType() -> None
        x = ...  # type: SketchyType
      """)
      ty = self.Infer("""\
        import a
        x = a.x
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def x() -> None: ...
      """)

  def testKeywordOnlyArgs(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def foo(x: str, *y: Any, z: complex = ...) -> int: ...
      """)
      ty = self.Infer("""\
        import a
        x = a.foo("foo %d %d", 3, 3)
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)

  def testSignature(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_pos(x: T, *args: int, z: int, **kws: int) -> T: ...
        def get_kwonly(x: int, *args: int, z: T, **kws: int) -> T: ...
        def get_varargs(x: int, *args: T, z: int, **kws: int) -> T: ...
        def get_kwargs(x: int, *args: int, z: int, **kws: T) -> T: ...
      """)
      ty = self.Infer("""\
        import a
        k = a.get_pos("foo", 3, 4, z=5)
        l = a.get_kwonly(3, 4, z=5j)
        m = a.get_varargs(1, *[1j, "foo"], z=3)
        n = a.get_kwargs(1, **dict())
        o = a.get_varargs(1, 2j, "foo", z=5)
        p = a.get_kwargs(1, 2, 3, z=5, u=3j)
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        k = ...  # type: str
        l = ...  # type: complex
        # TODO(kramm): Fix call_function_from_stack. The below should be:
        # m = ...  # type: Union[complex, str]
        # n = ...  # type: complex
        # o = ...  # type: Union[complex, str]
        # p = ...  # type: complex
        m = ...  # type: Any
        n = ...  # type: Any
        o = ...  # type: Any
        p = ...  # type: Any
      """)

  def testStarArgs(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Dict, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        def foo(a: K, *b, c: V, **d) -> Dict[K, V]: ...
      """)
      ty, errors = self.InferAndCheck("""\
        import foo
        a = foo.foo(*tuple(), **dict())
        b = foo.foo(*(1,), **{"c": 3j})
        c = foo.foo(*(1,))
        d = foo.foo(*(), **{"d": 3j})
      """, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Dict
        foo = ...  # type: module
        a = ...  # type: dict
        b = ...  # type: Dict[int, complex]
        c = ...  # type: Any
        d = ...  # type: Any
      """)
      self.assertErrorLogIs(errors, [
          (4, "missing-parameter", r"\bc\b"),
          (5, "missing-parameter", r"\ba\b"),
      ])

  def testUnionWithSuperclass(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A1(): pass
        class A2(A1): pass
        class A3(A2): pass
      """)
      ty = self.Infer("""
        import a
        def f(x):
          # Constrain the type of x so it doesn't pull everything into our pytd
          x = x + 16
          if x:
            return a.A1()
          else:
            return a.A3()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f(x: complex or float or int) -> a.A1
      """)

  def testBuiltinsModule(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        import __builtin__
        x = ...  # type: __builtin__.int
      """)
      ty = self.Infer("""
        import a
        x = a.x
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)

  def testFrozenSet(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, FrozenSet, Set
        x = ...  # type: FrozenSet[str]
        y = ...  # type: Set[Any]
      """)
      ty = self.Infer("""
        import a
        x = a.x - a.x
        y = a.x - a.y
      """, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import FrozenSet
        a = ...  # type: module
        x = ...  # type: FrozenSet[str]
        y = ...  # type: FrozenSet[str]
      """)


if __name__ == "__main__":
  test_inference.main()
