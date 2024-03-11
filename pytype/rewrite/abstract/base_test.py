from pytype.rewrite.abstract import base
from pytype.rewrite.flow import variables
from typing_extensions import assert_type

import unittest


class BaseValueTest(unittest.TestCase):

  def test_to_variable(self):

    class C(base.BaseValue):
      pass

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


if __name__ == '__main__':
  unittest.main()
