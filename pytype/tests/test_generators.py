"""Tests for generators."""

from pytype.tests import test_inference


class GeneratorTest(test_inference.InferenceTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def testNext(self):
    with self.Infer("""
      def f():
        return next(i for i in [1,2,3])
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> int
      """)

  def testList(self):
    with self.Infer("""
      y = list(x for x in [1, 2, 3])
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        y: list[int]
      """)

  def testReuse(self):
    with self.Infer("""
      y = list(x for x in [1, 2, 3])
      z = list(x for x in [1, 2, 3])
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        y: list[int]
        z: list[int]
      """)

  def testNextWithDefault(self):
    with self.Infer("""
      def f():
        return next((i for i in [1,2,3]), None)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> int or NoneType
      """)

  def testIterMatch(self):
    with self.Infer("""
      class Foo(object):
        def bar(self):
          for x in __any_object__:
            return x
        def __iter__(self):
          return generator()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class Foo:
          def bar(self) -> ?
          def __iter__(self) -> generator[nothing]
      """)

  def testCoroutineType(self):
    with self.Infer("""
      def foo(self):
        yield 3
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def foo(self) -> generator[int]
      """)

if __name__ == "__main__":
  test_inference.main()
