from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import classes
from pytype.rewrite.abstract import functions

import unittest


class ClassTest(unittest.TestCase):

  def test_get_attribute(self):
    x = base.PythonConstant(5)
    cls = classes.BaseClass('X', {'x': x})
    self.assertEqual(cls.get_attribute('x'), x)

  def test_get_nonexistent_attribute(self):
    cls = classes.BaseClass('X', {})
    self.assertIsNone(cls.get_attribute('x'))

  def test_instantiate(self):
    cls = classes.BaseClass('X', {})
    instance = cls.instantiate()
    self.assertEqual(instance.cls, cls)

  def test_call(self):
    cls = classes.BaseClass('X', {})
    instance = cls.call(functions.Args()).get_return_value()
    self.assertEqual(instance.cls, cls)


class MutableInstanceTest(unittest.TestCase):

  def test_get_instance_attribute(self):
    cls = classes.BaseClass('X', {})
    instance = classes.MutableInstance(cls)
    instance.members['x'] = base.PythonConstant(3)
    self.assertEqual(instance.get_attribute('x'), base.PythonConstant(3))

  def test_get_class_attribute(self):
    cls = classes.BaseClass('X', {'x': base.PythonConstant(3)})
    instance = classes.MutableInstance(cls)
    self.assertEqual(instance.get_attribute('x'), base.PythonConstant(3))

  def test_set_attribute(self):
    cls = classes.BaseClass('X', {})
    instance = classes.MutableInstance(cls)
    instance.set_attribute('x', base.PythonConstant(3))
    self.assertEqual(instance.members['x'], base.PythonConstant(3))


class FrozenInstanceTest(unittest.TestCase):

  def test_get_attribute(self):
    cls = classes.BaseClass('X', {})
    mutable_instance = classes.MutableInstance(cls)
    mutable_instance.set_attribute('x', base.PythonConstant(3))
    instance = mutable_instance.freeze()
    self.assertEqual(instance.get_attribute('x'), base.PythonConstant(3))


if __name__ == '__main__':
  unittest.main()
