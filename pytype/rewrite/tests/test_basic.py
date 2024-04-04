"""Basic functional tests."""
from pytype.tests import test_base


class BasicTest(test_base.BaseTest):
  """Basic functional tests."""

  def setUp(self):
    super().setUp()
    self.options.tweak(use_rewrite=True)

  def test_analyze_functions(self):
    self.Check("""
      def f():
        def g():
          pass
    """)

  def test_analyze_function_with_nonlocal(self):
    self.Check("""
      def f():
        x = None
        def g():
          return x
    """)

  def test_function_parameter(self):
    self.Check("""
      def f(x):
        return x
      f(0)
    """)

  def test_class(self):
    self.Check("""
      class C:
        def __init__(self):
          pass
    """)

  def test_method_side_effect(self):
    self.Check("""
      class C:
        def f(self):
          self.x = 3
        def g(self):
          self.f()
          return self.x
    """)

  def test_infer_stub(self):
    ty = self.Infer("""
      def f():
        def g():
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> None: ...
    """)

  def test_assert_type(self):
    errors = self.CheckWithErrors("""
      assert_type(0, int)
      assert_type(0, "int")
      assert_type(0, "str")  # assert-type[e]
    """)
    self.assertErrorSequences(errors, {'e': ['Expected: str', 'Actual: int']})


if __name__ == '__main__':
  test_base.main()
