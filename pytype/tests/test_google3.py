"""Tests for --check."""

from pytype import utils
from pytype.tests import test_base


class Google3Test(test_base.TargetIndependentTest):
  """Tests for the google3 overlay."""

  def testTypeCheckingConstant(self):
    with utils.Tempdir() as d:
      d.create_file("google3.pyi", "TYPE_CHECKING = ...  # type: bool")
      self.Check("""
        import google3
        if google3.TYPE_CHECKING:
          foo = ""
        else:
          foo = 42
        foo = foo.upper()
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
