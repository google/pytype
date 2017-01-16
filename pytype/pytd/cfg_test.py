"""Test for the cfg Python extension module."""

from pytype.pytd import cfg
import unittest


class CFGTest(unittest.TestCase):
  """Test control flow graph creation."""

  def testSimpleGraph(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("foo")
    n2 = n1.ConnectNew("n2")
    n3 = n1.ConnectNew("n3")
    n4 = n3.ConnectNew("n4")
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
    u = p.NewVariable()
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
    u = p.NewVariable()
    data = [1, 2, 3]
    a = u.AddBinding(data, source_set=[], where=node)
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
    u = p.NewVariable()
    a = u.AddBinding(1, source_set=[], where=node)
    b = u.AddBinding(2, source_set=[a], where=node)
    c = u.AddBinding(3, source_set=[a, b], where=node)
    expected_source_sets = [[], [a], [a, b]]
    for binding, expected_source_set in zip([a, b, c], expected_source_sets):
      origin, = binding.origins
      self.assertEquals(origin.where, node)
      source_set, = origin.source_sets
      self.assertItemsEqual(list(source_set), expected_source_set)

  def testVariableSet(self):
    p = cfg.Program()
    node1 = p.NewCFGNode("n1")
    node2 = node1.ConnectNew("n2")
    d = p.NewVariable()
    d.AddBinding("v1", source_set=[], where=node1)
    d.AddBinding("v2", source_set=[], where=node2)
    self.assertEquals(len(d.bindings), 2)

  def testAsciiTree(self):
    p = cfg.Program()
    node1 = p.NewCFGNode("n1")
    node2 = node1.ConnectNew("n2")
    node3 = node2.ConnectNew("n3")
    _ = node3.ConnectNew()
    # Just check sanity. Actual verification of the drawing algorithm is
    # done in utils_test.py.
    self.assertIsInstance(node1.AsciiTree(), str)
    self.assertIsInstance(node1.AsciiTree(forward=True), str)

  def testHasSource(self):
    p = cfg.Program()
    n0, n1, n2 = p.NewCFGNode("n0"), p.NewCFGNode("n1"), p.NewCFGNode("n2")
    u = p.NewVariable()
    u1 = u.AddBinding(0, source_set=[], where=n0)
    v = p.NewVariable()
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
    self.assertIsInstance(p.MergeVariables(n0, []), cfg.Variable)

  def testMergeOneVariable(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    u = p.NewVariable([0], [], n0)
    self.assertIs(p.MergeVariables(n0, [u]), u)
    self.assertIs(p.MergeVariables(n0, [u, u]), u)
    self.assertIs(p.MergeVariables(n0, [u, u, u]), u)

  def testMergeVariables(self):
    p = cfg.Program()
    n0, n1, n2 = p.NewCFGNode("n0"), p.NewCFGNode("n1"), p.NewCFGNode("n2")
    u = p.NewVariable()
    u1 = u.AddBinding(0, source_set=[], where=n0)
    v = p.NewVariable()
    v1 = v.AddBinding(1, source_set=[], where=n1)
    v2 = v.AddBinding(2, source_set=[], where=n1)
    w = p.NewVariable()
    w1 = w.AddBinding(1, source_set=[u1], where=n1)
    w2 = w.AddBinding(3, source_set=[], where=n1)
    vw = p.MergeVariables(n2, [v, w])
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
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    n4 = n2.ConnectNew("n4")
    n5 = n3.ConnectNew("n5")
    n4.ConnectTo(n5)
    n6 = n5.ConnectNew("n6")
    n5.ConnectTo(n6)

    all_x = p.NewVariable()
    x = all_x.AddBinding({}, source_set=[], where=n1)
    ab = p.NewVariable()
    x.data["ab"] = ab
    a = ab.AddBinding("A", source_set=[], where=n3)
    b = ab.AddBinding("B", source_set=[], where=n4)

    p.entrypoint = n1
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
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n1.ConnectNew("n3")
    n4 = p.NewCFGNode("n4")
    n2.ConnectTo(n4)
    n3.ConnectTo(n4)
    x = p.NewVariable()
    y = p.NewVariable()
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

  def testConditionOnStartNode(self):
    # Test that a condition on the initial node is tests.
    # At the time of writing this can not happen in pytype. The test guards
    # against future additions.
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable()
    x_a = x.AddBinding("a", source_set=[], where=n1)
    x_b = x.AddBinding("x", source_set=[], where=n1)
    self.assertTrue(n1.HasCombination([x_a]))
    n1.condition = x_b
    p.InvalidateSolver()
    self.assertFalse(n1.HasCombination([x_a]))

  def testConflictingBindingsFromCondition(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    x = p.NewVariable()
    x_a = x.AddBinding("a", source_set=[], where=n1)
    x_b = x.AddBinding("b", source_set=[], where=n1)
    p.entrypoint = n1
    n2.condition = x_a
    self.assertFalse(n3.HasCombination([x_b]))

  def testConditionsBlock(self):
    p = cfg.Program()
    unreachable_node = p.NewCFGNode("unreachable_node")
    y = p.NewVariable()
    unsatisfiable_binding = y.AddBinding("2", source_set=[],
                                         where=unreachable_node)
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2", condition=unsatisfiable_binding)
    n3 = n2.ConnectNew("n3")
    x = p.NewVariable()
    b1 = x.AddBinding("1", source_set=[], where=n1)
    self.assertFalse(n3.HasCombination([b1]))
    n1.ConnectTo(n3)
    self.assertTrue(n3.HasCombination([b1]))
    self.assertFalse(n2.HasCombination([b1]))

  def testConditionsMultiplePaths(self):
    p = cfg.Program()
    unreachable_node = p.NewCFGNode("unreachable_node")
    y = p.NewVariable()
    unsatisfiable_binding = y.AddBinding("2", source_set=[],
                                         where=unreachable_node)
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2", condition=unsatisfiable_binding)
    n3 = n2.ConnectNew("n3")
    n4 = n2.ConnectNew("n4")
    n4.ConnectTo(n3)
    x = p.NewVariable()
    b1 = x.AddBinding("1", source_set=[], where=n1)
    self.assertFalse(n3.HasCombination([b1]))
    self.assertFalse(n2.HasCombination([b1]))

  def testConditionsNotUsedIfAlternativeExist(self):
    p = cfg.Program()
    unreachable_node = p.NewCFGNode("unreachable_node")
    y = p.NewVariable()
    unsatisfiable_binding = y.AddBinding("2", source_set=[],
                                         where=unreachable_node)
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2", condition=unsatisfiable_binding)
    n3 = n2.ConnectNew("n3")
    x = p.NewVariable()
    b1 = x.AddBinding("1", source_set=[], where=n1)
    self.assertFalse(n3.HasCombination([b1]))

  def testSatisfiableCondition(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable()
    x1 = x.AddBinding("1", source_set=[], where=n1)
    n2 = n1.ConnectNew("n2")
    y = p.NewVariable()
    y2 = y.AddBinding("2", source_set=[], where=n2)
    n3 = n2.ConnectNew("n3", condition=y2)
    n4 = n3.ConnectNew("n4")
    self.assertTrue(n4.HasCombination([x1]))

  def testUnsatisfiableCondition(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable()
    x1 = x.AddBinding("1", source_set=[], where=n1)
    n2 = n1.ConnectNew("n2")
    x2 = x.AddBinding("2", source_set=[], where=n2)
    n3 = n2.ConnectNew("n3", condition=x2)
    n4 = n3.ConnectNew("n4")
    self.assertFalse(n4.HasCombination([x1]))

  def testNoNodeOnAllPaths(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    y = p.NewVariable()
    y1 = y.AddBinding("y", source_set=[], where=n1)
    n3 = n2.ConnectNew("n3")
    n4 = n1.ConnectNew("n4")
    n5 = n4.ConnectNew("n5")
    n3.ConnectTo(n5)
    x = p.NewVariable()
    x1 = x.AddBinding("x", source_set=[], where=n3)
    n2.condition = x1
    n4.condition = x1
    self.assertTrue(n5.HasCombination([y1]))

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
    x = p.NewVariable()
    y = p.NewVariable()
    xa = x.AddBinding("a", source_set=[], where=n2)
    ya = y.AddBinding("a", source_set=[], where=n2)
    xb = x.AddBinding("b", source_set=[], where=n3)
    yb = y.AddBinding("b", source_set=[], where=n3)
    p.entrypoint = n1
    self.assertTrue(n4.HasCombination([xa, ya]))
    self.assertTrue(n4.HasCombination([xb, yb]))
    self.assertFalse(n4.HasCombination([xa, yb]))
    self.assertFalse(n4.HasCombination([xb, ya]))

  def testConflicting(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable()
    a = x.AddBinding("a", source_set=[], where=n1)
    b = x.AddBinding("b", source_set=[], where=n1)
    p.entrypoint = n1
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
    x = p.NewVariable()
    y = p.NewVariable()
    z = p.NewVariable()
    a = x.AddBinding("a", source_set=[], where=n1)
    b = x.AddBinding("b", source_set=[], where=n1)
    ya = y.AddBinding("ya", source_set=[a], where=n2)
    yb = y.AddBinding("yb", source_set=[b], where=n2)
    za = z.AddBinding("za", source_set=[a], where=n2)
    zb = z.AddBinding("zb", source_set=[b], where=n2)
    p.entrypoint = n1
    self.assertTrue(n2.HasCombination([ya, za]))
    self.assertTrue(n2.HasCombination([yb, zb]))
    self.assertFalse(n2.HasCombination([ya, zb]))
    self.assertFalse(n2.HasCombination([yb, za]))

  def testConflictingBindings(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable()
    x_a = x.AddBinding("a", source_set=[], where=n1)
    x_b = x.AddBinding("b", source_set=[], where=n1)
    p.entrypoint = n1
    self.assertTrue(n1.HasCombination([x_a]))
    self.assertTrue(n1.HasCombination([x_b]))
    self.assertFalse(n1.HasCombination([x_a, x_b]))
    self.assertFalse(n2.HasCombination([x_a, x_b]))

  def testMidPoint(self):
    p = cfg.Program()
    x = p.NewVariable()
    y = p.NewVariable()
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x1 = x.AddBinding("1", source_set=[], where=n1)
    y1 = y.AddBinding("1", source_set=[x1], where=n1)
    n2 = n1.ConnectNew("n2")
    x2 = x.AddBinding("2", source_set=[], where=n2)
    n3 = n2.ConnectNew("n3")
    self.assertTrue(n3.HasCombination([y1, x2]))
    self.assertTrue(n3.HasCombination([x2, y1]))

  def testConditionsAreOrdered(self):
    # The error case in this test is non-deterministic. The test tries to verify
    # that the list returned by _PathFinder.FindNodeBackwards is ordered from
    # child to parent.
    # The error case would be a random order or the reverse order.
    # To guarantee that this test is working go to FindNodeBackwards and reverse
    # the order of self._on_path before generating the returned list.
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x1 = p.NewVariable().AddBinding("1", source_set=[], where=n1)
    n2 = n1.ConnectNew("n2", condition=p.NewVariable().AddBinding(
        "1", source_set=[], where=n1))
    n3 = n2.ConnectNew("n3", condition=p.NewVariable().AddBinding(
        "1", source_set=[], where=n2))
    n4 = n3.ConnectNew("n3", condition=p.NewVariable().AddBinding(
        "1", source_set=[], where=n3))
    # Strictly speaking n1, n2 and n3 would be enough to expose errors. n4 is
    # added to increase the chance of a failure if the order is random.
    self.assertTrue(n4.HasCombination([x1]))

  def testSameNodeOrigin(self):
    # [n1] x = a or b; y = x
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable()
    y = p.NewVariable()
    xa = x.AddBinding("xa", source_set=[], where=n1)
    xb = x.AddBinding("xb", source_set=[], where=n1)
    ya = y.AddBinding("ya", source_set=[xa], where=n1)
    yb = y.AddBinding("yb", source_set=[xb], where=n1)
    p.entrypoint = n1
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
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    x, y, z = "x", "y", "z"
    variable = p.NewVariable(bindings=[x, y],
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
    u = p.NewVariable()
    a1 = u.AddBinding(1, source_set=[], where=n1)
    a2 = u.AddBinding(2, source_set=[], where=n1)
    a3 = u.AddBinding(3, source_set=[], where=n1)
    a4 = u.AddBinding(4, source_set=[], where=n1)
    self.assertSameElements([a1, a2, a3, a4], n1.bindings)

  def testProgram(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    u1 = p.NewVariable()
    u2 = p.NewVariable()
    a11 = u1.AddBinding(11, source_set=[], where=n1)
    a12 = u1.AddBinding(12, source_set=[], where=n2)
    a21 = u2.AddBinding(21, source_set=[], where=n1)
    a22 = u2.AddBinding(22, source_set=[], where=n2)
    self.assertSameElements([n1, n2], p.cfg_nodes)
    self.assertSameElements([u1, u2], p.variables)
    self.assertSameElements([a11, a21], n1.bindings)
    self.assertSameElements([a12, a22], n2.bindings)

  def testEntryPoint(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable()
    a = x.AddBinding("a", source_set=[], where=n1)
    a = x.AddBinding("b", source_set=[], where=n2)
    p.entrypoint = n1
    self.assertTrue(n2.HasCombination([a]))

  def testNonFrozenSolving(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable()
    a = x.AddBinding("a", source_set=[], where=n1)
    a = x.AddBinding("b", source_set=[], where=n2)
    p.entrypoint = n1
    self.assertTrue(n2.HasCombination([a]))

  def testFilter2(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = p.NewCFGNode("n2")
    n1.ConnectTo(n2)
    x = p.NewVariable()
    a = x.AddBinding("a", source_set=[], where=n2)
    p.entrypoint = n1
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [a])

  def testHiddenConflict1(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n1.ConnectNew("n3")
    x = p.NewVariable()
    y = p.NewVariable()
    z = p.NewVariable()
    x_a = x.AddBinding("a", source_set=[], where=n1)
    x_b = x.AddBinding("b", source_set=[], where=n1)
    y_a = y.AddBinding("a", source_set=[x_a], where=n1)
    y_b = y.AddBinding("b", source_set=[x_b], where=n2)
    z_ab1 = z.AddBinding("ab1", source_set=[x_a, x_b], where=n3)
    z_ab2 = z.AddBinding("ab2", source_set=[y_a, x_b], where=n3)
    z_ab3 = z.AddBinding("ab3", source_set=[y_b, x_a], where=n3)
    z_ab4 = z.AddBinding("ab4", source_set=[y_a, y_b], where=n3)
    p.entrypoint = n1
    self.assertFalse(n2.HasCombination([y_a, x_b]))
    self.assertFalse(n2.HasCombination([y_b, x_a]))
    self.assertFalse(n3.HasCombination([z_ab1]))
    self.assertFalse(n3.HasCombination([z_ab2]))
    self.assertFalse(n3.HasCombination([z_ab3]))
    self.assertFalse(n3.HasCombination([z_ab4]))

  def testHiddenConflict2(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable()
    y = p.NewVariable()
    x_a = x.AddBinding("a", source_set=[], where=n1)
    x_b = x.AddBinding("b", source_set=[], where=n1)
    y_b = y.AddBinding("b", source_set=[x_b], where=n1)
    p.entrypoint = n1
    self.assertFalse(n2.HasCombination([y_b, x_a]))

  def testEmptyBinding(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable()
    a = x.AddBinding("a")
    p.entrypoint = n1
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [])
    a.AddOrigin(n2, [])
    p.entrypoint = n1
    self.assertEquals(x.Filter(n1), [])
    self.assertEquals(x.Filter(n2), [a])
    a.AddOrigin(n1, [a])
    p.entrypoint = n1
    self.assertEquals(x.Filter(n1), [a])
    self.assertEquals(x.Filter(n2), [a])

  def testAssignToNew(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    x = p.NewVariable()
    ax = x.AddBinding("a", source_set=[], where=n1)
    y = ax.AssignToNewVariable(n2)
    ay, = y.bindings
    z = y.AssignToNewVariable(n3)
    az, = z.bindings
    self.assertEquals([v.data for v in y.bindings], ["a"])
    self.assertEquals([v.data for v in z.bindings], ["a"])
    p.entrypoint = n1
    self.assertTrue(n1.HasCombination([ax]))
    self.assertTrue(n2.HasCombination([ax, ay]))
    self.assertTrue(n3.HasCombination([ax, ay, az]))
    self.assertFalse(n1.HasCombination([ax, ay]))
    self.assertFalse(n2.HasCombination([ax, ay, az]))

  def testPasteVariable(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    x = p.NewVariable()
    ax = x.AddBinding("a", source_set=[], where=n1)
    bx = x.AddBinding("b", source_set=[], where=n1)
    y = p.NewVariable()
    y.PasteVariable(x, n2)
    ay, by = y.bindings
    self.assertEquals([v.data for v in x.bindings], ["a", "b"])
    self.assertEquals([v.data for v in y.bindings], ["a", "b"])
    p.entrypoint = n1
    self.assertTrue(n1.HasCombination([ax]))
    self.assertTrue(n1.HasCombination([bx]))
    self.assertFalse(n1.HasCombination([ay]))
    self.assertFalse(n1.HasCombination([by]))
    self.assertTrue(n2.HasCombination([ay]))
    self.assertTrue(n2.HasCombination([by]))

  def testPasteAtSameNode(self):
    p = cfg.Program()
    n1 = p.NewCFGNode("n1")
    x = p.NewVariable()
    x.AddBinding("a", source_set=[], where=n1)
    x.AddBinding("b", source_set=[], where=n1)
    y = p.NewVariable()
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
    x = p.NewVariable()
    y = p.NewVariable()
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
    x = p.NewVariable()
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

  def testVariableCallback(self):
    counters = [0, 0]
    def callback1():
      counters[0] += 1
    def callback2():
      counters[1] += 1
    p = cfg.Program()
    x = p.NewVariable()
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

  def testInvalidateSolver(self):
    p = cfg.Program()
    x = p.NewVariable()
    n1 = p.NewCFGNode("n1")
    self.assertIsNone(p.solver)
    n1.HasCombination([])
    self.assertIsNotNone(p.solver)
    n2 = p.NewCFGNode("n2")
    self.assertIsNone(p.solver)
    n2.HasCombination([])
    self.assertIsNotNone(p.solver)
    x = p.NewVariable()  # a new variable by itself doesn't change the CFG
    self.assertIsNotNone(p.solver)
    a = x.AddBinding("a")
    a.AddOrigin(n1, {})
    self.assertIsNone(p.solver)
    n2.HasCombination([a])
    self.assertIsNotNone(p.solver)
    x = p.NewVariable(["b"], [a], n2)
    self.assertIsNone(p.solver)


if __name__ == "__main__":
  unittest.main()
