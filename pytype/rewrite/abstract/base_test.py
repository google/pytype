from pytype.rewrite.abstract import base
from pytype.rewrite.flow import variables
from typing_extensions import assert_type

import unittest


class BaseValueTest(unittest.TestCase):

  def test_to_variable(self):

    class C(base.BaseValue):

      def __repr__(self):
        return 'C'

      @property
      def _attrs(self):
        return (id(self),)

    c = C()
    var = c.to_variable()
    assert_type(var, variables.Variable[C])
    self.assertEqual(var.get_atomic_value(), c)


class PythonConstantTest(unittest.TestCase):

  def test_equal(self):
    c1 = base.PythonConstant('a')
    c2 = base.PythonConstant('a')
    self.assertEqual(c1, c2)

  def test_not_equal(self):
    c1 = base.PythonConstant('a')
    c2 = base.PythonConstant('b')
    self.assertNotEqual(c1, c2)

  def test_constant_type(self):
    c = base.PythonConstant('a')
    assert_type(c.constant, str)

  def test_get_type_from_variable(self):
    var = base.PythonConstant(True).to_variable()
    const = var.get_atomic_value(base.PythonConstant[int]).constant
    assert_type(const, int)


class SingletonTest(unittest.TestCase):

  def test_duplicate(self):
    _ = base.Singleton('TEST_SINGLETON')
    with self.assertRaises(ValueError):
      _ = base.Singleton('TEST_SINGLETON')


class UnionTest(unittest.TestCase):

  def test_basic(self):
    options = (base.PythonConstant(True), base.PythonConstant(False))
    union = base.Union(options)
    self.assertEqual(union.options, options)

  def test_flatten(self):
    union1 = base.Union((base.PythonConstant(True), base.PythonConstant(False)))
    union2 = base.Union((union1, base.PythonConstant(5)))
    self.assertEqual(union2.options, (base.PythonConstant(True),
                                      base.PythonConstant(False),
                                      base.PythonConstant(5)))

  def test_deduplicate(self):
    true = base.PythonConstant(True)
    false = base.PythonConstant(False)
    union = base.Union((true, false, true))
    self.assertEqual(union.options, (true, false))

  def test_order(self):
    true = base.PythonConstant(True)
    false = base.PythonConstant(False)
    self.assertEqual(base.Union((true, false)), base.Union((false, true)))


if __name__ == '__main__':
  unittest.main()
