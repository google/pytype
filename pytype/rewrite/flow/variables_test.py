from typing import Union

from pytype.rewrite.flow import variables
from typing_extensions import assert_type

import unittest


class ConditionTest(unittest.TestCase):
  pass


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


if __name__ == '__main__':
  unittest.main()
