"""Tests for --quick."""

from pytype.tests import test_base


class QuickTest(test_base.TargetIndependentTest):
  """Tests for --quick."""

  def testMaxDepth(self):
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

  def testArgUnknowns(self):
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
    self.assertTrue(p.type.name.startswith("~unknown"))
    # Lookup that a class with same _unknown_ name as the param type exists.
    _ = ty.Lookup(p.type.name)

  def testClosure(self):
    ty = self.Infer("""
      def f():
        class A(object): pass
        return {A: A()}
    """, quick=True, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      def f() -> dict
    """)

  def testInit(self):
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
        def real_init(self) -> None
        def f(self) -> int
      def f() -> Any
    """)


if __name__ == "__main__":
  test_base.main()
