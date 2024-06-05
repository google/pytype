"""Tests for --quick."""

from pytype.tests import test_base


class QuickTest(test_base.BaseTest):
  """Tests for --quick."""

  def test_max_depth(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self, elements):
          assert all(e for e in elements)
          self.elements = elements

        def bar(self):
          return self.elements
    """, quick=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo:
        elements = ...  # type: Any
        def __init__(self, elements: Any) -> None: ...
        def bar(self) -> Any: ...
    """)

  def test_closure(self):
    ty = self.Infer("""
      def f():
        class A: pass
        return {A: A()}
    """, quick=True, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      def f() -> dict: ...
    """)

  def test_init(self):
    # Tests that it's possible for --quick to handle this case with a large
    # enough maximum depth, even though it can't currently due to
    # QUICK_INFER_MAXIMUM_DEPTH being 1.
    ty = self.Infer("""
      class A:
        def __init__(self):
          self.real_init()
        def real_init(self):
          self.x = 42
        def f(self):
          return self.x
      def f():
        return A().f()
    """, quick=True, maximum_depth=2)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A:
        x = ...  # type: int
        def __init__(self) -> None: ...
        def real_init(self) -> None: ...
        def f(self) -> int: ...
      def f() -> Any: ...
    """)

  def test_analyze_annotated_max_depth(self):
    # --output with --analyze-annotated has the same max depth as --check.
    _, errors = self.InferWithErrors("""
      def make_greeting(user_id):
        return 'hello, user' + user_id  # unsupported-operands[e]
      def print_greeting():
        print(make_greeting(0))
    """, quick=True)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_max_depth_and_property(self):
    self.Check("""
      class C:
        def __init__(self):
          self.f()
        def f(self):
          pass
        @property
        def x(self) -> int:
          return 0
        def g(self):
          assert_type(self.x, int)
    """, quick=True, maximum_depth=1)


if __name__ == "__main__":
  test_base.main()
