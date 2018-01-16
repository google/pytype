"""Tests for the additional CFG utilities."""

from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils
import unittest


class CFGUtilTest(unittest.TestCase):
  """Test CFG utilities."""

  def testMergeZeroVariables(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    self.assertIsInstance(cfg_utils.MergeVariables(p, n0, []), cfg.Variable)

  def testMergeOneVariable(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    u = p.NewVariable([0], [], n0)
    self.assertIs(cfg_utils.MergeVariables(p, n0, [u]), u)
    self.assertIs(cfg_utils.MergeVariables(p, n0, [u, u]), u)
    self.assertIs(cfg_utils.MergeVariables(p, n0, [u, u, u]), u)

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
    vw = cfg_utils.MergeVariables(p, n2, [v, w])
    self.assertItemsEqual(vw.data, [1, 2, 3])
    val1, = [v for v in vw.bindings if v.data == 1]
    self.assertTrue(val1.HasSource(u1))

  def testMergeBindings(self):
    p = cfg.Program()
    n0 = p.NewCFGNode("n0")
    u = p.NewVariable()
    u1 = u.AddBinding("1", source_set=[], where=n0)
    v2 = u.AddBinding("2", source_set=[], where=n0)
    w1 = cfg_utils.MergeBindings(p, None, [u1, v2])
    w2 = cfg_utils.MergeBindings(p, n0, [u1, v2])
    self.assertItemsEqual(w1.data, ["1", "2"])
    self.assertItemsEqual(w2.data, ["1", "2"])

  def testAsciiTree(self):
    p = cfg.Program()
    node1 = p.NewCFGNode("n1")
    node2 = node1.ConnectNew("n2")
    node3 = node2.ConnectNew("n3")
    _ = node3.ConnectNew()
    # Just check sanity. Actual verification of the drawing algorithm is
    # done in utils_test.py.
    self.assertIsInstance(cfg_utils.CFGAsciiTree(node1), str)
    self.assertIsInstance(cfg_utils.CFGAsciiTree(node1, forward=True), str)

  def testBindingPrettyPrint(self):
    p = cfg.Program()
    node = p.NewCFGNode()
    u = p.NewVariable()
    v1 = u.AddBinding(1, source_set=[], where=node)
    v2 = u.AddBinding(2, source_set=[v1], where=node)
    v3 = u.AddBinding(3, source_set=[v2], where=node)
    cfg_utils.PrintBinding(v3)  # smoke test

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


if __name__ == "__main__":
  unittest.main()
