"""Tests for pytd.py."""

import itertools
import unittest
from pytype.pytd import pytd


class TestPytd(unittest.TestCase):
  """Test the simple functionality in pytd.py."""

  def setUp(self):
    self.int = pytd.ClassType("int")
    self.none_type = pytd.ClassType("NoneType")
    self.float = pytd.ClassType("float")
    self.list = pytd.ClassType("list")

  def testUnionTypeEq(self):
    u1 = pytd.UnionType((self.int, self.float))
    u2 = pytd.UnionType((self.float, self.int))
    self.assertEqual(u1, u2)
    self.assertEqual(u2, u1)
    self.assertEqual(u1.type_list, (self.int, self.float))
    self.assertEqual(u2.type_list, (self.float, self.int))

  def testUnionTypeNe(self):
    u1 = pytd.UnionType((self.int, self.float))
    u2 = pytd.UnionType((self.float, self.int, self.none_type))
    self.assertNotEqual(u1, u2)
    self.assertNotEqual(u2, u1)
    self.assertEqual(u1.type_list, (self.int, self.float))
    self.assertEqual(u2.type_list, (self.float, self.int, self.none_type))

  def testOrder(self):
    # pytd types' primary sort key is the class name, second sort key is
    # the contents when interpreted as a (named)tuple.
    nodes = [pytd.AnythingType(),
             pytd.GenericType(self.list, (self.int,)),
             pytd.NamedType("int"),
             pytd.NothingType(),
             pytd.UnionType(self.float),
             pytd.UnionType(self.int)]
    for n1, n2 in zip(nodes[:-1], nodes[1:]):
      self.assertLess(n1, n2)
      self.assertLessEqual(n1, n2)
      self.assertGreater(n2, n1)
      self.assertGreaterEqual(n2, n1)
    for p in itertools.permutations(nodes):
      self.assertEquals(list(sorted(p)), nodes)

if __name__ == "__main__":
  unittest.main()
