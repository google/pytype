"""Basic functional tests."""
from pytype.rewrite.tests import test_utils
from pytype.tests import test_base


class RewriteTest(test_base.BaseTest):

  def setUp(self):
    super().setUp()
    self.options.tweak(use_rewrite=True)


class BasicTest(RewriteTest):
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

  @test_utils.skipBeforePy((3, 11), 'Relies on 3.11+ bytecode')
  def test_function_kwargs(self):
    self.Check("""
      def f(x, *, y):
        return x
      f(0, y=1)
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

  def test_infer_class_body(self):
    ty = self.Infer("""
      class C:
        def __init__(self):
          self.x = 3
        def f(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      class C:
        x: int
        def __init__(self) -> None: ...
        def f(self) -> int: ...
    """)


class ImportsTest(RewriteTest):
  """Import tests."""

  def test_import(self):
    self.Check("""
      import os
      assert_type(os.__name__, str)  # attribute of the 'module' class
      assert_type(os.name, str)  # attribute of the 'os' module
    """)

  def test_builtins(self):
    self.Check("""
      assert_type(__builtins__.int, "Type[int]")
    """)

  def test_dotted_import(self):
    self.Check("""
      import os.path
      assert_type(os.path, "module")
    """)

  @test_base.skip('Not yet implemented')
  def test_from_import(self):
    self.Check("""
      from os import name, path
      assert_type(name, "str")
      assert_type(path, "module")
    """)

  @test_base.skip('Not yet implemented')
  def test_errors(self):
    self.CheckWithErrors("""
      import nonsense  # import-error
      import os.nonsense  # import-error
      from os import nonsense  # import-error
    """)

  def test_aliases(self):
    self.Check("""
      import os as so
      assert_type(so.name, "str")

      # Not yet implemented:
      # import os.path as path1
      # from os import path as path2
    """)


if __name__ == '__main__':
  test_base.main()
