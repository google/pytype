"""Tests for datatypes.py."""

from pytype import datatypes
from pytype.typegraph import cfg

import unittest


class AccessTrackingDictTest(unittest.TestCase):
  """Test AccessTrackingDict."""

  def setUp(self):
    self.d = datatypes.AccessTrackingDict({"a": 1, "b": 2})

  def test_get(self):
    v = self.d["a"]
    item, = self.d.accessed_subset.items()
    self.assertEqual(item, ("a", 1))
    self.assertEqual(v, 1)

  def test_set(self):
    self.d["a"] = 3
    item, = self.d.accessed_subset.items()
    self.assertEqual(item, ("a", 1))
    self.assertEqual(self.d["a"], 3)

  def test_set_new(self):
    self.d["c"] = 3
    self.assertFalse(self.d.accessed_subset)

  def test_del(self):
    del self.d["a"]
    item, = self.d.accessed_subset.items()
    self.assertEqual(item, ("a", 1))
    with self.assertRaises(KeyError):
      _ = self.d["a"]

  def test_repeat_access(self):
    self.d["a"] = 3
    v = self.d["a"]
    item, = self.d.accessed_subset.items()
    self.assertEqual(item, ("a", 1))
    self.assertEqual(v, 3)


class DatatypesTest(unittest.TestCase):
  """Test datatypes."""

  def setUp(self):
    self.prog = cfg.Program()

  def testMonitorDict(self):
    d = datatypes.MonitorDict()
    changestamp = d.changestamp
    var = self.prog.NewVariable()
    d["key"] = var
    self.assertGreater(d.changestamp, changestamp)
    changestamp = d.changestamp
    var.AddBinding("data")
    self.assertGreater(d.changestamp, changestamp)
    changestamp = d.changestamp
    var.AddBinding("data")  # No change because this is duplicate data
    self.assertEqual(d.changestamp, changestamp)
    changestamp = d.changestamp

  def testAliasingDict(self):
    d = datatypes.AliasingDict()
    # To avoid surprising behavior, we require desired dict functionality to be
    # explicitly overridden
    with self.assertRaises(NotImplementedError):
      d.viewitems()
    d.add_alias("alias", "name")
    self.assertNotIn("alias", d)
    self.assertNotIn("name", d)
    var1 = self.prog.NewVariable()
    d["alias"] = var1
    self.assertIn("name", d)
    self.assertIn("alias", d)
    self.assertEqual(var1, d["name"])
    self.assertEqual(d["name"], d["alias"])
    self.assertEqual(d["alias"], d.get("alias"))
    self.assertEqual(d["name"], d.get("name"))
    self.assertEqual(None, d.get("other_name"))
    var2 = self.prog.NewVariable()
    d["name"] = var2
    self.assertEqual(var2, d["name"])
    self.assertEqual(d["name"], d["alias"])

  def testAliasingDictRealiasing(self):
    d = datatypes.AliasingDict()
    d.add_alias("alias1", "name")
    d.add_alias("alias2", "name")
    self.assertRaises(AssertionError,
                      lambda: d.add_alias("name", "other_name"))
    try:
      d.add_alias("alias1", "other_name")
    except datatypes.AliasingDictConflictError as e:
      self.assertEqual(e.existing_name, "name")
    else:
      self.fail("AliasingDictConflictError not raised")
    d.add_alias("alias1", "name")
    d.add_alias("alias2", "alias1")
    d.add_alias("alias1", "alias2")
    # Check that the name, alias1, and alias2 still all refer to the same key
    var = self.prog.NewVariable()
    d["alias1"] = var
    self.assertEqual(1, len(d))
    self.assertEqual(var, d["name"])
    self.assertEqual(var, d["alias1"])
    self.assertEqual(var, d["alias2"])

  def testNonemptyAliasingDictRealiasing(self):
    d = datatypes.AliasingDict()
    d.add_alias("alias", "name")
    d["name"] = "hello"
    d["name2"] = "world"
    self.assertRaises(datatypes.AliasingDictConflictError,
                      lambda: d.add_alias("name2", "name"))
    d.add_alias("alias", "name")

  def testAliasingDictTransitive(self):
    d = datatypes.AliasingDict()
    d.add_alias("alias1", "name")
    d.add_alias("alias2", "alias1")
    d["name"] = self.prog.NewVariable()
    self.assertEqual(1, len(d))
    self.assertEqual(d["name"], d["alias1"])
    self.assertEqual(d["alias1"], d["alias2"])

  def testAliasingDictValueMove(self):
    d = datatypes.AliasingDict()
    v = self.prog.NewVariable()
    d["alias"] = v
    d.add_alias("alias", "name")
    self.assertEqual(d["name"], v)
    self.assertEqual(d["alias"], d["name"])

  def testAliasingDictTransitiveValueMove(self):
    d = datatypes.AliasingDict()
    d.add_alias("alias2", "name")
    v = self.prog.NewVariable()
    d["alias1"] = v
    d.add_alias("alias1", "alias2")
    self.assertEqual(d["name"], v)
    self.assertEqual(d["alias2"], d["name"])
    self.assertEqual(d["alias1"], d["alias2"])


if __name__ == "__main__":
  unittest.main()
