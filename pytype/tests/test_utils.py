"""Tests for utils.py."""

import os


from pytype import utils
from pytype.pytd import cfg as typegraph
from pytype.pytd import pytd
from pytype.tests import test_inference

import unittest


class TypegraphUtilsTest(unittest.TestCase):

  def setUp(self):
    self.prog = typegraph.Program()
    self.current_location = self.prog.NewCFGNode()

  def testVariableProduct(self):
    u1 = self.prog.NewVariable("u1", [1, 2], [], self.current_location)
    u2 = self.prog.NewVariable("u2", [3, 4], [], self.current_location)
    product = utils.variable_product([u1, u2])
    pairs = [[a.data for a in d]
             for d in product]
    self.assertItemsEqual(pairs, [
        [1, 3],
        [1, 4],
        [2, 3],
        [2, 4],
    ])

  def testVariableProductDict(self):
    u1 = self.prog.NewVariable("u1", [1, 2], [], self.current_location)
    u2 = self.prog.NewVariable("u2", [3, 4], [], self.current_location)
    product = utils.variable_product_dict({"a": u1, "b": u2})
    pairs = [{k: a.data for k, a in d.iteritems()}
             for d in product]
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
    self.assertEquals(utils.pretty_dnf(dnf), "(a & b) | c | (d & e & f)")

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

    nodes = [n1, n20, n3, n4, n5, n6, n7]
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

  def testFlattenSuperclasses(self):
    cls_a = pytd.Class("A", (), (), (), ())
    cls_b = pytd.Class("B", (cls_a,), (), (), ())
    cls_c = pytd.Class("C", (cls_a,), (), (), ())
    cls_d = pytd.Class("D", (cls_c,), (), (), ())
    cls_e = pytd.Class("E", (cls_d, cls_b), (), (), ())
    self.assertItemsEqual(utils.flattened_superclasses(cls_e),
                          [cls_a, cls_b, cls_c, cls_d, cls_e])

  def testTempdir(self):
    with utils.Tempdir() as d:
      filename1 = d.create_file("foo.txt")
      filename2 = d.create_file("bar.txt", "\tdata2")
      filename3 = d.create_file("baz.txt", "data3")
      filename4 = d.create_file("d1/d2/qqsv.txt", "  data4.1\n  data4.2")
      self.assertEquals(filename1, d["foo.txt"])
      self.assertEquals(filename2, d["bar.txt"])
      self.assertEquals(filename3, d["baz.txt"])
      self.assertEquals(filename4, d["d1/d2/qqsv.txt"])
      self.assertTrue(os.path.isdir(d.path))
      self.assertTrue(os.path.isfile(filename1))
      self.assertTrue(os.path.isfile(filename2))
      self.assertTrue(os.path.isfile(filename3))
      self.assertTrue(os.path.isfile(filename4))
      self.assertTrue(os.path.isdir(os.path.join(d.path, "d1")))
      self.assertTrue(os.path.isdir(os.path.join(d.path, "d1", "d2")))
      self.assertEqual(filename4, os.path.join(d.path, "d1", "d2", "qqsv.txt"))
      for filename, contents in [(filename1, ""),
                                 (filename2, "data2"),  # dedented
                                 (filename3, "data3"),
                                 (filename4, "data4.1\ndata4.2"),  # dedented
                                ]:
        with open(filename, "rb") as fi:
          self.assertEquals(fi.read(), contents)
    self.assertFalse(os.path.isdir(d.path))
    self.assertFalse(os.path.isfile(filename1))
    self.assertFalse(os.path.isfile(filename2))
    self.assertFalse(os.path.isfile(filename3))
    self.assertFalse(os.path.isdir(os.path.join(d.path, "d1")))
    self.assertFalse(os.path.isdir(os.path.join(d.path, "d1", "d2")))


if __name__ == "__main__":
  test_inference.main()
