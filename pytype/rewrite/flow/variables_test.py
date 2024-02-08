from typing import Tuple, Union

from pytype.rewrite.flow import conditions
from pytype.rewrite.flow import variables
from typing_extensions import assert_type

import unittest


class BindingTest(unittest.TestCase):

  def test_type(self):
    b = variables.Binding(0)
    assert_type(b, variables.Binding[int])


class VariableTest(unittest.TestCase):

  def test_from_value(self):
    var = variables.Variable.from_value(0)
    assert_type(var, variables.Variable[int])

  def test_multiple_bindings(self):
    var = variables.Variable((variables.Binding(0), variables.Binding('')))
    assert_type(var, variables.Variable[Union[int, str]])

  def test_multiple_bindings_superclass(self):
    class Parent:
      pass

    class Child1(Parent):
      pass

    class Child2(Parent):
      pass
    var: variables.Variable[Parent] = variables.Variable(
        (variables.Binding(Child1()), variables.Binding(Child2())))
    assert_type(var, variables.Variable[Parent])

  def test_get_atomic_value(self):
    var = variables.Variable.from_value(0)
    val = var.get_atomic_value()
    assert_type(val, int)
    self.assertEqual(val, 0)

  def test_get_atomic_value_empty_variable(self):
    var = variables.Variable(())
    with self.assertRaisesRegex(ValueError, 'Too few bindings'):
      var.get_atomic_value()

  def test_get_atomic_value_multiple_bindings(self):
    var = variables.Variable((variables.Binding(0), variables.Binding('')))
    with self.assertRaisesRegex(ValueError, 'Too many bindings'):
      var.get_atomic_value()

  def test_with_true_condition(self):
    var = variables.Variable.from_value(0)
    var2 = var.with_condition(conditions.TRUE)
    self.assertIs(var2, var)

  def test_with_condition(self):
    var = variables.Variable.from_value(0)
    var2 = var.with_condition(conditions.FALSE)
    self.assertEqual(len(var2.bindings), 1)
    self.assertEqual(var2.bindings[0].value, 0)
    self.assertIs(var2.bindings[0].condition, conditions.FALSE)

  def test_values(self):
    var = variables.Variable.from_value(0)
    values = var.values
    assert_type(values, Tuple[int, ...])
    self.assertEqual(values, (0,))

  def test_with_name(self):
    var = variables.Variable.from_value(0)
    x = var.with_name('x')
    self.assertEqual(x.name, 'x')
    self.assertEqual(x.values, (0,))

  def test_with_no_name(self):
    x = variables.Variable(name='x', bindings=(variables.Binding(0),))
    var = x.with_name(None)
    self.assertIsNone(var.name)
    self.assertEqual(var.values, (0,))


if __name__ == '__main__':
  unittest.main()
