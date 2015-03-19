# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import itertools
from pytype.pytd.parse import node
import unittest


# gpylint doesn't understand collections.namedtuple():
# pylint: disable=no-member


class Node1(node.Node("a", "b")):
  """Simple node for equality testing. Not equal to anything else."""
  pass


class Node2(node.Node("x", "y")):
  """For equality testing. Same attributes as Node3."""
  pass


class Node3(node.Node("x", "y")):
  """For equality testing: Same attributes as Node2."""
  pass


class Data(node.Node("d1", "d2", "d3")):
  """'Data' node. Visitor tests use this to store numbers in leafs."""
  pass


class V(node.Node("x")):
  """Inner node 'V', with one child. See testVisitor[...]() below."""
  pass


class X(node.Node("a", "b")):
  """Inner node 'X', with two children. See testVisitor[...]() below."""
  pass


class Y(node.Node("c", "d")):
  """Inner node 'Y', with two children. See testVisitor[...]() below."""
  pass


class XY(node.Node("x", "y")):
  """Inner node 'XY', with two children. See testVisitor[...]() below."""
  pass


class NodeWithVisit(node.Node("x", "y")):
  """A node with its own Visit function."""

  def Visit(self, visitor):
    """Allow a visitor to modify our children. Returns modified node."""
    # only visit x, not y
    x = self.x.Visit(visitor)
    return NodeWithVisit(x, self.y)


class DataVisitor(object):
  """A visitor that transforms Data nodes."""

  def VisitData(self, data):
    """Visit Data nodes, and set 'd3' attribute to -1."""
    return data.Replace(d3=-1)


class MultiNodeVisitor(object):
  """A visitor that visits Data, V and Y nodes and uses the *args feature."""

  def VisitData(self, _, r):
    """Visit Data nodes, change them to XY nodes, and set x and y."""
    return XY(r, r)

  def VisitV(self, _, r):
    """Visit V nodes, change them to X nodes with V nodes as children."""
    return X(V(r), V(r))

  def VisitY(self, y):
    """Visit Y nodes, and change them to X nodes with the same attributes."""
    return X(*y)


class TestNode(unittest.TestCase):
  """Test the node.Node class generator."""

  def testEq1(self):
    """Test the __eq__ and __ne__ functions of node.Node."""
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=2)
    self.assertTrue(n1 == n2)
    self.assertFalse(n1 != n2)

  def testEq2(self):
    """Test the __eq__ and __ne__ functions of identical nested nodes."""
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=2)
    d1 = Node2(x="foo", y=n1)
    d2 = Node2(x="foo", y=n1)
    d3 = Node2(x="foo", y=n2)
    d4 = Node2(x="foo", y=n2)
    self.assertTrue(d1 == d2 and d2 == d3 and d3 == d4 and d4 == d1)
    # Since node overloads __ne___, too, test it explicitly:
    self.assertFalse(d1 != d2 or d2 != d3 or d3 != d4 or d4 != d1)

  def testDeepEq2(self):
    """Test the __eq__ and __ne__ functions of differing nested nodes."""
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=3)
    d1 = Node2(x="foo", y=n1)
    d2 = Node3(x="foo", y=n1)
    d3 = Node2(x="foo", y=n2)
    d4 = Node3(x="foo", y=n2)
    self.assertTrue(d1 != d2)
    self.assertTrue(d1 != d3)
    self.assertTrue(d1 != d4)
    self.assertTrue(d2 != d3)
    self.assertTrue(d2 != d4)
    self.assertTrue(d3 != d4)
    self.assertFalse(d1 == d2)
    self.assertFalse(d1 == d3)
    self.assertFalse(d1 == d4)
    self.assertFalse(d2 == d3)
    self.assertFalse(d2 == d4)
    self.assertFalse(d3 == d4)

  def testImmutable(self):
    """Test that node.Node has/preserves immutatibility."""
    n1 = Node1(a=1, b=2)
    n2 = Node2(x="foo", y=n1)
    with self.assertRaises(AttributeError):
      n1.a = 2
    with self.assertRaises(AttributeError):
      n2.x = "bar"
    with self.assertRaises(AttributeError):
      n2.x.b = 3

  def testVisitor1(self):
    """Test node.Node.Visit() for a visitor that modifies leaf nodes."""
    data = Data(42, 43, 44)
    x = X(1, [1, 2])
    y = Y([V(1)], {"bla": data})
    xy = XY(x, y)
    xy_expected = "XY(X(1, [1, 2]), Y([V(1)], {'bla': Data(42, 43, 44)}))"
    self.assertEquals(repr(xy), xy_expected)
    v = DataVisitor()
    new_xy = xy.Visit(v)
    self.assertEquals(repr(new_xy),
                      "XY(X(1, [1, 2]), Y([V(1)], {'bla': Data(42, 43, -1)}))")
    self.assertEquals(repr(xy), xy_expected)  # check that xy is unchanged

  def testVisitor2(self):
    """Test node.Node.Visit() for visitors that modify inner nodes."""
    xy = XY(V(1), Data(1, 2, 3))
    xy_expected = "XY(V(1), Data(1, 2, 3))"
    self.assertEquals(repr(xy), xy_expected)
    v = MultiNodeVisitor()
    new_xy = xy.Visit(v, 42)
    self.assertEquals(repr(new_xy), "XY(X(V(42), V(42)), XY(42, 42))")
    self.assertEquals(repr(xy), xy_expected)  # check that xy is unchanged

  def testRecursion(self):
    """Test node.Node.Visit() for visitors that preserve attributes."""
    y = Y(Y(1, 2), Y(3, Y(4, 5)))
    y_expected = "Y(Y(1, 2), Y(3, Y(4, 5)))"
    self.assertEquals(repr(y), y_expected)
    v = MultiNodeVisitor()
    new_y = y.Visit(v)
    self.assertEquals(repr(new_y), y_expected.replace("Y", "X"))
    self.assertEquals(repr(y), y_expected)  # check that original is unchanged

  def testTuple(self):
    """Test node.Node.Visit() for nodes that contain tuples."""
    v = V((Data(1, 2, 3), Data(4, 5, 6)))
    v_expected = "V((Data(1, 2, 3), Data(4, 5, 6)))"
    self.assertEquals(repr(v), v_expected)
    visit = DataVisitor()
    new_v = v.Visit(visit)
    new_v_expected = "V((Data(1, 2, -1), Data(4, 5, -1)))"
    self.assertEquals(repr(new_v), new_v_expected)

  def testList(self):
    """Test node.Node.Visit() for nodes that contain lists."""
    v = V([Data(1, 2, 3), Data(4, 5, 6)])
    v_expected = "V([Data(1, 2, 3), Data(4, 5, 6)])"
    self.assertEquals(repr(v), v_expected)
    visit = DataVisitor()
    new_v = v.Visit(visit)
    new_v_expected = "V([Data(1, 2, -1), Data(4, 5, -1)])"
    self.assertEquals(repr(new_v), new_v_expected)

  def testEmptyDictionary(self):
    """Test node.Node.Visit() for nodes that contain empty dictionaries."""
    visit = DataVisitor()
    v = V({})
    new_v = v.Visit(visit)
    self.assertEquals(new_v, v)

  def testDictionary(self):
    """Test node.Node.Visit() for nodes that contain dictionaries."""
    v = V({1: Data(1, 2, 3), 2: Data(4, 5, 6)})
    new_v = v.Visit(DataVisitor())
    self.assertEquals(new_v.x[1], Data(1, 2, -1))
    self.assertEquals(new_v.x[2], Data(4, 5, -1))

  def testCustomVisit(self):
    """Test nodes that have their own Visit() function."""
    n = Y(NodeWithVisit(Y(1, 2), Y(1, 2)), None)
    n_expected = "Y(NodeWithVisit(Y(1, 2), Y(1, 2)), None)"
    self.assertEquals(repr(n), n_expected)
    visit = MultiNodeVisitor()
    new_n = n.Visit(visit)
    new_n_expected = "X(NodeWithVisit(X(1, 2), Y(1, 2)), None)"
    self.assertEquals(repr(new_n), new_n_expected)

  def testOrdering(self):
    nodes = [Node1(1, 1), Node1(1, 2),
             Node2(1, 1), Node2(2, 1),
             Node3(1, 1), Node3(2, 2),
             V(2)]
    for n1, n2 in zip(nodes[:-1], nodes[1:]):
      self.assertLess(n1, n2)
      self.assertLessEqual(n1, n2)
      self.assertGreater(n2, n1)
      self.assertGreaterEqual(n2, n1)
    for p in itertools.permutations(nodes):
      self.assertEquals(list(sorted(p)), nodes)

if __name__ == "__main__":
  unittest.main()
