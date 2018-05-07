"""Tests for reloading generated pyi."""

from pytype import utils
from pytype.pytd import pytd
from pytype.tests import test_base


class ReingestTest(test_base.TargetPython3BasicTest):
  """Tests for reloading the pyi we generate."""

  def testTypeParameterBound(self):
    foo = self.Infer("""
            from typing import TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T: return x
    """, deep=False)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd.Print(foo))
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f("")
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"float.*str")])

  def testDefaultArgumentType(self):
    foo = self.Infer("""
            from typing import Any, Callable, TypeVar
      T = TypeVar("T")
      def f(x):
        return True
      def g(x: Callable[[T], Any]) -> T: ...
    """)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd.Print(foo))
      self.Check("""
        import foo
        foo.g(foo.f).upper()
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
