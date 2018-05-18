"""Tests for the additional CFG utilities."""

import itertools

from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils
import unittest


class CFGUtilTest(unittest.TestCase):
  """Test CFG utilities."""

  def testMergeZeroVariables(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    self.assertIsInstance(cfg_utils.merge_variables(p, n0, []), cfg.Variable)

  def testMergeOneVariable(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    u = p.NewVariable([0], [], n0)
    self.assertIs(cfg_utils.merge_variables(p, n0, [u]), u)
    self.assertIs(cfg_utils.merge_variables(p, n0, [u, u]), u)
    self.assertIs(cfg_utils.merge_variables(p, n0, [u, u, u]), u)

  def testMergeVariables(self):
    p = cfg.Program()
    n0, n1, n2 = p.NewCFGNode("n0"), p.NewCFGNode("n1"), p.NewCFGNode("n2")
    u = p.NewVariable()
    u1 = u.AddBinding(0, source_set=[], where=n0)
    v = p.NewVariable()
    v.AddBinding(1, source_set=[], where=n1)
    v.AddBinding(2, source_set=[], where=n1)
    w = p.NewVariable()
    w.AddBinding(1, source_set=[u1], where=n1)
    w.AddBinding(3, source_set=[], where=n1)
    vw = cfg_utils.merge_variables(p, n2, [v, w])
    self.assertItemsEqual(vw.data, [1, 2, 3])
    val1, = [v for v in vw.bindings if v.data == 1]
    self.assertTrue(val1.HasSource(u1))

  def testMergeBindings(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    u = p.NewVariable()
    u1 = u.AddBinding("1", source_set=[], where=n0)
    v2 = u.AddBinding("2", source_set=[], where=n0)
    w1 = cfg_utils.merge_bindings(p, None, [u1, v2])
    w2 = cfg_utils.merge_bindings(p, n0, [u1, v2])
    self.assertItemsEqual(w1.data, ["1", "2"])
    self.assertItemsEqual(w2.data, ["1", "2"])

  def _create_nodes(self, node_id, node, num_nodes):
    """Create a chain of nodes. Used by _create_program_nodes.

    Args:
      node_id: The starting node id.
      node: The starting node.
      num_nodes: The number of nodes to create.

    Returns:
      A tuple of the next available node id, the last node created, and a list
      of all the nodes created.
    """
    nodes = []
    for _ in range(num_nodes):
      node = node.ConnectNew("n%d" % node_id)
      node_id += 1
      nodes.append(node)
    return node_id, node, nodes

  # Unpacking all_nodes confuses pylint because the list looks empty.
  # pylint: disable=unbalanced-tuple-unpacking
  def _create_program_nodes(self, p, num_module_nodes, *num_function_nodes):
    """Create nodes for a dummy program.

    Args:
      p: A cfg.Program.
      num_module_nodes: The number of nodes to create between the root node and
        the analyze node.
      *num_function_nodes: For every function in the program, the number of
        nodes in that function.

    Returns:
      A list of all the created nodes, except root and analyze.
    """
    node = p.NewCFGNode("root")
    all_nodes = []
    node_id = 1
    node_id, node, nodes = self._create_nodes(node_id, node, num_module_nodes)
    all_nodes.extend(nodes)
    analyze = node.ConnectNew("analyze")
    for num_nodes in num_function_nodes:
      node_id, node, nodes = self._create_nodes(node_id, analyze, num_nodes)
      all_nodes.extend(nodes)
      node.ConnectTo(analyze)
    return all_nodes


class DummyValue(object):
  """A class with a 'parameters' function, for testing cartesian products."""

  def __init__(self, index):
    self.index = index
    self._parameters = []

  def set_parameters(self, parameters):
    self._parameters = parameters

  def unique_parameter_values(self):
    return [param.bindings for param in self._parameters]

  def __repr__(self):
    return "x%d" % self.index


class VariableProductTest(unittest.TestCase):
  """Test variable-product utilities."""

  def setUp(self):
    self.prog = cfg.Program()
    self.current_location = self.prog.NewCFGNode()

  def testComplexityLimit(self):
    limit = cfg_utils.ComplexityLimit(5)
    limit.inc()
    limit.inc(2)
    limit.inc()
    self.assertRaises(cfg_utils.TooComplexError, limit.inc)

  def testVariableProduct(self):
    u1 = self.prog.NewVariable([1, 2], [], self.current_location)
    u2 = self.prog.NewVariable([3, 4], [], self.current_location)
    product = cfg_utils.variable_product([u1, u2])
    pairs = [[a.data for a in d]
             for d in product]
    self.assertItemsEqual(pairs, [
        [1, 3],
        [1, 4],
        [2, 3],
        [2, 4],
    ])

  def testDeepVariableProductRaises(self):
    x1, x2 = [DummyValue(i + 1) for i in range(2)]
    v1 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v2 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v3 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v4 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v5 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v6 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v7 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v8 = self.prog.NewVariable([x1, x2], [], self.current_location)
    self.assertRaises(cfg_utils.TooComplexError,
                      cfg_utils.deep_variable_product,
                      [v1, v2, v3, v4, v5, v6, v7, v8],
                      256)

  def testDeepVariableProductRaises2(self):
    x1, x2, x3, x4 = [DummyValue(i + 1) for i in range(4)]
    v1 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v2 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v3 = self.prog.NewVariable([x3, x4], [], self.current_location)
    v4 = self.prog.NewVariable([x3, x4], [], self.current_location)
    x1.set_parameters([v3])
    x2.set_parameters([v4])
    self.assertRaises(cfg_utils.TooComplexError,
                      cfg_utils.deep_variable_product, [v1, v2], 4)

  def testVariableProductDictRaises(self):
    values = [DummyValue(i + 1) for i in range(4)]
    v1 = self.prog.NewVariable(values, [], self.current_location)
    v2 = self.prog.NewVariable(values, [], self.current_location)
    v3 = self.prog.NewVariable(values, [], self.current_location)
    v4 = self.prog.NewVariable(values, [], self.current_location)
    variabledict = {"v1": v1, "v2": v2, "v3": v3, "v4": v4}
    self.assertRaises(cfg_utils.TooComplexError,
                      cfg_utils.variable_product_dict, variabledict, 4)

  def testDeepVariableProduct(self):
    x1, x2, x3, x4, x5, x6 = [DummyValue(i + 1) for i in range(6)]
    v1 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v2 = self.prog.NewVariable([x3], [], self.current_location)
    v3 = self.prog.NewVariable([x4, x5], [], self.current_location)
    v4 = self.prog.NewVariable([x6], [], self.current_location)
    x1.set_parameters([v2, v3])
    product = cfg_utils.deep_variable_product([v1, v4])
    rows = [{a.data for a in row}
            for row in product]
    self.assertItemsEqual(rows, [
        {x1, x3, x4, x6},
        {x1, x3, x5, x6},
        {x2, x6},
    ])

  def testDeepVariableProductWithEmptyVariables(self):
    x1 = DummyValue(1)
    v1 = self.prog.NewVariable([x1], [], self.current_location)
    v2 = self.prog.NewVariable([], [], self.current_location)
    x1.set_parameters([v2])
    product = cfg_utils.deep_variable_product([v1])
    rows = [{a.data for a in row}
            for row in product]
    self.assertItemsEqual(rows, [{x1}])

  def testDeepVariableProductWithEmptyTopLayer(self):
    x1 = DummyValue(1)
    v1 = self.prog.NewVariable([x1], [], self.current_location)
    v2 = self.prog.NewVariable([], [], self.current_location)
    product = cfg_utils.deep_variable_product([v1, v2])
    rows = [{a.data for a in row}
            for row in product]
    self.assertItemsEqual(rows, [{x1}])

  def testDeepVariableProductWithCycle(self):
    x1, x2, x3, x4, x5, x6 = [DummyValue(i + 1) for i in range(6)]
    v1 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v2 = self.prog.NewVariable([x3], [], self.current_location)
    v3 = self.prog.NewVariable([x4, x5], [], self.current_location)
    v4 = self.prog.NewVariable([x6], [], self.current_location)
    x1.set_parameters([v2, v3])
    x5.set_parameters([v1])
    product = cfg_utils.deep_variable_product([v1, v4])
    rows = [{a.data for a in row}
            for row in product]
    self.assertItemsEqual(rows, [
        {x1, x3, x4, x6},
        {x1, x2, x3, x5, x6},
        {x1, x3, x5, x6},
        {x2, x6},
    ])

  def testVariableProductDict(self):
    u1 = self.prog.NewVariable([1, 2], [], self.current_location)
    u2 = self.prog.NewVariable([3, 4], [], self.current_location)
    product = cfg_utils.variable_product_dict({"a": u1, "b": u2})
    pairs = [{k: a.data for k, a in d.items()} for d in product]
    self.assertItemsEqual(pairs, [
        {"a": 1, "b": 3},
        {"a": 1, "b": 4},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
    ])


class Node(object):
  """A graph node, for testing topological sorting."""

  def __init__(self, name, *incoming):
    self.name = name
    self.outgoing = []
    self.incoming = list(incoming)
    for n in incoming:
      n.outgoing.append(self)

  def connect_to(self, other_node):
    self.outgoing.append(other_node)
    other_node.incoming.append(self)

  def __repr__(self):
    return "Node(%s)" % self.name


class GraphUtilTest(unittest.TestCase):
  """Test abstract graph utilities."""

  def setUp(self):
    self.prog = cfg.Program()

  def testComputePredecessors(self):
    # n7      n6
    #  ^      ^
    #  |      |
    #  |      |
    # n1 ---> n20 --> n3 --> n5 -+
    #         | ^            ^   |
    #         | |            |   |
    #         | +------------|---+
    #         v              |
    #         n4 ------------+
    n1 = self.prog.NewCFGNode("n1")
    n20 = n1.ConnectNew("n20")
    n3 = n20.ConnectNew("n3")
    n4 = n20.ConnectNew("n4")
    n5 = n3.ConnectNew("n5")
    n6 = n20.ConnectNew("n6")
    n7 = n1.ConnectNew("n7")
    n3.ConnectTo(n5)
    n4.ConnectTo(n5)
    n5.ConnectTo(n20)

    # Intentionally pick a non-root as nodes[0] to verify that the graph
    # will still be fully explored.
    nodes = [n7, n1, n20, n3, n4, n5, n6]
    r = cfg_utils.compute_predecessors(nodes)
    self.assertItemsEqual(r[n1], {n1})
    self.assertItemsEqual(r[n20], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n3], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n4], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n5], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n6], {n1, n20, n3, n4, n5, n6})
    self.assertItemsEqual(r[n7], {n1, n7})

  def testOrderNodes0(self):
    order = cfg_utils.order_nodes([])
    self.assertItemsEqual(order, [])

  def testOrderNodes1(self):
    # n1 --> n2
    n1 = self.prog.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    order = cfg_utils.order_nodes([n1, n2])
    self.assertItemsEqual([n1, n2], order)

  def testOrderNodes2(self):
    # n1   n2(dead)
    n1 = self.prog.NewCFGNode("n1")
    n2 = self.prog.NewCFGNode("n2")
    order = cfg_utils.order_nodes([n1, n2])
    self.assertItemsEqual([n1], order)

  def testOrderNodes3(self):
    # n1 --> n2 --> n3
    # ^             |
    # +-------------+
    n1 = self.prog.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    n3.ConnectTo(n1)
    order = cfg_utils.order_nodes([n1, n2, n3])
    self.assertItemsEqual([n1, n2, n3], order)

  def testOrderNodes4(self):
    # n1 --> n3 --> n2
    # ^      |
    # +------+
    n1 = self.prog.NewCFGNode("n1")
    n3 = n1.ConnectNew("n3")
    n2 = n3.ConnectNew("n2")
    n3.ConnectTo(n1)
    order = cfg_utils.order_nodes([n1, n2, n3])
    self.assertItemsEqual([n1, n3, n2], order)

  def testOrderNodes5(self):
    # n1 --> n3 --> n2
    # ^      |
    # +------+      n4(dead)
    n1 = self.prog.NewCFGNode("n1")
    n3 = n1.ConnectNew("n3")
    n2 = n3.ConnectNew("n2")
    n3.ConnectTo(n1)
    n4 = self.prog.NewCFGNode("n4")
    order = cfg_utils.order_nodes([n1, n2, n3, n4])
    self.assertItemsEqual([n1, n3, n2], order)

  def testOrderNodes6(self):
    #  +-------------------+
    #  |                   v
    # n1 --> n2 --> n3 --> n5
    #        ^      |
    #        +------n4
    n1 = self.prog.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    n4 = n3.ConnectNew("n4")
    n4.ConnectTo(n2)
    n5 = n3.ConnectNew("n5")
    n1.ConnectTo(n5)
    order = cfg_utils.order_nodes([n1, n5, n4, n3, n2])
    self.assertItemsEqual([n1, n2, n3, n4, n5], order)

  def testOrderNodes7(self):
    #  +---------------------------------+
    #  |                                 v
    # n1 --> n2 --> n3 --> n4 --> n5 --> n6
    #        ^      |      ^      |
    #        |      v      |      v
    #        +------n7     +------n8
    n1 = self.prog.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    n4 = n3.ConnectNew("n4")
    n5 = n4.ConnectNew("n5")
    n6 = n5.ConnectNew("n6")
    n7 = n3.ConnectNew("n7")
    n7.ConnectTo(n2)
    n8 = n5.ConnectNew("n8")
    n8.ConnectTo(n4)
    n1.ConnectTo(n6)
    order = cfg_utils.order_nodes([n1, n2, n3, n4, n5, n6, n7, n8])
    self.assertItemsEqual([n1, n2, n3, n7, n4, n5, n8, n6], order)

  def testTopologicalSort(self):
    n1 = Node("1")
    n2 = Node("2", n1)
    n3 = Node("3", n2)
    n4 = Node("4", n2, n3)
    for permutation in itertools.permutations([n1, n2, n3, n4]):
      self.assertEqual(list(cfg_utils.topological_sort(permutation)),
                       [n1, n2, n3, n4])

  def testTopologicalSort2(self):
    n1 = Node("1")
    n2 = Node("2", n1)
    self.assertEqual(list(cfg_utils.topological_sort([n1, n2, 3, 4]))[-1], n2)

  def testTopologicalSortCycle(self):
    n1 = Node("1")
    n2 = Node("2")
    n1.incoming = [n2]
    n2.incoming = [n1]
    generator = cfg_utils.topological_sort([n1, n2])
    self.assertRaises(ValueError, list, generator)

  def testTopologicalSortSubCycle(self):
    n1 = Node("1")
    n2 = Node("2")
    n3 = Node("3")
    n1.incoming = [n2]
    n2.incoming = [n1]
    n3.incoming = [n1, n2]
    generator = cfg_utils.topological_sort([n1, n2, n3])
    self.assertRaises(ValueError, list, generator)

  def testTopologicalSortGetattr(self):
    self.assertEqual(list(cfg_utils.topological_sort([1])), [1])


if __name__ == "__main__":
  unittest.main()
