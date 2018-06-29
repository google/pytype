"""Test operators (basic tests)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ConcreteTest(test_base.TargetPython27FeatureTest,
                   test_utils.OperatorsTestMixin):
  """Tests for operators on concrete values (no unknowns)."""

  def test_div(self):
    self.check_expr("x / y", ["x=1", "y=2"], self.int)


class OverloadTest(test_base.TargetPython27FeatureTest,
                   test_utils.OperatorsTestMixin):
  """Tests for overloading operators."""

  def test_div(self):
    self.check_binary("__div__", "/")


class ReverseTest(test_base.TargetPython27FeatureTest,
                  test_utils.OperatorsTestMixin):
  """Tests for reverse operators."""

  def test_div(self):
    self.check_reverse("div", "/")


class InplaceTest(test_base.TargetPython27FeatureTest,
                  test_utils.OperatorsTestMixin):
  """Tests for in-place operators."""

  def test_div(self):
    self.check_inplace("idiv", "/=")


test_base.main(globals(), __name__ == "__main__")
