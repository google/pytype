"""Test for the cfg Python extension module."""

from pytype.pytd import cfg
import unittest


class CFGTest(unittest.TestCase):
  """Test control flow graph creation."""

  def testSimpleGraph(self):
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = n1.ConnectNew()
    n3 = n1.ConnectNew()
    n4 = n3.ConnectNew()
    self.assertEquals(len(n1.outgoing), 2)
    self.assertEquals(len(n2.outgoing), 0)
    self.assertEquals(len(n3.outgoing), 1)
    self.assertEquals(len(n2.incoming), 1)
    self.assertEquals(len(n3.incoming), 1)
    self.assertEquals(len(n4.incoming), 1)
    self.assertIn(n2, n1.outgoing)
    self.assertIn(n3, n1.outgoing)
    self.assertIn(n1, n2.incoming)
    self.assertIn(n1, n3.incoming)
    self.assertIn(n3, n4.incoming)

  def testValueValue(self):
    p = cfg.Program()
    node = p.NewCFGNode()
    u = p.NewVariable("v")
    v1 = u.AddValue(None, source_set=[], where=node)
    v2 = u.AddValue(u"data", source_set=[], where=node)
    v3 = u.AddValue({1: 2}, source_set=[], where=node)
    self.assertEquals(v1.data, None)
    self.assertEquals(v2.data, u"data")
    self.assertEquals(v3.data, {1: 2})

  def testGetAttro(self):
    p = cfg.Program()
    node = p.NewCFGNode()
    u = p.NewVariable("foo")
    data = [1, 2, 3]
    a = u.AddValue(data, source_set=[], where=node)
    self.assertEquals(a.variable.name, "foo")
    self.assertEquals(a.variable.values, [a])
    origin, = a.origins  # we expect exactly one origin
    self.assertEquals(origin.where, node)
    self.assertEquals(len(origin.source_sets), 1)
    source_set, = origin.source_sets
    self.assertEquals(list(source_set), [])
    self.assertEquals(a.data, data)

  def testGetOrigins(self):
    p = cfg.Program()
    node = p.NewCFGNode()
    u = p.NewVariable("foo")
    a = u.AddValue(1, source_set=[], where=node)
    b = u.AddValue(2, source_set=[a], where=node)
    c = u.AddValue(3, source_set=[a, b], where=node)
    expected_source_sets = [[], [a], [a, b]]
    for value, expected_source_set in zip([a, b, c], expected_source_sets):
      origin, = value.origins
      self.assertEquals(origin.where, node)
      source_set, = origin.source_sets
      self.assertItemsEqual(list(source_set), expected_source_set)

  def testValueName(self):
    p = cfg.Program()
    u = p.NewVariable("foo")
    self.assertEquals(u.name, "foo")
    u.name = "bar"
    self.assertEquals(u.name, "bar")

  def _Freeze(self, program, entrypoint=None):
    program.entrypoint = entrypoint
    program.Freeze()

  def testVariableSet(self):
    p = cfg.Program()
    node1 = p.NewCFGNode()
    node2 = node1.ConnectNew()
    d = p.NewVariable("d")
    d.AddValue("v1", source_set=[], where=node1)
    d.AddValue("v2", source_set=[], where=node2)
    self.assertEquals(len(d.values), 2)

  def testFilter(self):
    #                    x.ab = A()
    #               ,---+------------.
    #               |   n3           |
    #  x = X()      |    x.ab = B()  |
    #  +------------+---+------------+------------+
    #  n1           n2  n4           n5           n6
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = n1.ConnectNew()
    n3 = n2.ConnectNew()
    n4 = n2.ConnectNew()
    n5 = n3.ConnectNew()
    n4.ConnectTo(n5)
    n6 = n5.ConnectNew()
    n5.ConnectTo(n6)

    all_x = p.NewVariable("x")
    x = all_x.AddValue({}, source_set=[], where=n1)
    ab = p.NewVariable("x.ab")
    x.data["ab"] = ab
    a = ab.AddValue("A", source_set=[], where=n3)
    b = ab.AddValue("B", source_set=[], where=n4)

    self._Freeze(p)
    self.assertFalse(a.IsVisible(n1) or b.IsVisible(n1))
    self.assertFalse(a.IsVisible(n2) or b.IsVisible(n2))
    self.assertTrue(a.IsVisible(n3))
    self.assertTrue(b.IsVisible(n4))
    self.assertEquals(ab.Filter(n1), [])
    self.assertEquals(ab.Filter(n2), [])
    self.assertEquals(ab.FilteredData(n3), ["A"])
    self.assertEquals(ab.FilteredData(n4), ["B"])
    self.assertSameElements(["A", "B"], ab.FilteredData(n5))
    self.assertSameElements(["A", "B"], ab.FilteredData(n6))

  def testCombinations(self):
    # n1------->n2
    #  |        |
    #  v        v
    # n3------->n4
    # [n2] x = a; y = a
    # [n3] x = b; y = b
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n1.ConnectNew("n3")
    n4 = n2.ConnectNew("n4")
    n3.ConnectTo(n4)
    x = p.NewVariable("x")
    y = p.NewVariable("y")
    xa = x.AddValue("a", source_set=[], where=n2)
    ya = y.AddValue("a", source_set=[], where=n2)
    xb = x.AddValue("b", source_set=[], where=n3)
    yb = y.AddValue("b", source_set=[], where=n3)
    self._Freeze(p)
    self.assertTrue(n4.HasCombination([xa, ya]))
    self.assertTrue(n4.HasCombination([xb, yb]))
    self.assertFalse(n4.HasCombination([xa, yb]))
    self.assertFalse(n4.HasCombination([xb, ya]))

  def testConflicting(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable("x")
    a = x.AddValue("a", source_set=[], where=n1)
    b = x.AddValue("b", source_set=[], where=n1)
    self._Freeze(p)
    # At n1, x can either be a or b, but not both.
    self.assertTrue(n1.HasCombination([a]))
    self.assertTrue(n1.HasCombination([b]))
    self.assertFalse(n1.HasCombination([a, b]))

  def testOneStepSimultaneous(self):
    # Like testSimultaneous, but woven through an additional node
    # n1->n2->n3
    # [n1] x = a or b
    # [n2] y = x
    # [n2] z = x
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable("x")
    y = p.NewVariable("y")
    z = p.NewVariable("z")
    a = x.AddValue("a", source_set=[], where=n1)
    b = x.AddValue("b", source_set=[], where=n1)
    ya = y.AddValue("ya", source_set=[a], where=n2)
    yb = y.AddValue("yb", source_set=[b], where=n2)
    za = z.AddValue("za", source_set=[a], where=n2)
    zb = z.AddValue("zb", source_set=[b], where=n2)
    self._Freeze(p)
    self.assertTrue(n2.HasCombination([ya, za]))
    self.assertTrue(n2.HasCombination([yb, zb]))
    self.assertFalse(n2.HasCombination([ya, zb]))
    self.assertFalse(n2.HasCombination([yb, za]))

  def testSameNodeOrigin(self):
    # [n1] x = a or b; y = x
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable("x")
    y = p.NewVariable("y")
    xa = x.AddValue("xa", source_set=[], where=n1)
    xb = x.AddValue("xb", source_set=[], where=n1)
    ya = y.AddValue("ya", source_set=[xa], where=n1)
    yb = y.AddValue("yb", source_set=[xb], where=n1)
    self._Freeze(p)
    self.assertTrue(n1.HasCombination([xa]))
    self.assertTrue(n1.HasCombination([xb]))
    self.assertTrue(n1.HasCombination([xa, ya]))
    self.assertTrue(n1.HasCombination([xb, yb]))
    # We don't check the other two combinations, because within one CFG node,
    # values are treated as having any order, so the other combinations
    # are possible, too:
    # n1.HasCombination([xa, yb]) == True (because x = b; y = x; x = a)
    # n1.HasCombination([xb, ya]) == True (because x = a; y = x; x = b)

  def testNewVariable(self):
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = p.NewCFGNode()
    x, y, z = "x", "y", "z"
    variable = p.NewVariable("xyz",
                             values=[x, y],
                             source_set=[],
                             where=n1)
    variable.AddValue(z, source_set=variable.values, where=n2)
    self.assertSameElements([x, y, z], [v.data for v in variable.values])
    self.assertTrue(any(len(e.origins) for e in variable.values))

  def testNodeValues(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("node1")
    n2 = n1.ConnectNew("node2")
    self.assertEquals(n1.name, "node1")
    self.assertEquals(n2.name, "node2")
    u = p.NewVariable("var")
    a1 = u.AddValue(1, source_set=[], where=n1)
    a2 = u.AddValue(2, source_set=[], where=n1)
    a3 = u.AddValue(3, source_set=[], where=n1)
    a4 = u.AddValue(4, source_set=[], where=n1)
    self.assertSameElements([a1, a2, a3, a4], n1.values)

  def testProgram(self):
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = n1.ConnectNew()
    u1 = p.NewVariable("var1")
    u2 = p.NewVariable("var2")
    self.assertEquals(u1.name, "var1")
    self.assertEquals(u2.name, "var2")
    a11 = u1.AddValue(11, source_set=[], where=n1)
    a12 = u1.AddValue(12, source_set=[], where=n2)
    a21 = u2.AddValue(21, source_set=[], where=n1)
    a22 = u2.AddValue(22, source_set=[], where=n2)
    self.assertSameElements([n1, n2], p.cfg_nodes)
    self.assertSameElements([u1, u2], p.variables)
    self.assertSameElements([a11, a21], n1.values)
    self.assertSameElements([a12, a22], n2.values)

  def testEntryPoint(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    x = p.NewVariable("x")
    a = x.AddValue("a", source_set=[], where=n2)
    self._Freeze(p)
    self.assertTrue(n2.HasCombination([a]))
    self._Freeze(p, entrypoint=n2)
    self.assertTrue(n2.HasCombination([a]))
    self._Freeze(p, entrypoint=n1)
    self.assertFalse(n2.HasCombination([a]))

  def testEntryPoint2(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable("x")
    a = x.AddValue("a", source_set=[], where=n1)
    a = x.AddValue("b", source_set=[], where=n2)
    self._Freeze(p, entrypoint=n1)
    self.assertTrue(n2.HasCombination([a]))

  def testFilterWithEntryPoint(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    x = p.NewVariable("x")
    a = x.AddValue("a", source_set=[], where=n2)
    self._Freeze(p)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [a])
    self._Freeze(p, entrypoint=n1)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [])
    # This is atypical: We wouldn't normally change the entrypoint of a program
    # after we've set it. But these are tests.
    self._Freeze(p, entrypoint=None)
    self.assertEquals(x.FilteredData(n1), [])
    self.assertEquals(x.FilteredData(n2), ["a"])
    self._Freeze(p, entrypoint=n1)
    self.assertEquals(x.FilteredData(n1), [])
    self.assertEquals(x.FilteredData(n2), [])

  def testEmptyValue(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew()
    x = p.NewVariable("x")
    a = x.AddValue("a")
    self._Freeze(p)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [])
    a.AddOrigin(n2, [])
    self._Freeze(p)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [a])
    a.AddOrigin(n1, [a])
    self._Freeze(p)
    self.assertEquals(x.Filter(n1), [a])
    self.assertEquals(x.Filter(n2), [a])

  def testAssignToNew(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew()
    n3 = n2.ConnectNew()
    x = p.NewVariable("x")
    ax = x.AddValue("a", source_set=[], where=n1)
    y = ax.AssignToNewVariable("y", n2)
    ay, = y.values
    z = y.AssignToNewVariable("x", n3)
    az, = z.values
    self.assertEquals([v.data for v in y.values], ["a"])
    self.assertEquals([v.data for v in z.values], ["a"])
    self._Freeze(p)
    self.assertTrue(n1.HasCombination([ax]))
    self.assertTrue(n2.HasCombination([ax, ay]))
    self.assertTrue(n3.HasCombination([ax, ay, az]))
    self.assertFalse(n1.HasCombination([ax, ay]))
    self.assertFalse(n2.HasCombination([ax, ay, az]))

  def testAddValues(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew()
    x = p.NewVariable("x")
    ax = x.AddValue("a", source_set=[], where=n1)
    bx = x.AddValue("b", source_set=[], where=n1)
    y = p.NewVariable("y")
    y.AddValues(x, n2)
    ay, by = y.values
    self.assertEquals([v.data for v in x.values], ["a", "b"])
    self.assertEquals([v.data for v in y.values], ["a", "b"])
    self._Freeze(p)
    self.assertTrue(n1.HasCombination([ax]))
    self.assertTrue(n1.HasCombination([bx]))
    self.assertFalse(n1.HasCombination([ay]))
    self.assertFalse(n1.HasCombination([by]))
    self.assertTrue(n2.HasCombination([ay]))
    self.assertTrue(n2.HasCombination([by]))

  def testId(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    x = p.NewVariable("x")
    y = p.NewVariable("y")
    self.assertIsInstance(x.id, int)
    self.assertIsInstance(y.id, int)
    self.assertLess(x.id, y.id)
    self.assertIsInstance(n1.id, int)
    self.assertIsInstance(n2.id, int)
    self.assertLess(n1.id, n2.id)

  def testPrune(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    n4 = n3.ConnectNew("n4")
    n1.ConnectTo(n4)
    x = p.NewVariable("x")
    x.AddValue(1, [], n1)
    x.AddValue(2, [], n2)
    x.AddValue(3, [], n3)
    self.assertSameElements([1], [v.data for v in x.Values(n1)])
    self.assertSameElements([2], [v.data for v in x.Values(n2)])
    self.assertSameElements([3], [v.data for v in x.Values(n3)])
    self.assertSameElements([1, 3], [v.data for v in x.Values(n4)])
    self.assertSameElements([1], x.Data(n1))
    self.assertSameElements([2], x.Data(n2))
    self.assertSameElements([3], x.Data(n3))
    self.assertSameElements([1, 3], x.Data(n4))

  def testProgramFreeze(self):
    p = cfg.Program()
    p.Freeze()
    self.assertRaises(AssertionError, p.NewCFGNode)
    self.assertRaises(AssertionError, p.NewCFGNode, "named")
    self.assertRaises(AssertionError, p.NewCFGNode, name="named")

if __name__ == "__main__":
  unittest.main()
