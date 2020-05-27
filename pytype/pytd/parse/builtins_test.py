"""Tests for pytype.pytd.parse.builtins."""

from pytype.pytd import pytd
from pytype.pytd import visitors
from pytype.pytd.parse import builtins
from pytype.tests import test_base
import unittest


class UtilsTest(test_base.UnitTest):

  @classmethod
  def setUpClass(cls):
    super(UtilsTest, cls).setUpClass()
    cls.builtins = builtins.GetBuiltinsPyTD(cls.python_version)

  def test_get_builtins_pytd(self):
    self.assertIsNotNone(self.builtins)
    # Will throw an error for unresolved identifiers:
    self.builtins.Visit(visitors.VerifyLookup())

  def test_has_mutable_parameters(self):
    append = self.builtins.Lookup("__builtin__.list").Lookup("append")
    self.assertIsNotNone(append.signatures[0].params[0].mutated_type)

  def test_has_correct_self(self):
    update = self.builtins.Lookup("__builtin__.dict").Lookup("update")
    t = update.signatures[0].params[0].type
    self.assertIsInstance(t, pytd.GenericType)
    self.assertEqual(t.base_type, pytd.ClassType("__builtin__.dict"))

  def test_has_object_superclass(self):
    cls = self.builtins.Lookup("__builtin__.memoryview")
    self.assertEqual(cls.parents, (pytd.ClassType("__builtin__.object"),))
    cls = self.builtins.Lookup("__builtin__.object")
    self.assertEqual(cls.parents, ())


if __name__ == "__main__":
  unittest.main()
