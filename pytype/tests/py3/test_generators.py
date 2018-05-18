"""Tests for generators."""

from pytype.tests import test_base


class GeneratorTest(test_base.TargetPython3BasicTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def testReturnBeforeYield(self):
    self.Check("""
            from typing import Generator
      def f() -> generator:
        if __random__:
          return
        yield 5
    """)

  def testNoReturn(self):
    _, errors = self.InferWithErrors("""\
            from typing import Generator
      def f() -> Generator[str]:
        yield 42
    """)
    self.assertErrorLogIs(errors, [(4, "bad-return-type", r"str.*int")])


test_base.main(globals(), __name__ == "__main__")
