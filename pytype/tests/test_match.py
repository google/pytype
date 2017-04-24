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
                                      r"\(x: Callable\)")])

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
          (12, "wrong-arg-types", r"Expected.*Callable\[\[str\], str\]"),
          (14, "wrong-arg-types", r"Expected.*Callable\[\[bool\], bool\]"),
          (15, "wrong-arg-types", r"Expected.*" + expected)])


if __name__ == "__main__":
  test_inference.main()
