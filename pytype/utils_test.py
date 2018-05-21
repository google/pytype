"""Tests for utils.py."""

import logging

from pytype import utils

import unittest

# pylint: disable=invalid-name


log = logging.getLogger(__name__)


class UtilsTest(unittest.TestCase):
  """Test generic utilities."""

  def testNumericSortKey(self):
    k = utils.numeric_sort_key
    self.assertLess(k("1aaa"), k("12aa"))
    self.assertLess(k("12aa"), k("123a"))
    self.assertLess(k("a1aa"), k("a12a"))
    self.assertLess(k("a12a"), k("a123"))

  def testPrettyDNF(self):
    dnf = [["a", "b"], "c", ["d", "e", "f"]]
    self.assertEqual(utils.pretty_dnf(dnf), "(a & b) | c | (d & e & f)")

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

  def testPathToModuleName(self):
    self.assertIsNone(utils.path_to_module_name("../foo.py"))
    self.assertEqual("x.y.z", utils.path_to_module_name("x/y/z.pyi"))
    self.assertEqual("x.y.z", utils.path_to_module_name("x/y/z.pytd"))
    self.assertEqual("x.y.z", utils.path_to_module_name("x/y/z/__init__.pyi"))
    self.assertEqual("x.y.z.__init__",
                     utils.path_to_module_name("x/y/z/__init__.pyi",
                                               preserve_init=True))

  def testSplitVersion(self):
    self.assertEqual(utils.split_version("2.7"), (2, 7))


class DecoratorsTest(unittest.TestCase):
  """Test decorators."""

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
    self.assertIsNot(z1, z2)
    self.assertIs(z2, z3)

  def testAnnotatingDecorator(self):
    foo = utils.AnnotatingDecorator()
    @foo(3)
    def f():  # pylint: disable=unused-variable
      pass
    self.assertEqual(foo.lookup["f"], 3)


if __name__ == "__main__":
  unittest.main()
