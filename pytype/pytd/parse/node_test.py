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

from pytype.pytd import visitors
from pytype.pytd.parse import node
import unittest


# gpylint doesn't understand collections.namedtuple():
# pylint: disable=no-member


class Node1(node.Node("a", "b")):
  """Simple node for equality testing. Not equal to anything else."""


class Node2(node.Node("x", "y")):
  """For equality testing. Same attributes as Node3."""


class Node3(node.Node("x", "y")):
  """For equality testing: Same attributes as Node2."""


class Data(node.Node("d1", "d2", "d3")):
  """'Data' node. Visitor tests use this to store numbers in leafs."""


class V(node.Node("x")):
  """Inner node 'V', with one child. See testVisitor[...]() below."""


class X(node.Node("a", "b")):
  """Inner node 'X', with two children. See testVisitor[...]() below."""


class Y(node.Node("c", "d")):
  """Inner node 'Y', with two children. See testVisitor[...]() below."""


class XY(node.Node("x", "y")):
  """Inner node 'XY', with two children. See testVisitor[...]() below."""


class NodeWithVisit(node.Node("x", "y")):
  """A node with its own VisitNode function."""

  def VisitNode(self, visitor):
    """Allow a visitor to modify our children. Returns modified node."""
    # only visit x, not y
    x = self.x.Visit(visitor)
    return NodeWithVisit(x, self.y)


class DataVisitor(visitors.Visitor):
  """A visitor that transforms Data nodes."""

  def VisitData(self, data):
    """Visit Data nodes, and set 'd3' attribute to -1."""
    return data.Replace(d3=-1)


class MultiNodeVisitor(visitors.Visitor):
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


# We want to test == and != so:
# pylint: disable=g-generic-assert
class TestNode(unittest.TestCase):
  """Test the node.Node class generator."""

  def test_eq1(self):
    """Test the __eq__ and __ne__ functions of node.Node."""
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=2)
    self.assertTrue(n1 == n2)
    self.assertFalse(n1 != n2)

  def test_hash1(self):
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=2)
    self.assertEqual(hash(n1), hash(n2))

  def test_eq2(self):
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

  def test_hash2(self):
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=2)
    d1 = Node2(x="foo", y=n1)
    d2 = Node2(x="foo", y=n1)
    d3 = Node2(x="foo", y=n2)
    d4 = Node2(x="foo", y=n2)
    self.assertEqual(hash(d1), hash(d2))
    self.assertEqual(hash(d2), hash(d3))
    self.assertEqual(hash(d3), hash(d4))
    self.assertEqual(hash(d4), hash(d1))

  def test_deep_eq2(self):
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

  def test_deep_hash2(self):
    n1 = Node1(a=1, b=2)
    n2 = Node1(a=1, b=3)
    d1 = Node2(x="foo", y=n1)
    d2 = Node3(x="foo", y=n1)
    d3 = Node2(x="foo", y=n2)
    d4 = Node3(x="foo", y=n2)
    self.assertNotEqual(hash(d1), hash(d2))
    self.assertNotEqual(hash(d1), hash(d3))
    self.assertNotEqual(hash(d1), hash(d4))
    self.assertNotEqual(hash(d2), hash(d3))
    self.assertNotEqual(hash(d2), hash(d4))
    self.assertNotEqual(hash(d3), hash(d4))

  def test_immutable(self):
    """Test that node.Node has/preserves immutatibility."""
    n1 = Node1(a=1, b=2)
    n2 = Node2(x="foo", y=n1)
    with self.assertRaises(AttributeError):
      n1.a = 2
    with self.assertRaises(AttributeError):
      n2.x = "bar"
    with self.assertRaises(AttributeError):
      n2.x.b = 3

  def test_visitor1(self):
    """Test node.Node.Visit() for a visitor that modifies leaf nodes."""
    x = X(1, (1, 2))
    y = Y((V(1),), Data(42, 43, 44))
    xy = XY(x, y)
    xy_expected = "XY(X(1, (1, 2)), Y((V(1),), Data(42, 43, 44)))"
    self.assertEqual(repr(xy), xy_expected)
    v = DataVisitor()
    new_xy = xy.Visit(v)
    self.assertEqual(repr(new_xy),
                     "XY(X(1, (1, 2)), Y((V(1),), Data(42, 43, -1)))")
    self.assertEqual(repr(xy), xy_expected)  # check that xy is unchanged

  def test_visitor2(self):
    """Test node.Node.Visit() for visitors that modify inner nodes."""
    xy = XY(V(1), Data(1, 2, 3))
    xy_expected = "XY(V(1), Data(1, 2, 3))"
    self.assertEqual(repr(xy), xy_expected)
    v = MultiNodeVisitor()
    new_xy = xy.Visit(v, 42)
    self.assertEqual(repr(new_xy), "XY(X(V(42), V(42)), XY(42, 42))")
    self.assertEqual(repr(xy), xy_expected)  # check that xy is unchanged

  def test_recursion(self):
    """Test node.Node.Visit() for visitors that preserve attributes."""
    y = Y(Y(1, 2), Y(3, Y(4, 5)))
    y_expected = "Y(Y(1, 2), Y(3, Y(4, 5)))"
    self.assertEqual(repr(y), y_expected)
    v = MultiNodeVisitor()
    new_y = y.Visit(v)
    self.assertEqual(repr(new_y), y_expected.replace("Y", "X"))
    self.assertEqual(repr(y), y_expected)  # check that original is unchanged

  def test_tuple(self):
    """Test node.Node.Visit() for nodes that contain tuples."""
    v = V((Data(1, 2, 3), Data(4, 5, 6)))
    v_expected = "V((Data(1, 2, 3), Data(4, 5, 6)))"
    self.assertEqual(repr(v), v_expected)
    visit = DataVisitor()
    new_v = v.Visit(visit)
    new_v_expected = "V((Data(1, 2, -1), Data(4, 5, -1)))"
    self.assertEqual(repr(new_v), new_v_expected)

  def test_ordering(self):
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
      self.assertEqual(list(sorted(p)), nodes)

  def test_precondition(self):
    class MyNode(node.Node("s: str")):
      pass
    MyNode("a")  # OK.
    try:
      node.SetCheckPreconditions(False)
      MyNode(1)  # Preconditions are ignored.
    finally:
      # Restore preconditions (not part of the public API, but ensures the
      # test doesn't have a surprising side effect).
      node.SetCheckPreconditions(True)
# pylint: enable=g-generic-assert


if __name__ == "__main__":
  unittest.main()
