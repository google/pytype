"""Tests for generators."""

from pytype.tests import test_inference


class GeneratorTest(test_inference.InferenceTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def testNext(self):
    ty = self.Infer("""
      def f():
        return next(i for i in [1,2,3])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int
    """)

  def testList(self):
    ty = self.Infer("""
      y = list(x for x in [1, 2, 3])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      y = ...  # type: List[int, ...]
    """)

  def testReuse(self):
    ty = self.Infer("""
      y = list(x for x in [1, 2, 3])
      z = list(x for x in [1, 2, 3])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      y = ...  # type: List[int, ...]
      z = ...  # type: List[int, ...]
    """)

  def testNextWithDefault(self):
    ty = self.Infer("""
      def f():
        return next((i for i in [1,2,3]), None)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int or NoneType
    """)

  def testIterMatch(self):
    ty = self.Infer("""
      class Foo(object):
        def bar(self):
          for x in __any_object__:
            return x
        def __iter__(self):
          return generator()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def bar(self) -> ?
        def __iter__(self) -> Generator[nothing, nothing, nothing]
    """)

  def testCoroutineType(self):
    ty = self.Infer("""
      def foo(self):
        yield 3
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def foo(self) -> Generator[int, Any, Any]
    """)

  def testIterationOfGetItem(self):
    ty = self.Infer("""
      class Foo(object):
        def __getitem__(self, key):
          return "hello"

      def foo(self):
        for x in Foo():
          return x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __getitem__(self, key) -> str
      def foo(self) -> Union[None, str]
    """)


if __name__ == "__main__":
  test_inference.main()
