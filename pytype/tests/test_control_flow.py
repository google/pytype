"""Tests for control flow related issues.

TODO(b/241479600): This file tests control flow for a new block graph introduced
as part of a typegraph rewrite, while test_flow{1,2} exercise the old typegraph.
Merge the test files once the rewrite is complete.
"""

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy((3, 10), "Depends on 3.10+ bytecode")
class TestControlFlow(test_base.BaseTest):
  """Tests for control flow related features."""

  def test_local_definition(self):
    self.CheckWithErrors("""
      def f(x: int | str):
        if isinstance(x, int):
          if x > 10:
              y = 10
          else:
              a = False
        else:
          y = 'a'
        return y  # name-error
      """)

  def test_loop_variable(self):
    self.CheckWithErrors("""
      def f(xs):
        for x in xs:
          print(x)
        return x  # name-error
      """)

  def test_and_or(self):
    ty = self.Infer("""
      class Foo:
        def __bool__(self):
          return bool(__random__)

      a = Foo() and "a string" or 42
    """)
    # Behavior changed in 3.12: https://github.com/python/cpython/issues/124285
    if self.python_version >= (3, 12):
      self.assertTypesMatchPytd(
          ty,
          """
          class Foo:
            def __bool__(self) -> bool: ...
          a: str | int | Foo
          """,
      )
    else:
      self.assertTypesMatchPytd(
          ty,
          """
          class Foo:
            def __bool__(self) -> bool: ...
          a: str | int
          """,
      )


if __name__ == "__main__":
  test_base.main()
