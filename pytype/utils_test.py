"""Tests for utils.py."""

from pytype import utils
import six

import unittest


class UtilsTest(unittest.TestCase):
  """Test generic utilities."""

  def test_numeric_sort_key(self):
    k = utils.numeric_sort_key
    self.assertLess(k("1aaa"), k("12aa"))
    self.assertLess(k("12aa"), k("123a"))
    self.assertLess(k("a1aa"), k("a12a"))
    self.assertLess(k("a12a"), k("a123"))

  def test_pretty_dnf(self):
    dnf = [["a", "b"], "c", ["d", "e", "f"]]
    self.assertEqual(utils.pretty_dnf(dnf), "(a & b) | c | (d & e & f)")

  def test_list_strip_prefix(self):
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

  def test_list_starts_with(self):
    self.assertTrue(utils.list_startswith([1, 2, 3], []))
    self.assertTrue(utils.list_startswith([1, 2, 3], [1]))
    self.assertTrue(utils.list_startswith([1, 2, 3], [1, 2]))
    self.assertTrue(utils.list_startswith([1, 2, 3], [1, 2, 3]))
    self.assertFalse(utils.list_startswith([1, 2, 3], [2]))
    self.assertTrue(utils.list_startswith([], []))
    self.assertFalse(utils.list_startswith([], [1]))

  def test_invert_dict(self):
    a = {"p": ["q", "r"], "x": ["q", "z"]}
    b = utils.invert_dict(a)
    six.assertCountEqual(self, b["q"], ["p", "x"])
    self.assertEqual(b["r"], ["p"])
    self.assertEqual(b["z"], ["x"])

  def test_dynamic_var(self):
    var = utils.DynamicVar()
    self.assertIsNone(var.get())
    with var.bind(123):
      self.assertEqual(123, var.get())
      with var.bind(456):
        self.assertEqual(456, var.get())
      self.assertEqual(123, var.get())
    self.assertIsNone(var.get())

  def test_version_from_string_int(self):
    self.assertEqual(utils.version_from_string("2"), (2, 7))

  def test_version_from_string_tuple(self):
    self.assertEqual(utils.version_from_string("2.7"), (2, 7))

  def test_full_version_from_major2(self):
    self.assertEqual(utils.full_version_from_major(2), (2, 7))

  @unittest.skipUnless(six.PY3, "py3 minor version depends on host version")
  def test_full_version_from_major3(self):
    major, _ = utils.full_version_from_major(3)
    self.assertEqual(major, 3)

  def test_normalize_version_int(self):
    self.assertEqual(utils.normalize_version(2), (2, 7))

  def test_normalize_version_tuple(self):
    self.assertEqual(utils.normalize_version((2, 7)), (2, 7))

  def test_validate_version(self):
    old = utils._VALIDATE_PYTHON_VERSION_UPPER_BOUND
    utils._VALIDATE_PYTHON_VERSION_UPPER_BOUND = True
    self._validate_version_helper((1, 1))
    self._validate_version_helper((2, 1))
    self._validate_version_helper((2, 8))
    self._validate_version_helper((3, 1))
    self._validate_version_helper((3, 9))
    utils._VALIDATE_PYTHON_VERSION_UPPER_BOUND = old

  def _validate_version_helper(self, python_version):
    with self.assertRaises(utils.UsageError):
      utils.validate_version(python_version)

  def test_parse_interpreter_version(self):
    test_cases = (
        ("Python 2.7.8", (2, 7)),
        ("Python 3.6.3", (3, 6)),
        ("Python 3.6.4 :: Something custom (64-bit)", (3, 6)),
        ("[OS-Y 64-bit] Python 3.7.1", (3, 7)),
    )
    for version_str, expected in test_cases:
      self.assertEqual(expected, utils.parse_exe_version_string(version_str))

  def test_get_python_exe_version(self):
    version = utils.get_python_exe_version(["python"])
    self.assertIsInstance(version, tuple)
    self.assertEqual(len(version), 2)


def _make_tuple(x):
  return tuple(range(x))


class DecoratorsTest(unittest.TestCase):
  """Test decorators."""

  @utils.memoize
  def _f1(self, x, y):
    return x + y

  def test_memoize1(self):
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

  def test_memoize2(self):
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

  def test_memoize3(self):
    # We make use of an indirect way to create two identical
    # tuples so that we do not end up with the same object
    # due to constant literal caching.
    y1 = _make_tuple(2)
    y2 = _make_tuple(2)
    l1 = self._f3((1,), y1)
    l2 = self._f3((1,), y2)
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

  def test_memoize4(self):
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

  def test_memoize5(self):
    class Foo:

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

  def test_annotating_decorator(self):
    foo = utils.AnnotatingDecorator()
    @foo(3)
    def f():  # pylint: disable=unused-variable
      pass
    self.assertEqual(foo.lookup["f"], 3)


if __name__ == "__main__":
  unittest.main()
