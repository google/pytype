from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import classes
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest


class BaseValueTest(test_utils.ContextfulTestBase):

  def test_to_variable(self):

    class C(base.BaseValue):

      def __repr__(self):
        return 'C'

      @property
      def _attrs(self):
        return (id(self),)

    c = C(self.ctx)
    var = c.to_variable()
    assert_type(var, variables.Variable[C])
    self.assertEqual(var.get_atomic_value(), c)


class SingletonTest(test_utils.ContextfulTestBase):

  def test_duplicate(self):
    s1 = base.Singleton(self.ctx, 'TEST_SINGLETON')
    s2 = base.Singleton(self.ctx, 'TEST_SINGLETON')
    self.assertIs(s1, s2)


class UnionTest(test_utils.ContextfulTestBase):

  def test_basic(self):
    options = (classes.PythonConstant(self.ctx, True),
               classes.PythonConstant(self.ctx, False))
    union = base.Union(self.ctx, options)
    self.assertEqual(union.options, options)

  def test_flatten(self):
    union1 = base.Union(self.ctx, (classes.PythonConstant(self.ctx, True),
                                   classes.PythonConstant(self.ctx, False)))
    union2 = base.Union(self.ctx, (union1, classes.PythonConstant(self.ctx, 5)))
    self.assertEqual(union2.options, (classes.PythonConstant(self.ctx, True),
                                      classes.PythonConstant(self.ctx, False),
                                      classes.PythonConstant(self.ctx, 5)))

  def test_deduplicate(self):
    true = classes.PythonConstant(self.ctx, True)
    false = classes.PythonConstant(self.ctx, False)
    union = base.Union(self.ctx, (true, false, true))
    self.assertEqual(union.options, (true, false))

  def test_order(self):
    true = classes.PythonConstant(self.ctx, True)
    false = classes.PythonConstant(self.ctx, False)
    self.assertEqual(base.Union(self.ctx, (true, false)),
                     base.Union(self.ctx, (false, true)))


if __name__ == '__main__':
  unittest.main()
