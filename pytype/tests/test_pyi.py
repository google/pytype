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
      """, deep=True, pythonpath=[d.path])
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
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mod = ...  # type: module
        def g(x) -> str
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
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        mod = ...  # type: module
        def g(x) -> List[str, ...]
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
      """, deep=False, pythonpath=[d.path])
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
      """, deep=False, pythonpath=[d.path])
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
      """, deep=False, pythonpath=[d.path])
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
      """, deep=False, pythonpath=[d.path])
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
      """, deep=False, pythonpath=[d.path])
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
      """, deep=True, pythonpath=[d.path])
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
      """, deep=True, pythonpath=[d.path])
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
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def bar() -> Any: ...   # 'Any' because deep=False
        x = ...  # type: NoneType
      """)

  def testHex(self):
    ty = self.Infer("""\
      x = hex(4)
    """, deep=False)
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
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x) -> Any
        def g(x) -> Any
        def h(x) -> Any
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
      """, deep=True, pythonpath=[d.path])
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
      """, deep=True, pythonpath=[d.path])
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
      """, deep=True, pythonpath=[d.path])
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
      """, deep=True, pythonpath=[d.path])
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
        """, pythonpath=[d1.path, d2.path], deep=True)
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
      """, pythonpath=[d.path], deep=True)
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

  def testPosArg(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def get_pos(x: T, *args: int, z: int, **kws: int) -> T: ...
      """)
      ty = self.Infer("""
        import a
        v = a.get_pos("foo", 3, 4, z=5)
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: str
      """)

  def testKwonlyArg(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def get_kwonly(x: int, *args: int, z: T, **kwargs: int) -> T: ...
      """)
      ty = self.Infer("""
        import a
        v = a.get_kwonly(3, 4, z=5j)
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: complex
      """)

  def testVarargs(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_varargs(x: int, *args: T, z: int, **kws: int) -> T: ...
      """)
      ty, errors = self.InferAndCheck("""\
        from typing import Union
        import a
        l1 = None  # type: list[str]
        l2 = None  # type: list[Union[str, complex]]
        v1 = a.get_varargs(1, *l1)
        v2 = a.get_varargs(1, *l2, z=5)
        v3 = a.get_varargs(1, True, 2.0, z=5)
        v4 = a.get_varargs(1, 2j, "foo", z=5)  # bad: conflicting args types
        v5 = a.get_varargs(1, *None)  # bad: None not iterable
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        l1 = ...  # type: list[str]
        l2 = ...  # type: list[str or complex]
        v1 = ...  # type: str
        v2 = ...  # type: str or complex
        v3 = ...  # type: bool or float
        v4 = ...  # type: Any
        v5 = ...  # type: Any
      """)
      msg1 = (r"Expected: \(x, _, _2: complex, \.\.\.\).*"
              r"Actually passed: \(x, _, _2: str, \.\.\.\)")
      msg2 = (r"Expected: \(x, \*args: Iterable, \.\.\.\).*"
              r"Actually passed: \(x, args: None\)")
      self.assertErrorLogIs(errors, [(8, "wrong-arg-types", msg1),
                                     (9, "wrong-arg-types", msg2)])

  def testKwargs(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_kwargs(x: int, *args: int, z: int, **kws: T) -> T: ...
      """)
      ty, errors = self.InferAndCheck("""\
        from typing import Mapping, Union
        import a
        d1 = None  # type: dict[int, int]
        d2 = None  # type: Mapping[str, Union[str, complex]]
        v1 = a.get_kwargs(1, 2, 3, z=5, **d1)  # bad: K must be str
        v2 = a.get_kwargs(1, 2, 3, z=5, **d2)
        v3 = a.get_kwargs(1, 2, 3, z=5, v=0, u=3j)
        # bad: conflicting kwargs types
        v4 = a.get_kwargs(1, 2, 3, z=5, v="", u=3j)
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Mapping
        a = ...  # type: module
        d1 = ...  # type: dict[int, int]
        d2 = ...  # type: Mapping[str, str or complex]
        v1 = ...  # type: Any
        v2 = ...  # type: str or complex
        v3 = ...  # type: int or complex
        v4 = ...  # type: Any
      """)
      msg1 = (r"Expected: \(x, \*args, z, \*\*kws: Mapping\[str, Any\]\).*"
              r"Actually passed: \(x, _, _, z, kws: Dict\[int, int\]\)")
      msg2 = (r"Expected: \(x, _, _, u, v: complex, \.\.\.\).*"
              r"Actually passed: \(x, _, _, u, v: str, \.\.\.\)")
      self.assertErrorLogIs(errors, [(5, "wrong-arg-types", msg1),
                                     (9, "wrong-arg-types", msg2)])

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
      """, pythonpath=[d.path])
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
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f(x) -> a.A1
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
      """, pythonpath=[d.path], deep=True)
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import FrozenSet
        a = ...  # type: module
        x = ...  # type: FrozenSet[str]
        y = ...  # type: FrozenSet[str]
      """)

  def testRaises(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(raises): ...
      """)
      self.assertNoErrors("import foo", pythonpath=[d.path])

  def testTypeVarConflict(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, Sequence
        class A(List[int], Sequence[str]): ...
      """)
      ty, errors = self.InferAndCheck("""\
        import foo
        x = [] + foo.A()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: Any
        x = ...  # type: list
      """)
      self.assertErrorLogIs(errors, [(1, "pyi-error")])

  def testSameTypeVarName(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class MySupportsAbs(Generic[T]): ...
        class MyContextManager(Generic[T]):
          def __enter__(self) -> T: ...
        class Foo(MySupportsAbs[float], MyContextManager[Foo]): ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.Foo().__enter__()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        v = ...  # type: ?
      """)

  def testStarImport(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: int
        T = TypeVar("T")
        class A(object): ...
        def f(x: T) -> T: ...
        B = A
      """)
      d.create_file("bar.pyi", """
        from foo import *
      """)
      self.assertNoErrors("""
        import bar
        bar.x
        bar.T
        bar.A
        bar.f
        bar.B
      """, pythonpath=[d.path])

  def testStarImportValue(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        def f(x: T) -> T
        class Foo(object): pass
      """)
      d.create_file("bar.pyi", """
        from foo import *
      """)
      ty = self.Infer("""
        import bar
        v1 = bar.Foo()
        v2 = bar.f("")
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        bar = ...  # type: module
        v1 = ...  # type: foo.Foo
        v2 = ...  # type: str
      """)

  def testStarImportGetAttr(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def __getattr__(name) -> ?
      """)
      d.create_file("bar.pyi", """
        from foo import *
      """)
      self.assertNoErrors("""
        import bar
        bar.rumpelstiltskin
      """, pythonpath=[d.path])

  def testAlias(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: Foo): ...
        g = f
        class Foo: ...
      """)
      self.assertNoErrors("import foo", pythonpath=[d.path])

  def testCustomBinaryOperator(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def __sub__(self, other) -> str: ...
        class Bar(Foo):
          def __rsub__(self, other) -> int: ...
      """)
      self.assertNoErrors("""
        import foo
        (foo.Foo() - foo.Bar()).real
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_inference.main()
