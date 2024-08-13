"""Basic tests over Python 3 targets."""

from pytype.tests import test_base


class TestExec(test_base.BaseTest):
  """Basic tests."""

  def test_exec_function(self):
    self.assertNoCrash(
        self.Check,
        """
      g = {}
      exec("a = 11", g, g)
      assert g['a'] == 11
      """,
    )

  def test_import_shadowed(self):
    """Test that we import modules from pytd/ rather than typeshed."""
    # We can't import the following modules from typeshed; this tests that we
    # import them correctly from our internal pytd/ versions.
    for module in ["importlib", "re", "signal"]:
      ty = self.Infer(f"import {module}")
      self.assertTypesMatchPytd(ty, f"import {module}")

  def test_cleanup(self):
    ty = self.Infer("""
      with open("foo.py", "r") as f:
        v = f.read()
      w = 42
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TextIO
      f = ...  # type: TextIO
      v = ...  # type: str
      w = ...  # type: int
    """,
    )

  def test_store_fast_empty_var(self):
    self.assertNoCrash(
        self.Check,
        """
        def bar():
          raise NotImplementedError
        def foo():
          try:
            bar()
          except () as e: # Emits STORE_FAST for `e` and STACK[-1] is empty var
                          # (i.e. no bindings)
            pass
        """,
    )

  def test_unconditionally_del_export(self):
    ty = self.Infer("""
      foo = 1
      def bar():
        return 1
      class Baz:
        def __init__(self):
          self.baz = 1
      del foo   # unconditionally deleted --> should not appear in types
      del bar   # unconditionally deleted --> should not appear in types
      del Baz   # unconditionally deleted --> should not appear in types
    """)
    self.assertTypesMatchPytd(ty, "")

  def test_conditionally_del_export(self):
    ty = self.Infer("""
      foo = 1
      def bar():
        return 1
      class Baz:
        def __init__(self):
          self.baz = 1
      if __random__:
        del foo   # conditionally deleted --> should appear in types
        del bar   # conditionally deleted --> should appear in types
        del Baz   # conditionally deleted --> should appear in types
    """)
    self.assertTypesMatchPytd(
        ty,
        """
        # TODO: b/359466700 - Ideally we could say that `foo` might be absent.
        foo: int
        def bar() -> int: ...
        class Baz:
          baz: int
          def __init__(self) -> None: ...
        """,
    )


if __name__ == "__main__":
  test_base.main()
