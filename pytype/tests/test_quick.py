"""Tests for --quick."""

from pytype.pytd import escape
from pytype.tests import test_base


class QuickTest(test_base.TargetIndependentTest):
  """Tests for --quick."""

  def test_max_depth(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, elements):
          assert all(e for e in elements)
          self.elements = elements

        def bar(self):
          return self.elements
    """, quick=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        elements = ...  # type: Any
        def __init__(self, elements: Any) -> None: ...
        def bar(self) -> Any: ...
    """)

  def test_arg_unknowns(self):
    # test that even with --quick, we still generate ~unknowns for parameters.
    ty = self.Infer("""
      def f(x):
        return 42
    """, quick=True, show_library_calls=True)
    f = ty.Lookup("f")
    self.assertEqual(len(f.signatures), 1)
    s = f.signatures[0]
    self.assertEqual(len(s.params), 1)
    p = s.params[0]
    self.assertTrue(escape.is_unknown(p.type.name))
    # Lookup that a class with same _unknown_ name as the param type exists.
    _ = ty.Lookup(p.type.name)

  def test_closure(self):
    ty = self.Infer("""
      def f():
        class A(object): pass
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
      class A(object):
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
      class A(object):
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


test_base.main(globals(), __name__ == "__main__")
