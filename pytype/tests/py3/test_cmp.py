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


class CmpOpTest(test_base.TargetPython3FeatureTest):
  """Tests comparison operator behavior in Python 3."""

  def test_lt(self):
    # In Python 3, comparisons between two types that don't define their own
    # comparison dunder methods is not guaranteed to succeed, except for ==, !=,
    # is and is not.
    # pytype infers a boolean value for those comparisons that always succeed,
    # and currently infers Any for ones that don't.
    # In Python 2, "x" would be bool. (See tests/py2/test_cmp.py)
    # Comparison between types is necessary to trigger the "comparison always
    # succeeds" behavior in vm.py.
    ty = self.Infer("res = (1).__class__ < ''.__class__")
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      res: Any
    """)


test_base.main(globals(), __name__ == "__main__")
