"""Test comparison operators."""

from pytype.tests import test_base


class InstanceUnequalityTest(test_base.TargetPython3BasicTest):

  def test_is(self):
    """SomeType is not be the same as AnotherType."""
    self.Check("""
            from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is None:
          return x
        else:
          return None
      """)


if __name__ == "__main__":
  test_base.main()
