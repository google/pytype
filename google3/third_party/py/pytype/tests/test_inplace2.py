"""Test operators (basic tests)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class InplaceTest(test_base.BaseTest,
                  test_utils.InplaceTestMixin):
  """In-place operator tests."""

  # / changed its semantics in python3, so this is forked into two tests.
  def test_idiv(self):
    self._check_inplace("/", ["x=1", "y=2"], "float")
    self._check_inplace("/", ["x=1.0", "y=2"], "float")
    self._check_inplace("/", ["x=1", "y=2.0"], "float")
    self._check_inplace("/", ["x=1j", "y=2j"], "complex")
    self._check_inplace("/", ["x=2j", "y=1"], "complex")
    self._check_inplace("/", ["x=3+2j", "y=1.0"], "complex")


if __name__ == "__main__":
  test_base.main()
