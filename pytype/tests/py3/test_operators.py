"""Test operators (basic tests)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ConcreteTest(test_base.TargetPython3FeatureTest,
                   test_utils.OperatorsTestMixin):
  """Tests for operators on concrete values (no unknowns)."""

  def test_div(self):
    self.check_expr("x / y", ["x=1", "y=2"], self.float)


class OverloadTest(test_base.TargetPython3FeatureTest,
                   test_utils.OperatorsTestMixin):
  """Tests for overloading operators."""

  def test_div(self):
    self.check_binary("__truediv__", "/")


class ReverseTest(test_base.TargetPython3FeatureTest,
                  test_utils.OperatorsTestMixin):
  """Tests for reverse operators."""

  def test_div(self):
    self.check_reverse("truediv", "/")


class InplaceTest(test_base.TargetPython3FeatureTest,
                  test_utils.OperatorsTestMixin):
  """Tests for in-place operators."""

  def test_div(self):
    self.check_inplace("itruediv", "/=")


test_base.main(globals(), __name__ == "__main__")
