"""Tests for the analysis phase matcher (match_var_against_type)."""

from pytype import utils
from pytype.tests import test_base


class MatchTest(test_base.TargetPython3BasicTest):
  """Tests for matching types."""

  def testNoArgumentPyTDFunctionAgainstCallable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar() -> bool
      """)
      _, errors = self.InferWithErrors("""\
                from typing import Callable
        import foo

        def f(x: Callable[[], int]): ...
        def g(x: Callable[[], str]): ...

        f(foo.bar)  # ok
        g(foo.bar)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(9, "wrong-arg-types",
                                      r"\(x: Callable\[\[\], str\]\).*"
                                      r"\(x: Callable\[\[\], bool\]\)")])

  def testPyTDFunctionAgainstCallableWithTypeParameters(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f1(x: int) -> int: ...
        def f2(x: int) -> bool: ...
        def f3(x: int) -> str: ...
      """)
      _, errors = self.InferWithErrors("""\
                from typing import Callable, TypeVar
        import foo

        T_plain = TypeVar("T_plain")
        T_constrained = TypeVar("T_constrained", int, bool)
        def f1(x: Callable[[T_plain], T_plain]): ...
        def f2(x: Callable[[T_constrained], T_constrained]): ...

        f1(foo.f1)  # ok
        f1(foo.f2)  # ok
        f1(foo.f3)
        f2(foo.f1)  # ok
        f2(foo.f2)
        f2(foo.f3)
      """, pythonpath=[d.path])
      expected = r"Callable\[\[Union\[bool, int\]\], Union\[bool, int\]\]"
      self.assertErrorLogIs(errors, [
          (12, "wrong-arg-types",
           r"Expected.*Callable\[\[str\], str\].*"
           r"Actual.*Callable\[\[int\], str\]"),
          (14, "wrong-arg-types",
           r"Expected.*Callable\[\[bool\], bool\].*"
           r"Actual.*Callable\[\[int\], bool\]"),
          (15, "wrong-arg-types",
           r"Expected.*" + expected + ".*"
           r"Actual.*Callable\[\[int\], str\]")])

  def testInterpreterFunctionAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
            from typing import Callable
      def f(x: Callable[[bool], int]): ...
      def g1(x: int) -> bool:
        return __any_object__
      def g2(x: str) -> int:
        return __any_object__
      f(g1)  # ok
      f(g2)
    """)
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types",
                                    r"Expected.*Callable\[\[bool\], int\].*"
                                    r"Actual.*Callable\[\[str\], int\]")])

  def testBoundInterpreterFunctionAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
            from typing import Callable

      class A(object):
        def f(self, x: int) -> bool:
          return __any_object__
      unbound = A.f
      bound = A().f

      def f1(x: Callable[[bool], int]): ...
      def f2(x: Callable[[A, bool], int]): ...
      def f3(x: Callable[[bool], str]): ...

      f1(bound)  # ok
      f2(bound)
      f3(bound)
      f1(unbound)
      f2(unbound)  # ok
    """)
    self.assertErrorLogIs(errors, [(15, "wrong-arg-types",
                                    r"Expected.*Callable\[\[A, bool\], int\].*"
                                    r"Actual.*Callable\[\[int\], bool\]"),
                                   (16, "wrong-arg-types",
                                    r"Expected.*Callable\[\[bool\], str\].*"
                                    r"Actual.*Callable\[\[int\], bool\]"),
                                   (17, "wrong-arg-types",
                                    r"Expected.*Callable\[\[bool\], int\].*"
                                    r"Actual.*Callable\[\[Any, int\], bool\]")])

  def testCallableParameters(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Callable, List, TypeVar
        T = TypeVar("T")
        def f1(x: Callable[..., T]) -> List[T]: ...
        def f2(x: Callable[[T], Any]) -> List[T]: ...
      """)
      ty = self.Infer("""\
                from typing import Any, Callable
        import foo

        def g1(): pass
        def g2() -> int: pass
        v1 = foo.f1(g1)
        v2 = foo.f1(g2)

        def g3(x): pass
        def g4(x: int): pass
        w1 = foo.f2(g3)
        w2 = foo.f2(g4)
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, List
        foo = ...  # type: module
        def g1() -> Any: ...
        def g2() -> int: ...
        def g3(x) -> Any: ...
        def g4(x: int) -> Any: ...

        v1 = ...  # type: list
        v2 = ...  # type: List[int]
        w1 = ...  # type: list
        w2 = ...  # type: List[int]
      """)

  def testVariableLengthFunctionAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
            from typing import Any, Callable
      def f(x: Callable[[int], Any]): pass
      def g1(x: int=0): pass
      def g2(x: str=""): pass
      f(g1)  # ok
      f(g2)
    """)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types",
                                    r"Expected.*Callable\[\[int\], Any\].*"
                                    r"Actual.*Callable\[\[str\], Any\]")])

  def testCallableInstanceAgainstCallableWithTypeParameters(self):
    _, errors = self.InferWithErrors("""\
            from typing import Callable, TypeVar
      T = TypeVar("T")
      def f(x: Callable[[T], T]): ...
      def g() -> Callable[[int], str]: return __any_object__
      f(g())
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Expected.*Callable\[\[str\], str\].*"
                                    r"Actual.*Callable\[\[int\], str\]")])

  def testFunctionWithTypeParameterReturnAgainstCallable(self):
    _, errors = self.InferWithErrors("""\
            from typing import Callable, AnyStr, TypeVar
      T = TypeVar("T")
      def f(x: Callable[..., AnyStr]): ...
      def g1(x: AnyStr) -> AnyStr: return x
      def g2(x: T) -> T: return x

      f(g1)  # ok
      f(g2)
    """)
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types")])

  def testUnionInTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable, Iterator, List, TypeVar
        T = TypeVar("T")
        def decorate(func: Callable[..., Iterator[T]]) -> List[T]
      """)
      ty = self.Infer("""
                from typing import Generator, Optional
        import foo
        @foo.decorate
        def f() -> Generator[Optional[str]]:
          yield "hello world"
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Optional
        foo = ...  # type: module
        f = ...  # type: List[Optional[str]]
      """)

  def testAnyStr(self):
    self.Check("""
            from typing import AnyStr, Dict, Tuple
      class Foo(object):
        def bar(self, x: Dict[Tuple[AnyStr], AnyStr]): ...
    """)

  def testFormalType(self):
    _, errors = self.InferWithErrors("""\
            from typing import AnyStr, List, NamedTuple
      def f(x: str):
        pass
      f(AnyStr)
      def g(x: List[str]):
        pass
      g([AnyStr])
      H = NamedTuple("H", [('a', AnyStr)])
    """)
    self.assertErrorLogIs(errors, [
        (5, "invalid-typevar"),
        (8, "invalid-typevar"),
        (9, "invalid-typevar")])

  def testTypeVarWithBound(self):
    _, errors = self.InferWithErrors("""\
            from typing import Callable, TypeVar
      T1 = TypeVar("T1", bound=int)
      T2 = TypeVar("T2")
      def f(x: T1) -> T1:
        return __any_object__
      def g(x: Callable[[T2], T2]) -> None:
        pass
      g(f)  # line 9
    """)
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types",
                                    r"Expected.*T2.*Actual.*T1")])

  def testCallableBaseClass(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable, Union, Type
        def f() -> Union[Callable[[], ...], Type[Exception]]
        def g() -> Union[Type[Exception], Callable[[], ...]]
      """)
      self.Check("""
                from typing import Union
        import foo
        class Foo(foo.f()):
          pass
        class Bar(foo.g()):
          pass
        def f(x: Foo, y: Bar) -> Union[Bar, Foo]:
          return x or y
        f(Foo(), Bar())
      """, pythonpath=[d.path])


class MatchTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for matching types."""

  # Forked into py2 and py3 versions

  def testCallable(self):
    ty = self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator
      tokenize = ...  # type: module
      def f() -> NoneType
      x = ...  # type: Generator[tokenize.TokenInfo, None, None]
    """)

  def testCallableAgainstGeneric(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar, Callable, Generic, Iterable, Iterator
        A = TypeVar("A")
        N = TypeVar("N")
        class Foo(Generic[A]):
          def __init__(self, c: Callable[[], N]):
            self = Foo[N]
        x = ...  # type: Iterator[int]
      """)
      self.Check("""
        import foo
        foo.Foo(foo.x.__next__)
      """, pythonpath=[d.path])

  def testEmpty(self):
    ty = self.Infer("""
      a = []
      b = ["%d" % i for i in a]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      a = ...  # type: List[nothing]
      b = ...  # type: List[str]
    """)

  def testBoundAgainstCallable(self):
    ty = self.Infer("""
      import io
      import tokenize
      x = tokenize.generate_tokens(io.StringIO("").readline)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator
      io = ...  # type: module
      tokenize = ...  # type: module
      x = ...  # type: Generator[tokenize.TokenInfo, None, None]
    """)


if __name__ == "__main__":
  test_base.main()
