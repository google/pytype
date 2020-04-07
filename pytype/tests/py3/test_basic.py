"""Basic tests over Python 3 targets."""

from pytype.tests import test_base


class TestExec(test_base.TargetPython3FeatureTest):
  """Basic tests."""

  def test_exec_function(self):
    self.assertNoCrash(self.Check, """
      g = {}
      exec("a = 11", g, g)
      assert g['a'] == 11
      """)

  def test_import_shadowed(self):
    """Test that we import modules from pytd/ rather than typeshed."""
    # We can't import the following modules from typeshed; this tests that we
    # import them correctly from our internal pytd/ versions.
    for module in [
        "importlib",
        "re",
        "signal"
    ]:
      ty = self.Infer("import %s" % module)
      expected = "  %s = ...  # type: module" % module
      self.assertTypesMatchPytd(ty, expected)

  def test_cleanup(self):
    ty = self.Infer("""
      with open("foo.py", "r") as f:
        v = f.read()
      w = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TextIO
      f = ...  # type: TextIO
      v = ...  # type: str
      w = ...  # type: int
    """)


test_base.main(globals(), __name__ == "__main__")
