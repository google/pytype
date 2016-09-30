"""Test for the cfg Python extension module."""

from pytype.pytd import cfg
import unittest


class CFGTest(unittest.TestCase):
  """Test control flow graph creation."""

  def testSimpleGraph(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("foo")
    n2 = n1.ConnectNew()
    n3 = n1.ConnectNew()
    n4 = n3.ConnectNew()
    self.assertEquals("<0>foo", n1.Label())
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

  def testBindingBinding(self):
    p = cfg.Program()
    node = p.NewCFGNode()
    u = p.NewVariable("v")
    v1 = u.AddBinding(None, source_set=[], where=node)
    v2 = u.AddBinding(u"data", source_set=[], where=node)
    v3 = u.AddBinding({1: 2}, source_set=[], where=node)
    self.assertEquals(v1.data, None)
    self.assertEquals(v2.data, u"data")
    self.assertEquals(v3.data, {1: 2})
    self.assertEquals("<binding of variable 0 to data %d>" % id(v3.data),
                      str(v3))

  def testGetAttro(self):
    p = cfg.Program()
    node = p.NewCFGNode()
    u = p.NewVariable("foo")
    data = [1, 2, 3]
    a = u.AddBinding(data, source_set=[], where=node)
    self.assertEquals(a.variable.name, "foo")
    self.assertEquals(a.variable.bindings, [a])
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
    a = u.AddBinding(1, source_set=[], where=node)
    b = u.AddBinding(2, source_set=[a], where=node)
    c = u.AddBinding(3, source_set=[a, b], where=node)
    expected_source_sets = [[], [a], [a, b]]
    for binding, expected_source_set in zip([a, b, c], expected_source_sets):
      origin, = binding.origins
      self.assertEquals(origin.where, node)
      source_set, = origin.source_sets
      self.assertItemsEqual(list(source_set), expected_source_set)

  def testBindingName(self):
    p = cfg.Program()
    u = p.NewVariable("foo")
    self.assertEquals(u.name, "foo")
    u.name = "bar"
    self.assertEquals(u.name, "bar")

  def _Freeze(self, program, entrypoint):
    program.entrypoint = entrypoint
    program.Freeze()

  def testVariableSet(self):
    p = cfg.Program()
    node1 = p.NewCFGNode()
    node2 = node1.ConnectNew()
    d = p.NewVariable("d")
    d.AddBinding("v1", source_set=[], where=node1)
    d.AddBinding("v2", source_set=[], where=node2)
    self.assertEquals(len(d.bindings), 2)

  def testAsciiTree(self):
    p = cfg.Program()
    node1 = p.NewCFGNode()
    node2 = node1.ConnectNew()
    node3 = node2.ConnectNew()
    _ = node3.ConnectNew()
    # Just check sanity. Actual verification of the drawing algorithm is
    # done in utils_test.py.
    self.assertIsInstance(node1.AsciiTree(), str)
    self.assertIsInstance(node1.AsciiTree(forward=True), str)

  def testHasSource(self):
    p = cfg.Program()
    n0, n1, n2 = p.NewCFGNode("n0"), p.NewCFGNode("n1"), p.NewCFGNode("n2")
    u = p.NewVariable("u")
    u1 = u.AddBinding(0, source_set=[], where=n0)
    v = p.NewVariable("v")
    v1 = v.AddBinding(1, source_set=[], where=n1)
    v2 = v.AddBinding(2, source_set=[u1], where=n1)
    v3a = v.AddBinding(3, source_set=[], where=n1)
    v3b = v.AddBinding(3, source_set=[u1], where=n2)
    self.assertEquals(v3a, v3b)
    v3 = v3a
    self.assertTrue(v1.HasSource(v1))
    self.assertTrue(v2.HasSource(v2))
    self.assertTrue(v3.HasSource(v3))
    self.assertFalse(v1.HasSource(u1))
    self.assertTrue(v2.HasSource(u1))
    self.assertTrue(v3.HasSource(u1))

  def testMergeZeroVariables(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    self.assertIsInstance(p.MergeVariables(n0, "u", []), cfg.Variable)

  def testMergeOneVariable(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    u = p.NewVariable("u", [0], [], n0)
    self.assertIs(p.MergeVariables(n0, "u", [u]), u)
    self.assertIs(p.MergeVariables(n0, "u", [u, u]), u)
    self.assertIs(p.MergeVariables(n0, "u", [u, u, u]), u)

  def testMergeVariables(self):
    p = cfg.Program()
    n0, n1, n2 = p.NewCFGNode("n0"), p.NewCFGNode("n1"), p.NewCFGNode("n2")
    u = p.NewVariable("u")
    u1 = u.AddBinding(0, source_set=[], where=n0)
    v = p.NewVariable("v")
    v1 = v.AddBinding(1, source_set=[], where=n1)
    v2 = v.AddBinding(2, source_set=[], where=n1)
    w = p.NewVariable("w")
    w1 = w.AddBinding(1, source_set=[u1], where=n1)
    w2 = w.AddBinding(3, source_set=[], where=n1)
    vw = p.MergeVariables(n2, "vw", [v, w])
    self.assertItemsEqual(vw.data, [1, 2, 3])
    val1, = [v for v in vw.bindings if v.data == 1]
    self.assertTrue(val1.HasSource(u1))

  def testFilter1(self):
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
    x = all_x.AddBinding({}, source_set=[], where=n1)
    ab = p.NewVariable("x.ab")
    x.data["ab"] = ab
    a = ab.AddBinding("A", source_set=[], where=n3)
    b = ab.AddBinding("B", source_set=[], where=n4)

    self._Freeze(p, entrypoint=n1)
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

  def testCanHaveCombination(self):
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = n1.ConnectNew()
    n3 = n1.ConnectNew()
    n4 = p.NewCFGNode()
    n2.ConnectTo(n4)
    n3.ConnectTo(n4)
    x = p.NewVariable("x")
    y = p.NewVariable("y")
    x1 = x.AddBinding("1", source_set=[], where=n2)
    y2 = y.AddBinding("2", source_set=[], where=n3)
    self.assertTrue(n4.CanHaveCombination([x1, y2]))
    self.assertTrue(n4.CanHaveCombination([x1]))
    self.assertTrue(n4.CanHaveCombination([y2]))
    self.assertTrue(n3.CanHaveCombination([y2]))
    self.assertTrue(n2.CanHaveCombination([x1]))
    self.assertTrue(n1.CanHaveCombination([]))
    self.assertFalse(n1.CanHaveCombination([x1]))
    self.assertFalse(n1.CanHaveCombination([y2]))
    self.assertFalse(n2.CanHaveCombination([x1, y2]))
    self.assertFalse(n3.CanHaveCombination([x1, y2]))

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
    xa = x.AddBinding("a", source_set=[], where=n2)
    ya = y.AddBinding("a", source_set=[], where=n2)
    xb = x.AddBinding("b", source_set=[], where=n3)
    yb = y.AddBinding("b", source_set=[], where=n3)
    self._Freeze(p, entrypoint=n1)
    self.assertTrue(n4.HasCombination([xa, ya]))
    self.assertTrue(n4.HasCombination([xb, yb]))
    self.assertFalse(n4.HasCombination([xa, yb]))
    self.assertFalse(n4.HasCombination([xb, ya]))

  def testConflicting(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable("x")
    a = x.AddBinding("a", source_set=[], where=n1)
    b = x.AddBinding("b", source_set=[], where=n1)
    self._Freeze(p, entrypoint=n1)
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
    a = x.AddBinding("a", source_set=[], where=n1)
    b = x.AddBinding("b", source_set=[], where=n1)
    ya = y.AddBinding("ya", source_set=[a], where=n2)
    yb = y.AddBinding("yb", source_set=[b], where=n2)
    za = z.AddBinding("za", source_set=[a], where=n2)
    zb = z.AddBinding("zb", source_set=[b], where=n2)
    self._Freeze(p, entrypoint=n1)
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
    xa = x.AddBinding("xa", source_set=[], where=n1)
    xb = x.AddBinding("xb", source_set=[], where=n1)
    ya = y.AddBinding("ya", source_set=[xa], where=n1)
    yb = y.AddBinding("yb", source_set=[xb], where=n1)
    self._Freeze(p, entrypoint=n1)
    self.assertTrue(n1.HasCombination([xa]))
    self.assertTrue(n1.HasCombination([xb]))
    self.assertTrue(n1.HasCombination([xa, ya]))
    self.assertTrue(n1.HasCombination([xb, yb]))
    # We don't check the other two combinations, because within one CFG node,
    # bindings are treated as having any order, so the other combinations
    # are possible, too:
    # n1.HasCombination([xa, yb]) == True (because x = b; y = x; x = a)
    # n1.HasCombination([xb, ya]) == True (because x = a; y = x; x = b)

  def testNewVariable(self):
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = p.NewCFGNode()
    x, y, z = "x", "y", "z"
    variable = p.NewVariable("xyz",
                             bindings=[x, y],
                             source_set=[],
                             where=n1)
    variable.AddBinding(z, source_set=variable.bindings, where=n2)
    self.assertSameElements([x, y, z], [v.data for v in variable.bindings])
    self.assertTrue(any(len(e.origins) for e in variable.bindings))

  def testNodeBindings(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("node1")
    n2 = n1.ConnectNew("node2")
    self.assertEquals(n1.name, "node1")
    self.assertEquals(n2.name, "node2")
    u = p.NewVariable("var")
    a1 = u.AddBinding(1, source_set=[], where=n1)
    a2 = u.AddBinding(2, source_set=[], where=n1)
    a3 = u.AddBinding(3, source_set=[], where=n1)
    a4 = u.AddBinding(4, source_set=[], where=n1)
    self.assertSameElements([a1, a2, a3, a4], n1.bindings)

  def testProgram(self):
    p = cfg.Program()
    n1 = p.NewCFGNode()
    n2 = n1.ConnectNew()
    u1 = p.NewVariable("var1")
    u2 = p.NewVariable("var2")
    self.assertEquals(u1.name, "var1")
    self.assertEquals(u2.name, "var2")
    a11 = u1.AddBinding(11, source_set=[], where=n1)
    a12 = u1.AddBinding(12, source_set=[], where=n2)
    a21 = u2.AddBinding(21, source_set=[], where=n1)
    a22 = u2.AddBinding(22, source_set=[], where=n2)
    self.assertSameElements([n1, n2], p.cfg_nodes)
    self.assertSameElements([u1, u2], p.variables)
    self.assertSameElements([a11, a21], n1.bindings)
    self.assertSameElements([a12, a22], n2.bindings)

  def testDisconnected(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    self.assertRaises(AssertionError, self._Freeze, p, entrypoint=n1)
    self.assertRaises(AssertionError, self._Freeze, p, entrypoint=n2)

  def testEntryPoint(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable("x")
    a = x.AddBinding("a", source_set=[], where=n1)
    a = x.AddBinding("b", source_set=[], where=n2)
    self._Freeze(p, entrypoint=n1)
    self.assertTrue(n2.HasCombination([a]))

  def testFilter2(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    n1.ConnectTo(n2)
    x = p.NewVariable("x")
    a = x.AddBinding("a", source_set=[], where=n2)
    self._Freeze(p, entrypoint=n1)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [a])

  def testEmptyBinding(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew()
    x = p.NewVariable("x")
    a = x.AddBinding("a")
    self._Freeze(p, entrypoint=n1)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [])
    a.AddOrigin(n2, [])
    self._Freeze(p, entrypoint=n1)
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [a])
    a.AddOrigin(n1, [a])
    self._Freeze(p, entrypoint=n1)
    self.assertEquals(x.Filter(n1), [a])
    self.assertEquals(x.Filter(n2), [a])

  def testAssignToNew(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew()
    n3 = n2.ConnectNew()
    x = p.NewVariable("x")
    ax = x.AddBinding("a", source_set=[], where=n1)
    y = ax.AssignToNewVariable("y", n2)
    ay, = y.bindings
    z = y.AssignToNewVariable("x", n3)
    az, = z.bindings
    self.assertEquals([v.data for v in y.bindings], ["a"])
    self.assertEquals([v.data for v in z.bindings], ["a"])
    self._Freeze(p, entrypoint=n1)
    self.assertTrue(n1.HasCombination([ax]))
    self.assertTrue(n2.HasCombination([ax, ay]))
    self.assertTrue(n3.HasCombination([ax, ay, az]))
    self.assertFalse(n1.HasCombination([ax, ay]))
    self.assertFalse(n2.HasCombination([ax, ay, az]))

  def testPasteVariable(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew()
    x = p.NewVariable("x")
    ax = x.AddBinding("a", source_set=[], where=n1)
    bx = x.AddBinding("b", source_set=[], where=n1)
    y = p.NewVariable("y")
    y.PasteVariable(x, n2)
    ay, by = y.bindings
    self.assertEquals([v.data for v in x.bindings], ["a", "b"])
    self.assertEquals([v.data for v in y.bindings], ["a", "b"])
    self._Freeze(p, entrypoint=n1)
    self.assertTrue(n1.HasCombination([ax]))
    self.assertTrue(n1.HasCombination([bx]))
    self.assertFalse(n1.HasCombination([ay]))
    self.assertFalse(n1.HasCombination([by]))
    self.assertTrue(n2.HasCombination([ay]))
    self.assertTrue(n2.HasCombination([by]))

  def testPasteAtSameNode(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable("x")
    x.AddBinding("a", source_set=[], where=n1)
    x.AddBinding("b", source_set=[], where=n1)
    y = p.NewVariable("y")
    y.PasteVariable(x, n1)
    ay, _ = y.bindings
    self.assertEquals([v.data for v in x.bindings], ["a", "b"])
    self.assertEquals([v.data for v in y.bindings], ["a", "b"])
    o, = ay.origins
    self.assertItemsEqual([cfg.SourceSet([])], o.source_sets)
    o, = ay.origins
    self.assertItemsEqual([cfg.SourceSet([])], o.source_sets)

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
    x.AddBinding(1, [], n1)
    x.AddBinding(2, [], n2)
    x.AddBinding(3, [], n3)
    self.assertSameElements([1], [v.data for v in x.Bindings(n1)])
    self.assertSameElements([2], [v.data for v in x.Bindings(n2)])
    self.assertSameElements([3], [v.data for v in x.Bindings(n3)])
    self.assertSameElements([1, 3], [v.data for v in x.Bindings(n4)])
    self.assertSameElements([1], x.Data(n1))
    self.assertSameElements([2], x.Data(n2))
    self.assertSameElements([3], x.Data(n3))
    self.assertSameElements([1, 3], x.Data(n4))

  def testProgramFreeze(self):
    p = cfg.Program()
    n = p.NewCFGNode("n")
    self._Freeze(p, entrypoint=n)
    self.assertRaises(AssertionError, p.NewCFGNode)
    self.assertRaises(AssertionError, p.NewCFGNode, "named")
    self.assertRaises(AssertionError, p.NewCFGNode, name="named")

  def testVariableCallback(self):
    counters = [0, 0]
    def callback1():
      counters[0] += 1
    def callback2():
      counters[1] += 1
    p = cfg.Program()
    x = p.NewVariable("x")
    x.RegisterChangeListener(callback1)
    x.AddBinding("a")
    self.assertListEqual(counters, [1, 0])
    x.RegisterChangeListener(callback2)
    x.AddBinding("b")
    self.assertListEqual(counters, [2, 1])
    x.AddBinding("a")  # Duplicate binding; callbacks should not be triggered
    self.assertListEqual(counters, [2, 1])
    x.UnregisterChangeListener(callback1)
    x.AddBinding("c")
    self.assertListEqual(counters, [2, 2])

if __name__ == "__main__":
  unittest.main()
