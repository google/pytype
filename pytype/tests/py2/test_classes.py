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

  def testInitTestClassInSetup(self):
    ty = self.Infer("""\
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      unittest = ...  # type: module
      class A(unittest.TestCase):
          x = ...  # type: int
          def fooTest(self) -> int: ...
    """)

  def testInitInheritedTestClassInSetup(self):
    ty = self.Infer("""\
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
      class B(A):
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      unittest = ...  # type: module
      class A(unittest.TestCase):
          x = ...  # type: int
      class B(A):
          x = ...  # type: int
          def fooTest(self) -> int: ...
    """)


test_base.main(globals(), __name__ == "__main__")
