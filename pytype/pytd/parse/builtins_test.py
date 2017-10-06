

import os
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd.parse import builtins
from pytype.pytd.parse import visitors
import unittest


class UtilsTest(unittest.TestCase):

  PYTHON_VERSION = (2, 7)

  @classmethod
  def setUpClass(cls):
    cls.builtins = builtins.GetBuiltinsPyTD(cls.PYTHON_VERSION)

  def testGetBuiltinsPyTD(self):
    self.assertIsNotNone(self.builtins)
    # Will throw an error for unresolved identifiers:
    self.builtins.Visit(visitors.VerifyLookup())

  def testHasMutableParameters(self):
    append = self.builtins.Lookup("__builtin__.list").Lookup("append")
    self.assertIsNotNone(append.signatures[0].params[0].mutated_type)

  def testHasCorrectSelf(self):
    update = self.builtins.Lookup("__builtin__.dict").Lookup("update")
    t = update.signatures[0].params[0].type
    self.assertIsInstance(t, pytd.GenericType)
    self.assertEqual(t.base_type, pytd.ClassType("__builtin__.dict"))

  def testHasObjectSuperClass(self):
    cls = self.builtins.Lookup("__builtin__.memoryview")
    self.assertEqual(cls.parents, (pytd.ClassType("__builtin__.object"),))
    cls = self.builtins.Lookup("__builtin__.object")
    self.assertEqual(cls.parents, ())

  def testParsePyTD(self):
    """Test ParsePyTD()."""
    ast = builtins.ParsePyTD("a = ...  # type: int",
                             "<inline>", python_version=(2, 7, 6),
                             lookup_classes=True)
    a = ast.Lookup("a").type
    self.assertItemsEqual(a, pytd.ClassType("int"))
    self.assertIsNotNone(a.cls)  # verify that the lookup succeeded

  def testParsePredefinedPyTD(self):
    """Test ParsePredefinedPyTD()."""
    ast = builtins.ParsePredefinedPyTD(
        "builtins", "__builtin__", python_version=(2, 7, 6))
    self.assertIsNotNone(ast.Lookup("__builtin__.int"))

  def testPrecompilation(self):
    # Get original (non-precompiled) values.
    b1, t1 = builtins.GetBuiltinsAndTyping(self.PYTHON_VERSION)
    # Write precompiled data.
    with utils.Tempdir() as d:
      precompiled = os.path.join(d.path, "precompiled.pickle")
      builtins.Precompile(precompiled, self.PYTHON_VERSION)
      # Clear the cache
      builtins._cached_builtins_pytd = None
      # Load precompiled data.
      builtins.LoadPrecompiled(precompiled)
    self.assertIsNotNone(builtins._cached_builtins_pytd)
    b2, t2 = builtins.GetBuiltinsAndTyping(self.PYTHON_VERSION)
    self.assertEqual(pytd.Print(b1), pytd.Print(b2))
    self.assertEqual(pytd.Print(t1), pytd.Print(t2))


if __name__ == "__main__":
  unittest.main()
