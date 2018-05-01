"""Tests for pytd.py."""

import itertools
import pickle
import textwrap
import unittest

from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import visitors
from six.moves import cPickle


class TestPytd(unittest.TestCase):
  """Test the simple functionality in pytd.py."""

  PYTHON_VERSION = (2, 7)

  def setUp(self):
    self.int = pytd.ClassType("int")
    self.none_type = pytd.ClassType("NoneType")
    self.float = pytd.ClassType("float")
    self.list = pytd.ClassType("list")

  def testFunctionPickle(self):
    test_obj = "x1"
    f = pytd.FunctionType("test_name", test_obj)
    pickled_f = cPickle.dumps(f, pickle.HIGHEST_PROTOCOL)
    unpickled_f = cPickle.loads(pickled_f)
    # Objects can not be directly compared, as they use the NamedTuple equals.
    # Which does not know about .function.
    self.assertEqual(f.name, unpickled_f.name)
    self.assertEqual(f.function, unpickled_f.function)

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
             pytd.UnionType((self.float,)),
             pytd.UnionType((self.int,))]
    for n1, n2 in zip(nodes[:-1], nodes[1:]):
      self.assertLess(n1, n2)
      self.assertLessEqual(n1, n2)
      self.assertGreater(n2, n1)
      self.assertGreaterEqual(n2, n1)
    for p in itertools.permutations(nodes):
      self.assertEqual(list(sorted(p)), nodes)

  def testASTeq(self):
    # This creates two ASts that are equivalent but whose sources are slightly
    # different. The union types are different (int,str) vs (str,int) but the
    # ordering is ignored when testing for equality (which ASTeq uses).
    src1 = textwrap.dedent("""
        def foo(a: int or str) -> C
        T = TypeVar('T')
        class C(typing.Generic[T], object):
            def bar(x: T) -> NoneType
        CONSTANT = ...  # type: C[float]
        """)
    src2 = textwrap.dedent("""
        CONSTANT = ...  # type: C[float]
        T = TypeVar('T')
        class C(typing.Generic[T], object):
            def bar(x: T) -> NoneType
        def foo(a: str or int) -> C
        """)
    tree1 = parser.parse_string(src1, python_version=self.PYTHON_VERSION)
    tree2 = parser.parse_string(src2, python_version=self.PYTHON_VERSION)
    tree1.Visit(visitors.VerifyVisitor())
    tree2.Visit(visitors.VerifyVisitor())
    self.assertTrue(tree1.constants)
    self.assertTrue(tree1.classes)
    self.assertTrue(tree1.functions)
    self.assertTrue(tree2.constants)
    self.assertTrue(tree2.classes)
    self.assertTrue(tree2.functions)
    self.assertIsInstance(tree1, pytd.TypeDeclUnit)
    self.assertIsInstance(tree2, pytd.TypeDeclUnit)
    # For the ==, != tests, TypeDeclUnit uses identity
    # pylint: disable=g-generic-assert
    self.assertTrue(tree1 == tree1)
    self.assertTrue(tree2 == tree2)
    self.assertFalse(tree1 == tree2)
    self.assertFalse(tree2 == tree1)
    self.assertFalse(tree1 != tree1)
    self.assertFalse(tree2 != tree2)
    self.assertTrue(tree1 != tree2)
    self.assertTrue(tree2 != tree1)
    # pylint: enable=g-generic-assert
    self.assertEqual(tree1, tree1)
    self.assertEqual(tree2, tree2)
    self.assertNotEqual(tree1, tree2)
    self.assertTrue(tree1.ASTeq(tree2))
    self.assertTrue(tree1.ASTeq(tree1))
    self.assertTrue(tree2.ASTeq(tree1))
    self.assertTrue(tree2.ASTeq(tree2))

  def testEmptyNodesAreTrue(self):
    self.assertTrue(pytd.AnythingType())
    self.assertTrue(pytd.NothingType())


if __name__ == "__main__":
  unittest.main()
