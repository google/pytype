from typing import Tuple

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import utils
from typing_extensions import assert_type

import unittest


class GetAtomicConstantTest(unittest.TestCase):

  def test_get(self):
    var = base.PythonConstant('a').to_variable()
    const = utils.get_atomic_constant(var)
    self.assertEqual(const, 'a')

  def test_get_with_type(self):
    var = base.PythonConstant('a').to_variable()
    const = utils.get_atomic_constant(var, str)
    assert_type(const, str)
    self.assertEqual(const, 'a')

  def test_get_with_bad_type(self):
    var = base.PythonConstant('a').to_variable()
    with self.assertRaisesRegex(ValueError, 'expected int, got str'):
      utils.get_atomic_constant(var, int)

  def test_get_with_parameterized_type(self):
    var = base.PythonConstant(('a',)).to_variable()
    const = utils.get_atomic_constant(var, Tuple[str, ...])
    assert_type(const, Tuple[str, ...])
    self.assertEqual(const, ('a',))

  def test_get_with_bad_parameterized_type(self):
    var = base.PythonConstant('a').to_variable()
    with self.assertRaisesRegex(ValueError, 'expected tuple, got str'):
      utils.get_atomic_constant(var, Tuple[str, ...])


class JoinValuesTest(unittest.TestCase):

  def test_empty(self):
    self.assertEqual(utils.join_values([]), base.ANY)

  def test_one_value(self):
    a = base.PythonConstant('a')
    self.assertEqual(utils.join_values([a]), a)

  def test_multiple_values(self):
    a = base.PythonConstant('a')
    b = base.PythonConstant('b')
    val = utils.join_values([a, b])
    self.assertEqual(val, base.Union((a, b)))


if __name__ == '__main__':
  unittest.main()
