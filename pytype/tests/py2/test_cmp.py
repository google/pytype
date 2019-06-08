"""Test comparison operators."""

from pytype.tests import test_base


class CmpOpTest(test_base.TargetPython27FeatureTest):
  """Tests comparison operator behavior in Python 2."""

  def test_lt(self):
    # In Python 2, comparisons between any two objects will always succeed,
    # so pytype will infer a boolean value for them.
    # In Python 3, this should be an error, because the int and str classes are
    # not comparable. (See tests/py3/test_cmp.py)
    # Comparison between types is necessary to trigger the "comparison always
    # succeeds" behavior in vm.py.
    ty = self.Infer("res = (1).__class__ < ''.__class__")
    self.assertTypesMatchPytd(ty, "res: bool")


test_base.main(globals(), __name__ == "__main__")
