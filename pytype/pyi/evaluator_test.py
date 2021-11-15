"""Tests for pytype.pyi.evaluator."""

import sys

from pytype.pyi import evaluator
from pytype.pyi import types

import unittest

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


_eval = evaluator.eval_string_literal


class EvaluatorTest(unittest.TestCase):

  def test_str(self):
    self.assertEqual(_eval('"hello world"'), 'hello world')

  def test_num(self):
    self.assertEqual(_eval('3'), 3)

  def test_tuple(self):
    self.assertEqual(_eval('(None,)'), (None,))

  def test_list(self):
    self.assertEqual(_eval('[None]'), [None])

  def test_set(self):
    self.assertEqual(_eval('{None}'), {None})

  def test_dict(self):
    self.assertEqual(_eval('{"k": 0}'), {'k': 0})

  def test_name_constant(self):
    self.assertEqual(_eval('True'), True)

  def test_name(self):
    self.assertEqual(_eval('x'), 'x')

  def test_unop(self):
    self.assertEqual(_eval('-3'), -3)

  def test_binop(self):
    self.assertEqual(_eval('5 + 5'), 10)

  def test_constant(self):
    const = ast3.Constant('salutations')
    self.assertEqual(evaluator.literal_eval(const), 'salutations')

  def test_expr(self):
    expr = ast3.Expr(ast3.Num(8))
    self.assertEqual(evaluator.literal_eval(expr), 8)

  def test_pyi_int_constant(self):
    const = types.Pyval.from_num(ast3.parse('42', mode='eval').body)
    self.assertEqual(evaluator.literal_eval(const), 42)

  def test_pyi_none_constant(self):
    const = types.Pyval.from_const(ast3.parse('None', mode='eval').body)
    self.assertIsNone(evaluator.literal_eval(const))


if __name__ == '__main__':
  unittest.main()
