"""Tests of __builtin__.tuple."""

from pytype import utils
from pytype.tests import test_base


class TupleTest(test_base.TargetPython3BasicTest):
  """Tests for __builtin__.tuple."""

  def testUnpackInlineTuple(self):
    ty = self.Infer("""\
            from typing import Tuple
      def f(x: Tuple[str, int]):
        return x
      v1, v2 = f(__any_object__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      def f(x: Tuple[str, int]) -> Tuple[str, int]: ...
      v1 = ...  # type: str
      v2 = ...  # type: int
    """)

  def testUnpackTupleOrTuple(self):
    self.Check("""
            def f():
        if __random__:
          return (False, 'foo')
        else:
          return (False, 'foo')
      def g() -> str:
        a, b = f()
        return b
    """)

  def testUnpackTupleOrList(self):
    self.Check("""
            def f():
        if __random__:
          return (False, 'foo')
        else:
          return ['foo', 'bar']
      def g() -> str:
        a, b = f()
        return b
    """)

  def testUnpackAmbiguousTuple(self):
    self.Check("""
            def f() -> tuple:
        return __any_object__
      a, b = f()
    """)

  def testTuplePrinting(self):
    _, errors = self.InferWithErrors("""\
            from typing import Tuple
      def f(x: Tuple[str, ...]):
        pass
      def g(y: Tuple[str]):
        pass
      f((42,))
      f(tuple([42]))
      f(("", ""))  # okay
      g((42,))
      g(("", ""))
      g(("",))  # okay
      g(tuple([""]))  # okay
    """)
    x = r"Tuple\[str, \.\.\.\]"
    y = r"Tuple\[str\]"
    tuple_int = r"Tuple\[int\]"
    tuple_ints = r"Tuple\[int, \.\.\.\]"
    tuple_str_str = r"Tuple\[str, str\]"
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types",
                                    r"%s.*%s" % (x, tuple_int)),
                                   (8, "wrong-arg-types",
                                    r"%s.*%s" % (x, tuple_ints)),
                                   (10, "wrong-arg-types",
                                    r"%s.*%s" % (y, tuple_int)),
                                   (11, "wrong-arg-types",
                                    r"%s.*%s" % (y, tuple_str_str))
                                  ])

  def testInlineTuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class A(Tuple[int, str]): ...
      """)
      self.Check("""
                from typing import Tuple, Type
        import foo
        def f(x: Type[Tuple[int, str]]):
          pass
        def g(x: Tuple[int, str]):
          pass
        f(type((1, "")))
        g((1, ""))
        g(foo.A())
      """, pythonpath=[d.path])

  def testInlineTupleError(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class A(Tuple[str, int]): ...
      """)
      _, errors = self.InferWithErrors("""\
                from typing import Tuple, Type
        import foo
        def f(x: Type[Tuple[int, str]]):
          pass
        def g(x: Tuple[int, str]):
          pass
        f(type(("", 1)))
        g(("", 1))
        g(foo.A())
      """, pythonpath=[d.path])
      expected = r"Tuple\[int, str\]"
      actual = r"Tuple\[str, int\]"
      self.assertErrorLogIs(errors, [
          (8, "wrong-arg-types",
           r"Type\[%s\].*Type\[%s\]" % (expected, actual)),
          (9, "wrong-arg-types", r"%s.*%s" % (expected, actual)),
          (10, "wrong-arg-types", r"%s.*foo\.A" % expected)])

  def testTupleCombinationExplosion(self):
    self.Check("""
            from typing import Any, Dict, List, Tuple, Union
      AlphaNum = Union[str, int]
      def f(x: Dict[AlphaNum, Any]) -> List[Tuple]:
        return list(sorted((k, v) for k, v in x.items() if k in {}))
    """)

  def testTupleInContainer(self):
    ty = self.Infer("""
            from typing import List, Tuple
      def f(l: List[Tuple[int, List[int]]]):
        line, foo = l[0]
        return foo
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple, TypeVar
      def f(l: List[Tuple[int, List[int]]]) -> List[int]: ...
    """)

  def testMismatchedPyiTuple(self):
    with utils.Tempdir() as d:
      d.create_file("bar.pyi", """
        class Bar(tuple): ...
      """)
      errors = self.CheckWithErrors("""\
                from typing import Tuple
        import bar
        def foo() -> Tuple[bar.Bar, bar.Bar]:
          return bar.Bar(None, None)  # line 5
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(5, "wrong-arg-count", "1.*3")])


class TupleTestPython3Feature(test_base.TargetPython3FeatureTest):
  """Tests for __builtin__.tuple."""

  def testIteration(self):
    ty = self.Infer("""\
      class Foo(object):
        mytuple = (1, "foo", 3j)
        def __getitem__(self, pos):
          return Foo.mytuple.__getitem__(pos)
      r = [x for x in Foo()]  # Py 3 does not leak 'x'
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      class Foo(object):
        mytuple = ...  # type: Tuple[int, str, complex]
        def __getitem__(self, pos: int) -> int or str or complex
      r = ...  # type: List[int or str or complex]
    """)

  def testBadUnpackingWithSlurp(self):
    _, errors = self.InferWithErrors("""\
      a, *b, c = (1,)
    """)
    self.assertErrorLogIs(
        errors, [(1, "bad-unpacking", "1 value.*3 variables")])


if __name__ == "__main__":
  test_base.main()
