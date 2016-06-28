"""Tests for pytype.pytd.parse.builtins."""

from pytype.pytd import pytd
from pytype.pytd.parse import builtins
from pytype.pytd.parse import visitors
import unittest


class UtilsTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.builtins = builtins.GetBuiltinsPyTD()

  def testGetBuiltinsPyTD(self):
    self.assertIsNotNone(self.builtins)
    # Will throw an error for unresolved identifiers:
    visitors.LookupClasses(self.builtins)

  def testHasMutableParameters(self):
    append = self.builtins.Lookup("__builtin__.list").Lookup("append")
    self.assertIsInstance(append.signatures[0].params[0], pytd.MutableParameter)

  def testHasCorrectSelf(self):
    update = self.builtins.Lookup("__builtin__.dict").Lookup("update")
    t = update.signatures[0].params[0].type
    self.assertIsInstance(t, pytd.GenericType)
    self.assertEquals(t.base_type, pytd.ClassType("__builtin__.dict"))

  def testHasObjectSuperClass(self):
    cls = self.builtins.Lookup("__builtin__.int")
    self.assertEquals(cls.parents, (pytd.ClassType("__builtin__.object"),))
    cls = self.builtins.Lookup("__builtin__.object")
    self.assertEquals(cls.parents, ())


if __name__ == "__main__":
  unittest.main()
