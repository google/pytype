"""Tests for handling PYI code."""

import unittest


from pytype import utils
from pytype.tests import test_inference


class PYITest(test_inference.InferenceTest):
  """Tests for PYI."""

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
      """, deep=True, solve_unknowns=False,
                      extract_locals=True,  # TODO(kramm): Shouldn't need this.
                      pythonpath=[d.path])
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
        from typing import Optional, List, Any, IO
        def split(s: Optional[float]) -> List[str, ...]: ...
      """)
      ty = self.Infer("""\
        import mod
        def g(x):
          return mod.split(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mod = ...  # type: module
        def g(x: NoneType or float) -> List[str, ...]
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
        def __getattr__(name) -> Any
      """)
      ty = self.Infer("""\
        import vague
        x = vague.foo + vague.bar
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
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
      """, deep=False, solve_unknowns=False, extract_locals=True,
                      pythonpath=[d.path])
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
      """, deep=False, solve_unknowns=False, extract_locals=True,
                      pythonpath=[d.path])
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
        a = ...  # type: module
        def f(foo, bar) -> Union[bytearray, str, unicode]: ...
        def g() -> NoneType: ...
      """)

  def testIterable(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(l: Iterable[int]) -> int: ...
      """)
      ty = self.Infer("""\
        import a
        u = a.f([1, 2, 3])
      """, deep=False, pythonpath=[d.path], extract_locals=True)
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
        def f(*args, **kwargs) -> Any: ...
      """)

  def testCallable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
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
        def f(x) -> Any
        class Foo: pass
      """)
      ty = self.Infer("""
        import foo
        def g():
          return foo.f(foo.Foo())
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def g() -> Any
      """)


  @unittest.skip("pytd matching needs to understand inheritance")
  def testClasses(self):
    with utils.Tempdir() as d:
      d.create_file("classes.pytd", """
        class A(object):
          def foo(self) -> A
        class B(A):
          pass
      """)
      with self.Infer("""\
        import classes
        x = classes.B().foo()
      """, deep=False, solve_unknowns=False, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          classes = ...  # type: module
          x = ...  # type: int
        """)

if __name__ == "__main__":
  test_inference.main()
