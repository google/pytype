"""Tests for classes."""

from pytype.tests import test_base


class ClassesTest(test_base.TargetPython27FeatureTest):
  """Tests for classes."""

  def testTypeChange(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.__class__ = int
      # Setting __class__ makes the type ambiguous to pytype, so it thinks that
      # both str.__mod__(unicode) -> unicode and str.__mod__(Any) -> str can
      # match this operation.
      x = "" % type(A())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        pass
      x = ...  # type: Any
    """)


test_base.main(globals(), __name__ == "__main__")
