"""Tests for utils.py."""

import itertools
import logging
import os

from pytype import utils
from pytype.typegraph import cfg

import unittest

# pylint: disable=invalid-name


log = logging.getLogger(__name__)


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


class UtilsTest(unittest.TestCase):

  def setUp(self):
    self.prog = cfg.Program()
    self.current_location = self.prog.NewCFGNode()

  def testReplaceExtension(self):
    self.assertEqual("foo.bar", utils.replace_extension("foo.txt", "bar"))
    self.assertEqual("foo.bar", utils.replace_extension("foo.txt", ".bar"))
    self.assertEqual("a.b.c.bar", utils.replace_extension("a.b.c.txt", ".bar"))
    self.assertEqual("a.b/c.bar", utils.replace_extension("a.b/c.d", ".bar"))
    self.assertEqual("xyz.bar", utils.replace_extension("xyz", "bar"))

  def testComplexityLimit(self):
    limit = utils.ComplexityLimit(5)
    limit.inc()
    limit.inc(2)
    limit.inc()
    self.assertRaises(utils.TooComplexError, limit.inc)

  def testVariableProduct(self):
    u1 = self.prog.NewVariable([1, 2], [], self.current_location)
    u2 = self.prog.NewVariable([3, 4], [], self.current_location)
    product = utils.variable_product([u1, u2])
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
    self.assertRaises(utils.TooComplexError,
                      utils.deep_variable_product, [v1, v2, v3, v4,
                                                    v5, v6, v7, v8], 256)

  def testDeepVariableProductRaises2(self):
    x1, x2, x3, x4 = [DummyValue(i + 1) for i in range(4)]
    v1 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v2 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v3 = self.prog.NewVariable([x3, x4], [], self.current_location)
    v4 = self.prog.NewVariable([x3, x4], [], self.current_location)
    x1.set_parameters([v3])
    x2.set_parameters([v4])
    self.assertRaises(utils.TooComplexError,
                      utils.deep_variable_product, [v1, v2], 4)

  def testVariableProductDictRaises(self):
    values = [DummyValue(i + 1) for i in range(4)]
    v1 = self.prog.NewVariable(values, [], self.current_location)
    v2 = self.prog.NewVariable(values, [], self.current_location)
    v3 = self.prog.NewVariable(values, [], self.current_location)
    v4 = self.prog.NewVariable(values, [], self.current_location)
    variabledict = {"v1": v1, "v2": v2, "v3": v3, "v4": v4}
    self.assertRaises(utils.TooComplexError,
                      utils.variable_product_dict, variabledict, 4)

  def testDeepVariableProduct(self):
    x1, x2, x3, x4, x5, x6 = [DummyValue(i + 1) for i in range(6)]
    v1 = self.prog.NewVariable([x1, x2], [], self.current_location)
    v2 = self.prog.NewVariable([x3], [], self.current_location)
    v3 = self.prog.NewVariable([x4, x5], [], self.current_location)
    v4 = self.prog.NewVariable([x6], [], self.current_location)
    x1.set_parameters([v2, v3])
    product = utils.deep_variable_product([v1, v4])
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
    product = utils.deep_variable_product([v1])
    rows = [{a.data for a in row}
            for row in product]
    self.assertItemsEqual(rows, [{x1}])

  def testDeepVariableProductWithEmptyTopLayer(self):
    x1 = DummyValue(1)
    v1 = self.prog.NewVariable([x1], [], self.current_location)
    v2 = self.prog.NewVariable([], [], self.current_location)
    product = utils.deep_variable_product([v1, v2])
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
    product = utils.deep_variable_product([v1, v4])
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
    product = utils.variable_product_dict({"a": u1, "b": u2})
    pairs = [{k: a.data for k, a in d.items()} for d in product]
    self.assertItemsEqual(pairs, [
        {"a": 1, "b": 3},
        {"a": 1, "b": 4},
        {"a": 2, "b": 3},
        {"a": 2, "b": 4},
    ])

  def testNumericSortKey(self):
    k = utils.numeric_sort_key
    self.assertLess(k("1aaa"), k("12aa"))
    self.assertLess(k("12aa"), k("123a"))
    self.assertLess(k("a1aa"), k("a12a"))
    self.assertLess(k("a12a"), k("a123"))

  def testPrettyDNF(self):
    dnf = [["a", "b"], "c", ["d", "e", "f"]]
    self.assertEqual(utils.pretty_dnf(dnf), "(a & b) | c | (d & e & f)")

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
    r = utils.compute_predecessors(nodes)
    self.assertItemsEqual(r[n1], {n1})
    self.assertItemsEqual(r[n20], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n3], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n4], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n5], {n1, n20, n3, n4, n5})
    self.assertItemsEqual(r[n6], {n1, n20, n3, n4, n5, n6})
    self.assertItemsEqual(r[n7], {n1, n7})

  def testOrderNodes0(self):
    order = utils.order_nodes([])
    self.assertItemsEqual(order, [])

  def testOrderNodes1(self):
    # n1 --> n2
    n1 = self.prog.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    order = utils.order_nodes([n1, n2])
    self.assertItemsEqual([n1, n2], order)

  def testOrderNodes2(self):
    # n1   n2(dead)
    n1 = self.prog.NewCFGNode("n1")
    n2 = self.prog.NewCFGNode("n2")
    order = utils.order_nodes([n1, n2])
    self.assertItemsEqual([n1], order)

  def testOrderNodes3(self):
    # n1 --> n2 --> n3
    # ^             |
    # +-------------+
    n1 = self.prog.NewCFGNode("n1")
    n2 = n1.ConnectNew("n2")
    n3 = n2.ConnectNew("n3")
    n3.ConnectTo(n1)
    order = utils.order_nodes([n1, n2, n3])
    self.assertItemsEqual([n1, n2, n3], order)

  def testOrderNodes4(self):
    # n1 --> n3 --> n2
    # ^      |
    # +------+
    n1 = self.prog.NewCFGNode("n1")
    n3 = n1.ConnectNew("n3")
    n2 = n3.ConnectNew("n2")
    n3.ConnectTo(n1)
    order = utils.order_nodes([n1, n2, n3])
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
    order = utils.order_nodes([n1, n2, n3, n4])
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
    order = utils.order_nodes([n1, n5, n4, n3, n2])
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
    order = utils.order_nodes([n1, n2, n3, n4, n5, n6, n7, n8])
    self.assertItemsEqual([n1, n2, n3, n7, n4, n5, n8, n6], order)

  def testTopologicalSort(self):
    n1 = Node("1")
    n2 = Node("2", n1)
    n3 = Node("3", n2)
    n4 = Node("4", n2, n3)
    for permutation in itertools.permutations([n1, n2, n3, n4]):
      self.assertEqual(list(utils.topological_sort(permutation)),
                       [n1, n2, n3, n4])

  def testTopologicalSort2(self):
    n1 = Node("1")
    n2 = Node("2", n1)
    self.assertEqual(list(utils.topological_sort([n1, n2, 3, 4]))[-1], n2)

  def testTopologicalSortCycle(self):
    n1 = Node("1")
    n2 = Node("2")
    n1.incoming = [n2]
    n2.incoming = [n1]
    generator = utils.topological_sort([n1, n2])
    self.assertRaises(ValueError, list, generator)

  def testTopologicalSortSubCycle(self):
    n1 = Node("1")
    n2 = Node("2")
    n3 = Node("3")
    n1.incoming = [n2]
    n2.incoming = [n1]
    n3.incoming = [n1, n2]
    generator = utils.topological_sort([n1, n2, n3])
    self.assertRaises(ValueError, list, generator)

  def testTopologicalSortGetattr(self):
    self.assertEqual(list(utils.topological_sort([1])), [1])

  def testTempdir(self):
    with utils.Tempdir() as d:
      filename1 = d.create_file("foo.txt")
      filename2 = d.create_file("bar.txt", "\tdata2")
      filename3 = d.create_file("baz.txt", "data3")
      filename4 = d.create_file("d1/d2/qqsv.txt", "  data4.1\n  data4.2")
      filename5 = d.create_directory("directory")
      self.assertEqual(filename1, d["foo.txt"])
      self.assertEqual(filename2, d["bar.txt"])
      self.assertEqual(filename3, d["baz.txt"])
      self.assertEqual(filename4, d["d1/d2/qqsv.txt"])
      self.assertTrue(os.path.isdir(d.path))
      self.assertTrue(os.path.isfile(filename1))
      self.assertTrue(os.path.isfile(filename2))
      self.assertTrue(os.path.isfile(filename3))
      self.assertTrue(os.path.isfile(filename4))
      self.assertTrue(os.path.isdir(os.path.join(d.path, "d1")))
      self.assertTrue(os.path.isdir(os.path.join(d.path, "d1", "d2")))
      self.assertTrue(os.path.isdir(filename5))
      self.assertEqual(filename4, os.path.join(d.path, "d1", "d2", "qqsv.txt"))
      for filename, contents in [(filename1, ""),
                                 (filename2, "data2"),  # dedented
                                 (filename3, "data3"),
                                 (filename4, "data4.1\ndata4.2"),  # dedented
                                ]:
        with open(filename, "r") as fi:
          self.assertEqual(fi.read(), contents)
    self.assertFalse(os.path.isdir(d.path))
    self.assertFalse(os.path.isfile(filename1))
    self.assertFalse(os.path.isfile(filename2))
    self.assertFalse(os.path.isfile(filename3))
    self.assertFalse(os.path.isdir(os.path.join(d.path, "d1")))
    self.assertFalse(os.path.isdir(os.path.join(d.path, "d1", "d2")))
    self.assertFalse(os.path.isdir(filename5))

  def testCd(self):
    with utils.Tempdir() as d:
      d.create_directory("foo")
      d1 = os.getcwd()
      with utils.cd(d.path):
        self.assertTrue(os.path.isdir("foo"))
      d2 = os.getcwd()
      self.assertEqual(d1, d2)

  def testListStripPrefix(self):
    self.assertEqual([1, 2, 3], utils.list_strip_prefix([1, 2, 3], []))
    self.assertEqual([2, 3], utils.list_strip_prefix([1, 2, 3], [1]))
    self.assertEqual([3], utils.list_strip_prefix([1, 2, 3], [1, 2]))
    self.assertEqual([], utils.list_strip_prefix([1, 2, 3], [1, 2, 3]))
    self.assertEqual([1, 2, 3],
                     utils.list_strip_prefix([1, 2, 3], [0, 1, 2, 3]))
    self.assertEqual([], utils.list_strip_prefix([], [1, 2, 3]))
    self.assertEqual(list("wellington"), utils.list_strip_prefix(
        list("newwellington"), list("new")))
    self.assertEqual(
        "a.somewhat.long.path.src2.d3.shrdlu".split("."),
        utils.list_strip_prefix(
            "top.a.somewhat.long.path.src2.d3.shrdlu".split("."),
            "top".split(".")))

  def testListStartsWith(self):
    self.assertTrue(utils.list_startswith([1, 2, 3], []))
    self.assertTrue(utils.list_startswith([1, 2, 3], [1]))
    self.assertTrue(utils.list_startswith([1, 2, 3], [1, 2]))
    self.assertTrue(utils.list_startswith([1, 2, 3], [1, 2, 3]))
    self.assertFalse(utils.list_startswith([1, 2, 3], [2]))
    self.assertTrue(utils.list_startswith([], []))
    self.assertFalse(utils.list_startswith([], [1]))

  def testGetAbsoluteName(self):
    test_cases = [
        ("x.y", "a.b", "x.y.a.b"),
        ("", "a.b", "a.b"),
        ("x.y", ".a.b", "x.y.a.b"),
        ("x.y", "..a.b", "x.a.b"),
        ("x.y", "...a.b", None),
    ]
    for prefix, name, expected in test_cases:
      self.assertEqual(utils.get_absolute_name(prefix, name), expected)

  @utils.memoize
  def _f1(self, x, y):
    return x + y

  def testMemoize1(self):
    l1 = self._f1((1,), (2,))
    l2 = self._f1(x=(1,), y=(2,))
    l3 = self._f1((1,), y=(2,))
    self.assertIs(l1, l2)
    self.assertIs(l2, l3)
    l1 = self._f1((1,), (2,))
    l2 = self._f1((1,), (3,))
    self.assertIsNot(l1, l2)

  @utils.memoize("x")
  def _f2(self, x, y):
    return x + y

  def testMemoize2(self):
    l1 = self._f2((1,), (2,))
    l2 = self._f2((1,), (3,))
    self.assertIs(l1, l2)
    l1 = self._f2(x=(1,), y=(2,))
    l2 = self._f2(x=(1,), y=(3,))
    self.assertIs(l1, l2)
    l1 = self._f2((1,), (2,))
    l2 = self._f2((2,), (2,))
    self.assertIsNot(l1, l2)

  @utils.memoize("(x, id(y))")
  def _f3(self, x, y):
    return x + y

  def testMemoize3(self):
    l1 = self._f3((1,), (2,))
    l2 = self._f3((1,), (2,))
    self.assertIsNot(l1, l2)  # two different ids
    y = (2,)
    l1 = self._f3((1,), y)
    l2 = self._f3((1,), y)
    l3 = self._f3(x=(1,), y=y)
    self.assertIs(l1, l2)
    self.assertIs(l2, l3)

  @utils.memoize("(x, y)")
  def _f4(self, x=1, y=2):
    return x + y

  def testMemoize4(self):
    z1 = self._f4(1, 2)
    z2 = self._f4(1, 3)
    self.assertNotEqual(z1, z2)
    z1 = self._f4(1, 2)
    z2 = self._f4(1, 2)
    self.assertIs(z1, z2)
    z1 = self._f4()
    z2 = self._f4()
    self.assertIs(z1, z2)
    z1 = self._f4()
    z2 = self._f4(1, 2)
    self.assertIs(z1, z2)

  def testMemoize5(self):
    class Foo(object):

      @utils.memoize("(self, x, y)")
      def _f5(self, x, y):
        return x + y
    foo1 = Foo()
    foo2 = Foo()
    z1 = foo1._f5((1,), (2,))
    z2 = foo2._f5((1,), (2,))
    z3 = foo2._f5((1,), (2,))
    self.assertFalse(z1 is z2)
    self.assertTrue(z2 is z3)

  def testInvertDict(self):
    a = {"p": ["q", "r"], "x": ["q", "z"]}
    b = utils.invert_dict(a)
    self.assertEqual(sorted(b["q"]), ["p", "x"])
    self.assertEqual(b["r"], ["p"])
    self.assertEqual(b["z"], ["x"])

  def testDynamicVar(self):
    var = utils.DynamicVar()
    self.assertIsNone(var.get())
    with var.bind(123):
      self.assertEqual(123, var.get())
      with var.bind(456):
        self.assertEqual(456, var.get())
      self.assertEqual(123, var.get())
    self.assertIsNone(var.get())

  def testAnnotatingDecorator(self):
    foo = utils.AnnotatingDecorator()
    @foo(3)
    def f():  # pylint: disable=unused-variable
      pass
    self.assertEqual(foo.lookup["f"], 3)

  def testListPytypeFiles(self):
    l = list(utils.list_pytype_files("pytd/stdlib/2"))
    self.assertIn("ctypes.pytd", l)
    self.assertIn("collections.pytd", l)

  def testPathToModuleName(self):
    self.assertEqual("x.y.z", utils.path_to_module_name("x/y/z.pyi"))
    self.assertEqual("x.y.z", utils.path_to_module_name("x/y/z.pytd"))
    self.assertEqual("x.y.z", utils.path_to_module_name("x/y/z/__init__.pyi"))


if __name__ == "__main__":
  unittest.main()
