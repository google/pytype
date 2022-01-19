"""Tests for typing.Final and typing.final."""

from pytype.tests import test_base


class TestFinalDecorator(test_base.BaseTest):
  """Test @final."""

  def test_subclass(self):
    err = self.CheckWithErrors("""
      from typing import final
      @final
      class A:
        pass
      class B(A):  # base-class-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class A"]})

  def test_subclass_with_other_bases(self):
    err = self.CheckWithErrors("""
      from typing import final
      @final
      class A:
        pass
      class B(list, A):  # base-class-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class A"]})

  def test_typing_extensions_import(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
      @final
      class A:
        pass
      class B(A):  # base-class-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class A"]})


if __name__ == "__main__":
  test_base.main()
