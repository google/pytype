"""Tests for pytd.py."""

import itertools
import pickle

from pytype.pytd import pytd
from six.moves import cPickle
import unittest


class TestPytd(unittest.TestCase):
  """Test the simple functionality in pytd.py."""

  def setUp(self):
    super(TestPytd, self).setUp()
    self.int = pytd.ClassType("int")
    self.none_type = pytd.ClassType("NoneType")
    self.float = pytd.ClassType("float")
    self.list = pytd.ClassType("list")

  def test_function_pickle(self):
    test_obj = "x1"
    f = pytd.FunctionType("test_name", test_obj)
    pickled_f = cPickle.dumps(f, pickle.HIGHEST_PROTOCOL)
    unpickled_f = cPickle.loads(pickled_f)
    # Objects can not be directly compared, as they use the NamedTuple equals.
    # Which does not know about .function.
    self.assertEqual(f.name, unpickled_f.name)
    self.assertEqual(f.function, unpickled_f.function)

  def test_union_type_eq(self):
    u1 = pytd.UnionType((self.int, self.float))
    u2 = pytd.UnionType((self.float, self.int))
    self.assertEqual(u1, u2)
    self.assertEqual(u2, u1)
    self.assertEqual(u1.type_list, (self.int, self.float))
    self.assertEqual(u2.type_list, (self.float, self.int))

  def test_union_type_ne(self):
    u1 = pytd.UnionType((self.int, self.float))
    u2 = pytd.UnionType((self.float, self.int, self.none_type))
    self.assertNotEqual(u1, u2)
    self.assertNotEqual(u2, u1)
    self.assertEqual(u1.type_list, (self.int, self.float))
    self.assertEqual(u2.type_list, (self.float, self.int, self.none_type))

  def test_order(self):
    # pytd types' primary sort key is the class name, second sort key is
    # the contents when interpreted as a (named)tuple.
    nodes = [pytd.AnythingType(),
             pytd.GenericType(self.list, (self.int,)),
             pytd.NamedType("int"),
             pytd.NothingType(),
             pytd.UnionType((self.float,)),
             pytd.UnionType((self.int,))]
    for n1, n2 in zip(nodes[:-1], nodes[1:]):
      self.assertLess(n1, n2)
      self.assertLessEqual(n1, n2)
      self.assertGreater(n2, n1)
      self.assertGreaterEqual(n2, n1)
    for p in itertools.permutations(nodes):
      self.assertEqual(list(sorted(p)), nodes)

  def test_empty_nodes_are_true(self):
    self.assertTrue(pytd.AnythingType())
    self.assertTrue(pytd.NothingType())


if __name__ == "__main__":
  unittest.main()
