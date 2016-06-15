"""Tests of builtins (in pytd/builtins/__builtins__.pytd).

File 2/2. Split into two parts to enable better test parallelism.
"""

from pytype.tests import test_inference


class BuiltinTests2(test_inference.InferenceTest):
  """Tests for builtin methods and classes."""

  def testDivModWithUnknown(self):
    ty = self.Infer("""
      def f(x, y):
        divmod(x, __any_object__)
        return divmod(3, y)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: int or float or complex or long,
            y: int or float or complex or long) -> Tuple[int or float or complex or long, ...]
    """)

  def testDefaultDict(self):
    ty = self.Infer("""
      import collections
      r = collections.defaultdict()
      r[3] = 3
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      r = ...  # type: collections.defaultdict
    """)

  def testImportLib(self):
    ty = self.Infer("""
      import importlib
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      importlib = ...  # type: module
    """)

  def testSetUnion(self):
    ty = self.Infer("""
      def f(y):
        return set.union(*y)
      def g(y):
        return set.intersection(*y)
      def h(y):
        return set.difference(*y)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(y) -> Set[Any]: ...
      def g(y) -> Set[Any]: ...
      def h(y) -> Set[Any]: ...
    """)

  def testFrozenSetInheritance(self):
    ty = self.Infer("""
      class Foo(frozenset):
        pass
      Foo([])
    """, deep=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(frozenset[Any]):
        pass
    """)


if __name__ == "__main__":
  test_inference.main()
