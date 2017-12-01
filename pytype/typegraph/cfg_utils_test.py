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

  def testCopyVarDiscardOrigin(self):
    # def f():
    #   x = None  # node 1
    #   return x  # node 2
    # def g():
    #   return f()  # node 3
    # old binding:
    #   "ret"->None @ node 2
    #     "x"->None @ node 1
    # new binding:
    #   "ret"->None @ node 3
    p = cfg.Program()
    node1, node2, node3 = self._create_program_nodes(p, 0, 2, 1)
    source = p.NewVariable().AddBinding("x", source_set=[], where=node1)
    old_var = p.NewVariable(["ret"], source_set=[source], where=node2)
    new_var = cfg_utils.CopyVarApprox(
        p, slice(node1.id, node2.id), node3, old_var)
    b, = new_var.bindings
    self.assertEqual(b.data, "ret")
    o, = b.origins
    self.assertIs(o.where, node3)
    self.assertEqual(o.source_sets, [set()])

  def testCopyVarDiscardMultipleOrigin(self):
    # x = None  # node 1
    # def f():
    #   y = None  # node 2
    #   return x if __random__ else y  # node 3
    # def g():
    #   return f()  # node 4
    # old binding:
    #   "ret"->None @ node3
    #     "x"->None @ node1
    #     "y"->None @ node2
    # new binding:
    #   "ret"->None @ node4
    p = cfg.Program()
    node1, node2, node3, node4 = self._create_program_nodes(p, 1, 2, 1)
    source_x = p.NewVariable().AddBinding("x", source_set=[], where=node1)
    source_y = p.NewVariable().AddBinding("y", source_set=[], where=node2)
    old_binding = p.NewVariable().AddBinding(
        "ret", source_set=[source_x], where=node3)
    old_binding.AddOrigin(where=node3, source_set=[source_y])
    new_var = cfg_utils.CopyVarApprox(
        p, slice(node2.id, node3.id), node4, old_binding.variable)
    b, = new_var.bindings
    self.assertEqual(b.data, "ret")
    o, = b.origins
    self.assertIs(o.where, node4)
    self.assertEqual(o.source_sets, [set()])

  def testCopyVarKeepOrigin(self):
    # x = None  # node 1
    # def f():
    #   return x  # node 2
    # def g():
    #   return f()  # node 3
    # old binding:
    #   "ret"->None @ node 2
    #     "x"->None @ node 1
    # new binding:
    #   "ret"->None @ node 3
    #     "x"->None @ node 1
    p = cfg.Program()
    node1, node2, node3 = self._create_program_nodes(p, 1, 1, 1)
    source = p.NewVariable().AddBinding("x", source_set=[], where=node1)
    old_var = p.NewVariable(["ret"], source_set=[source], where=node2)
    new_var = cfg_utils.CopyVarApprox(
        p, slice(node2.id, node2.id), node3, old_var)
    b, = new_var.bindings
    self.assertEqual(b.data, "ret")
    o, = b.origins
    self.assertIs(o.where, node3)
    (b2,), = o.source_sets
    o2, = b2.origins
    self.assertIs(o2.where, node1)
    self.assertEqual(o2.source_sets, [set()])

  def testCopyVarKeepMultipleOrigin(self):
    # x = None  # node 1
    # y = None  # node 2
    # def f():
    #   return x if __random__ else y  # node 3
    # def g():
    #   return f()  # node 4
    # old binding:
    #   "ret"->None @ node 3
    #     "x"->None @ node 1
    #     "y"->None @ node 2
    # new binding:
    #   "ret"->None @ node 4
    #     "x"->None @ node 1
    #     "y"->None @ node 2
    p = cfg.Program()
    node1, node2, node3, node4 = self._create_program_nodes(p, 2, 1, 1)
    source_x = p.NewVariable().AddBinding("x", source_set=[], where=node1)
    source_y = p.NewVariable().AddBinding("y", source_set=[], where=node2)
    old_binding = p.NewVariable().AddBinding(
        "ret", source_set=[source_x], where=node3)
    old_binding.AddOrigin(where=node3, source_set=[source_y])
    new_var = cfg_utils.CopyVarApprox(
        p, slice(node3.id, node3.id), node4, old_binding.variable)
    b, = new_var.bindings
    o, = b.origins
    self.assertIs(o.where, node4)
    (b2,), = o.source_sets
    self.assertItemsEqual([o.where for o in b2.origins], [node1, node2])
    self.assertItemsEqual([o.source_sets for o in b2.origins],
                          [[set()], [set()]])

  def testCopyVarKeepOtherFuncOrigin(self):
    # x = None  # node 1
    # def f():
    #   global x
    #   x = None  # node 2
    # def g():
    #   return x  # node 3
    # def h():
    #   return g()  # node 4
    # old binding:
    #   "ret"->None @ node 3
    #     "x"->None @ node 1
    #     "x"->None @ node 2
    # new binding:
    #   "ret"->None @ node 4
    #     "x"->None @ node 1
    #     "x"->None @ node 2
    p = cfg.Program()
    node1, node2, node3, node4 = self._create_program_nodes(p, 1, 1, 1, 1)
    source_mod = p.NewVariable().AddBinding("x", source_set=[], where=node1)
    source_f = p.NewVariable().AddBinding("x", source_set=[], where=node2)
    old_binding = p.NewVariable().AddBinding(
        "ret", source_set=[source_mod], where=node3)
    old_binding.AddOrigin(where=node3, source_set=[source_f])
    new_var = cfg_utils.CopyVarApprox(
        p, slice(node3.id, node3.id), node4, old_binding.variable)
    b, = new_var.bindings
    o, = b.origins
    self.assertIs(o.where, node4)
    (b2,), = o.source_sets
    self.assertItemsEqual([o.where for o in b2.origins], [node1, node2])
    self.assertItemsEqual([o.source_sets for o in b2.origins],
                          [[set()], [set()]])

  def testCopyVarKeepOtherFuncOriginReordered(self):
    # x = None  # node 1
    # def f():
    #   return x  # node 2
    # def g():
    #   global x
    #   x = None  # node 3
    # def h():
    #   return f()  # node 4
    # old binding:
    #   "ret"->None @ node 2
    #     "x"->None @ node 1
    #     "x"->None @ node 3
    # new binding:
    #   "ret"->None @ node 4
    #     "x"->None @ node 1
    #     "x"->None @ node 3
    p = cfg.Program()
    node1, node2, node3, node4 = self._create_program_nodes(p, 1, 1, 1, 1)
    source_mod = p.NewVariable().AddBinding("x", source_set=[], where=node1)
    source_g = p.NewVariable().AddBinding("x", source_set=[], where=node3)
    old_binding = p.NewVariable().AddBinding(
        "ret", source_set=[source_mod], where=node2)
    old_binding.AddOrigin(where=node2, source_set=[source_g])
    new_var = cfg_utils.CopyVarApprox(
        p, slice(node2.id, node2.id), node4, old_binding.variable)
    b, = new_var.bindings
    o, = b.origins
    self.assertIs(o.where, node4)
    (b2,), = o.source_sets
    self.assertItemsEqual([o.where for o in b2.origins], [node1, node3])
    self.assertItemsEqual([o.source_sets for o in b2.origins],
                          [[set()], [set()]])
  # pylint: enable=unbalanced-tuple-unpacking


if __name__ == "__main__":
  unittest.main()
