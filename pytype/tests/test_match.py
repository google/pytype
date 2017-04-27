"""Tests for the analysis phase matcher (match_var_against_type)."""


from pytype import utils
from pytype.tests import test_inference


class MatchTest(test_inference.InferenceTest):
  """Tests for matching types."""

  def testCallable(self):
    ty = self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator, Tuple
      tokenize = ...  # type: module
      def f() -> NoneType
      x = ...  # type: Generator[Tuple[int, str, Tuple[int, int], Tuple[int, int], str], None, None]
    """)

  def testBoundAgainstCallable(self):
    ty = self.Infer("""
      import tokenize
      import StringIO
      x = tokenize.generate_tokens(StringIO.StringIO("").readline)
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator, Tuple
      tokenize = ...  # type: module
      StringIO = ...  # type: module
      x = ...  # type: Generator[Tuple[int, str, Tuple[int, int], Tuple[int, int], str], None, None]
    """)

  def testTypeAgainstCallable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable
        def f(x: Callable) -> str
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.f(int)
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> str
      """)

  def testMatchUnknownAgainstContainer(self):
    ty = self.Infer("""
      a = {1}
      def f(x):
        return a & x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Set
      a = ...  # type: Set[int]

      def f(x: Iterable) -> Set[int]: ...
    """)

  def testMatchStatic(self):
    ty = self.Infer("""
      s = {1}
      def f(x):
        # set.intersection is a static method:
        return s.intersection(x)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Set
      s = ...  # type: Set[int]

      def f(x) -> set: ...
    """)

  def testGenericHierarchy(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Iterable
        def f(x: Iterable[str]) -> str
      """)
      ty = self.Infer("""
        import a
        x = a.f(["a", "b", "c"])
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: str
      """)

  def testEmpty(self):
    ty = self.Infer("""
      a = []
      b = ["%d" % i for i in a]
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      a = ...  # type: List[nothing]
      b = ...  # type: List[str]
      i = ...  # type: Any
    """)

  def testGeneric(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Iterable
        K = TypeVar("K")
        V = TypeVar("V")
        Q = TypeVar("Q")
        class A(Iterable[V], Generic[K, V]): ...
        class B(A[K, V]):
          def __init__(self):
            self := B[bool, str]
        def f(x: Iterable[Q]) -> Q
      """)
      ty = self.Infer("""
        import a
        x = a.f(a.B())
      """, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: str
      """)

  def testMatchIdentityFunction(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T: ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.f(__any_object__)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        v = ...  # type: Any
      """)

  def testNoArgumentPyTDFunctionAgainstCallable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar() -> bool
      """)
      _, errors = self.InferAndCheck("""\
        from __future__ import google_type_annotations
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
      _, errors = self.InferAndCheck("""\
        from __future__ import google_type_annotations
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
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
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
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
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
        from __future__ import google_type_annotations
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
      """, pythonpath=[d.path])
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
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
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
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Callable, TypeVar
      T = TypeVar("T")
      def f(x: Callable[[T], T]): ...
      def g() -> Callable[[int], str]: return __any_object__
      f(g())
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Expected.*Callable\[\[str\], str\].*"
                                    r"Actual.*Callable\[\[int\], str\]")])

  def testFunctionWithTypeParameterArgAgainstCallable(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Any, AnyStr, Callable, TypeVar
      T = TypeVar("T")
      MyAnyStr = TypeVar("MyAnyStr", unicode, str)
      def f(x: Callable[[AnyStr], Any]): ...
      def g1(x: AnyStr) -> AnyStr: return x
      def g2(x: T) -> T: return x
      def g3(x: MyAnyStr) -> MyAnyStr: return x

      f(g1)  # ok: same parameter
      f(g2)
      f(g3)  # ok: constraints match
    """)
    self.assertErrorLogIs(errors, [(11, "wrong-arg-types")])

  def testFunctionWithTypeParameterReturnAgainstCallable(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
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
        from __future__ import google_type_annotations
        from typing import Generator, Optional
        import foo
        @foo.decorate
        def f() -> Generator[Optional[str]]:
          yield "hello world"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Optional
        foo = ...  # type: module
        f = ...  # type: List[Optional[str]]
      """)


if __name__ == "__main__":
  test_inference.main()
