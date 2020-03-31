"""Tests for handling PYI code."""

from pytype import file_utils
from pytype.tests import test_base


class PYITest(test_base.TargetIndependentTest):
  """Tests for PYI."""

  def testModuleParameter(self):
    """This test that types.ModuleType works."""
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        import types
        def f(x: types.ModuleType = ...) -> None
      """)
      self.Check("""
        import os
        import mod

        mod.f(os)
        """, pythonpath=[d.path])

  def testOptional(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def f(x: int = ...) -> None
      """)
      ty = self.Infer("""\
        import mod
        def f():
          return mod.f()
        def g():
          return mod.f(3)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mod = ...  # type: module
        def f() -> NoneType
        def g() -> NoneType
      """)

  def testSolve(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def f(node: int, *args, **kwargs) -> str
      """)
      ty = self.Infer("""\
        import mod
        def g(x):
          return mod.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mod = ...  # type: module
        def g(x) -> str
      """)

  def testTyping(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        from typing import Any, IO, List, Optional
        def split(s: Optional[int]) -> List[str, ...]: ...
      """)
      ty = self.Infer("""\
        import mod
        def g(x):
          return mod.split(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        mod = ...  # type: module
        def g(x) -> List[str, ...]
      """)

  def testClasses(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        def f(foo, bar) -> Any
        def g() -> NoneType: ...
      """)

  def testIterable(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f(x=...) -> bool: ...
      """)

  def testCallable(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x) -> Any
        def g(x) -> Any
        def h(x) -> Any
      """)

  def testOldStyleClassObjectMatch(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        def f(x) -> Any
        class Foo: pass
      """)
      ty = self.Infer("""
        import foo
        def g():
          return foo.f(foo.Foo())
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def g() -> Any
      """)

  def testIdentity(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f(3)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: int
      """)

  def testImportFunctionTemplate(self):
    with file_utils.Tempdir() as d1:
      d1.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T
      """)
      with file_utils.Tempdir() as d2:
        d2.create_file("bar.pyi", """
          import foo
          f = foo.f
        """)
        ty = self.Infer("""
          import bar
          x = bar.f("")
        """, pythonpath=[d1.path, d2.path])
        self.assertTypesMatchPytd(ty, """
          bar = ...  # type: module
          x = ...  # type: str
        """)

  def testMultipleGetAttr(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      ty, errors = self.InferWithErrors("""\
        from foo import *
        from bar import *  # Nonsense import generates a top-level __getattr__  # import-error[e]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      self.assertErrorRegexes(errors, {"e": r"bar"})

  def testPyiListItem(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        lst = ...  # type: list
        def f(x: int) -> str
      """)
      ty = self.Infer("""
        import a
        x = a.f(a.lst[0])
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: str
      """)

  def testDubiousFunctionReference(self):
    with file_utils.Tempdir() as d:
      # TODO(kramm): pytd.ToType() currently allows this. Should it?
      d.create_file("a.pyi", """
        def DubiousType() -> None
        x = ...  # type: DubiousType
      """)
      ty = self.Infer("""\
        import a
        x = a.x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def x() -> None: ...
      """)

  def testKeywordOnlyArgs(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def foo(x: str, *y: Any, z: complex = ...) -> int: ...
      """)
      ty = self.Infer("""\
        import a
        x = a.foo("foo %d %d", 3, 3)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)

  def testPosArg(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def get_pos(x: T, *args: int, z: int, **kws: int) -> T: ...
      """)
      ty = self.Infer("""
        import a
        v = a.get_pos("foo", 3, 4, z=5)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: str
      """)

  def testKwonlyArg(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def get_kwonly(x: int, *args: int, z: T, **kwargs: int) -> T: ...
      """)
      ty = self.Infer("""
        import a
        v = a.get_kwonly(3, 4, z=5j)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: complex
      """)

  def testStarArgs(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Dict, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        def foo(a: K, *b, c: V, **d) -> Dict[K, V]: ...
      """)
      ty, errors = self.InferWithErrors("""\
        import foo
        a = foo.foo(*tuple(), **dict())
        b = foo.foo(*(1,), **{"c": 3j})
        c = foo.foo(*(1,))  # missing-parameter[e1]
        d = foo.foo(*(), **{"d": 3j})  # missing-parameter[e2]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Dict
        foo = ...  # type: module
        a = ...  # type: dict
        b = ...  # type: Dict[int, complex]
        c = ...  # type: Any
        d = ...  # type: Any
      """)
      self.assertErrorRegexes(errors, {"e1": r"\bc\b", "e2": r"\ba\b"})

  def testUnionWithSuperclass(self):
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def f(x) -> a.A1
      """)

  def testBuiltinsModule(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        import __builtin__
        x = ...  # type: __builtin__.int
      """)
      ty = self.Infer("""
        import a
        x = a.x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)

  def testFrozenSet(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, FrozenSet, Set
        x = ...  # type: FrozenSet[str]
        y = ...  # type: Set[Any]
      """)
      ty = self.Infer("""
        import a
        x = a.x - a.x
        y = a.x - a.y
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import FrozenSet
        a = ...  # type: module
        x = ...  # type: FrozenSet[str]
        y = ...  # type: FrozenSet[str]
      """)

  def testRaises(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(raises): ...
      """)
      self.Check("import foo", pythonpath=[d.path])

  def testTypeVarConflict(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, Sequence
        class A(List[int], Sequence[str]): ...
      """)
      ty, _ = self.InferWithErrors("""\
        import foo  # pyi-error
        x = [] + foo.A()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: Any
        x = ...  # type: list
      """)

  def testSameTypeVarName(self):
    with file_utils.Tempdir() as d:
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
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        v = ...  # type: foo.Foo
      """)

  def testTypeParamInMutation(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        T2 = TypeVar("T2")
        class Bar(Generic[T]):
          def bar(self, x:T2):
            self = Bar[T2]
      """)
      ty = self.Infer("""\
        import foo
        x = foo.Bar()
        x.bar(10)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: foo.Bar[int]
      """)

  def testBadTypeParamInMutation(self):
    with file_utils.Tempdir() as d:
      # T2 is not in scope when used in the mutation in Bar.bar()
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        T2 = TypeVar("T2")
        class Bar(Generic[T]):
          def quux(self, x: T2): ...
          def bar(self):
            self = Bar[T2]
      """)
      # We should get an error at import time rather than at use time here.
      _, errors = self.InferWithErrors("""\
        import foo  # pyi-error[e]
        x = foo.Bar()
        x.bar()
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"T2"})

  def testStarImport(self):
    with file_utils.Tempdir() as d:
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
      self.Check("""
        import bar
        bar.x
        bar.T
        bar.A
        bar.f
        bar.B
      """, pythonpath=[d.path])

  def testStarImportValue(self):
    with file_utils.Tempdir() as d:
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
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        bar = ...  # type: module
        v1 = ...  # type: foo.Foo
        v2 = ...  # type: str
      """)

  def testStarImportGetAttr(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def __getattr__(name) -> ?
      """)
      d.create_file("bar.pyi", """
        from foo import *
      """)
      self.Check("""
        import bar
        bar.rumpelstiltskin
      """, pythonpath=[d.path])

  def testAlias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: Foo): ...
        g = f
        class Foo: ...
      """)
      self.Check("import foo", pythonpath=[d.path])

  def testCustomBinaryOperator(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def __sub__(self, other) -> str: ...
        class Bar(Foo):
          def __rsub__(self, other) -> int: ...
      """)
      self.Check("""
        import foo
        (foo.Foo() - foo.Bar()).real
      """, pythonpath=[d.path])

  def testParameterizedAny(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        x = ...  # type: Any
        y = ...  # type: x[Any]
      """)
      self.Check("""
        import foo
      """, pythonpath=[d.path])

  def testParameterizedExternalAny(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        x = ...  # type: Any
      """)
      d.create_file("bar.pyi", """
        import foo
        from typing import Any
        x = ...  # type: foo.x[Any]
      """)
      self.Check("""
        import bar
      """, pythonpath=[d.path])

  def testParameterizedAlias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        x = ...  # type: Any
      """)
      d.create_file("bar.pyi", """
        import foo
        from typing import Any
        x = foo.x[Any]
      """)
      self.Check("""
        import bar
      """, pythonpath=[d.path])

  def testAnythingConstant(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        Foo = ...  # type: ?
      """)
      d.create_file("bar.pyi", """
        import foo
        def f(x: foo.Foo) -> None: ...
      """)
      self.Check("""
        import bar
        bar.f(42)
      """, pythonpath=[d.path])

  def testAliasStaticMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A:
          @staticmethod
          def t(a: str) -> None: ...
      """)
      ty = self.Infer("""\
        import foo
        ta = foo.A.t
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Callable
        foo = ...  # type: module
        ta = ...  # type: Callable[[str], None]
        """)

  def testAliasConstant(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          const = ...  # type: int
        Const = Foo.const
      """)
      ty = self.Infer("""
        import foo
        Const = foo.Const
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        Const = ...  # type: int
      """)

  def testAliasMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def f(self) -> int: ...
        Func = Foo.f
      """)
      ty = self.Infer("""
        import foo
        Func = foo.Func
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def Func(self) -> int: ...
      """)

  def testAliasAliases(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          a1 = const
          a2 = f
          const = ...  # type: int
          def f(self) -> int: ...
        Const = Foo.a1
        Func = Foo.a2
      """)
      ty = self.Infer("""
        import foo
        Const = foo.Const
        Func = foo.Func
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        Const = ...  # type: int
        def Func(self) -> int: ...
      """)

  def testGenericInheritance(self):
    with file_utils.Tempdir() as d:
      # Inspired by typeshed/stdlib/2/UserString.pyi
      d.create_file("foo.pyi", """
        from typing import Sequence, MutableSequence, TypeVar
        TFoo = TypeVar("TFoo", bound=Foo)
        class Foo(Sequence[Foo]):
          def __getitem__(self: TFoo, i: int) -> TFoo: ...
        class Bar(Foo, MutableSequence[Bar]): ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.Bar()[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        v = ...  # type: foo.Bar
      """)

  def testDotImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", "class A: ...")
      d.create_file("foo/b.pyi", """
        from . import a
        X = a.A
      """)
      ty = self.Infer("""
        from foo import b
        a = b.X()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        b = ...  # type: module
        a = ...  # type: foo.a.A
      """)

  def testDotDotImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", "class A: ...")
      d.create_file("foo/bar/b.pyi", """
        from .. import a
        X = a.A
      """)
      ty = self.Infer("""
        from foo.bar import b
        a = b.X()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        b = ...  # type: module
        a = ...  # type: foo.a.A
      """)

  def testTypingAlias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import typing as _typing
        def f(x: _typing.Tuple[str, str]) -> None: ...
      """)
      self.Check("import foo", pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
