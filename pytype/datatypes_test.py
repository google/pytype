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
    self.assertEqual("hello", d["alias"])
    self.assertEqual("hello", d["name"])
    self.assertEqual("world", d["name2"])
    d.add_alias("name", "name2", op=lambda x, y: x + " " + y)
    self.assertEqual("hello world", d["name"])
    self.assertEqual("hello world", d["name2"])
    self.assertEqual("hello world", d["alias"])

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

  def testAliasingDictWithUnionFind(self):
    d = datatypes.AliasingDict()
    d["alias1"] = "1"
    d["alias3"] = "2"
    d.add_alias("alias1", "alias2")
    d.add_alias("alias4", "alias3")
    self.assertEqual(d["alias1"], "1")
    self.assertEqual(d["alias2"], "1")
    self.assertEqual(d["alias3"], "2")
    self.assertEqual(d["alias4"], "2")
    d.add_alias("alias1", "alias3", str.__add__)
    self.assertEqual(d["alias1"], "12")
    self.assertEqual(d["alias2"], "12")
    self.assertEqual(d["alias3"], "12")
    self.assertEqual(d["alias4"], "12")

    d["alias5"] = "34"
    d.add_alias("alias5", "alias6")
    d.add_alias("alias6", "alias7")
    d.add_alias("alias7", "alias8")
    self.assertEqual(d["alias5"], "34")
    self.assertEqual(d["alias6"], "34")
    self.assertEqual(d["alias7"], "34")
    self.assertEqual(d["alias8"], "34")

    d.add_alias("alias1", "alias8", str.__add__)
    for i in range(1, 9):
      self.assertEqual(d["alias" + str(i)], "1234")

  def testAliasingDictGet(self):
    d = datatypes.AliasingDict()
    d["alias1"] = "1"
    d.add_alias("alias1", "alias2")
    self.assertEqual(d.get("alias1"), "1")
    self.assertEqual(d.get("alias2"), "1")
    self.assertEqual(d.get("alias3", "2"), "2")
    self.assertEqual(d.get("alias3"), None)

  def testAddAliasForAliasingMonitorDict(self):
    d = datatypes.AliasingMonitorDict()
    d["alias1"] = "1"
    d["alias2"] = "1"
    self.assertEqual(2, len(d))
    # Merge with same values
    d.add_alias("alias1", "alias2")
    self.assertEqual(1, len(d))
    self.assertEqual(d["alias1"], "1")
    self.assertEqual(d["alias2"], "1")

    # Merge with different values
    d["alias3"] = "2"
    with self.assertRaises(datatypes.AliasingDictConflictError):
      d.add_alias("alias1", "alias3")

    # Neither of names has value
    d.add_alias("alias5", "alias6")
    # The first name is in dict
    d.add_alias("alias3", "alias4")
    # The second name is in dict
    d.add_alias("alias5", "alias3")
    self.assertEqual(d["alias3"], "2")
    self.assertEqual(d["alias4"], "2")
    self.assertEqual(d["alias5"], "2")
    self.assertEqual(d["alias6"], "2")

  def testAliasingMonitorDictMerge(self):
    d1 = datatypes.AliasingMonitorDict()
    d1["alias1"] = "1"
    d1.add_alias("alias1", "alias2")

    d2 = datatypes.AliasingMonitorDict()
    d2["alias3"] = "1"
    d2.add_alias("alias3", "alias4")

    d1.merge_from(d2)
    self.assertEqual(d1["alias1"], "1")
    self.assertEqual(d1["alias2"], "1")
    self.assertEqual(d1["alias3"], "1")
    self.assertEqual(d1["alias4"], "1")
    self.assertEqual(d1.same_name("alias3", "alias4"), True)

    d4 = datatypes.AliasingMonitorDict()
    d4["alias2"] = 3
    with self.assertRaises(datatypes.AliasingDictConflictError):
      d1.merge_from(d4)

    d3 = datatypes.AliasingMonitorDict()
    d3.add_alias("alias2", "alias5")
    d3["alias5"] = 3
    with self.assertRaises(datatypes.AliasingDictConflictError):
      d1.merge_from(d3)

if __name__ == "__main__":
  unittest.main()
