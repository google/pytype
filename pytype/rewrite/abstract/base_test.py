from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import classes
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest


class FakeValue(base.BaseValue):

  def __repr__(self):
    return 'FakeValue'

  @property
  def _attrs(self):
    return (id(self),)


class BaseValueTest(test_utils.ContextfulTestBase):

  def test_to_variable(self):
    v = FakeValue(self.ctx)
    var = v.to_variable()
    assert_type(var, variables.Variable[FakeValue])
    self.assertEqual(var.get_atomic_value(), v)
    self.assertIsNone(var.name)

  def test_name(self):
    var = FakeValue(self.ctx).to_variable('NamedVariable')
    self.assertEqual(var.name, 'NamedVariable')


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

  def test_instantiate(self):
    class_x = classes.SimpleClass(self.ctx, 'X', {})
    class_y = classes.SimpleClass(self.ctx, 'Y', {})
    union = base.Union(self.ctx, (class_x, class_y))
    union_instance = union.instantiate()
    instance_x = classes.MutableInstance(self.ctx, class_x).freeze()
    instance_y = classes.MutableInstance(self.ctx, class_y).freeze()
    self.assertEqual(union_instance,
                     base.Union(self.ctx, (instance_x, instance_y)))


if __name__ == '__main__':
  unittest.main()
