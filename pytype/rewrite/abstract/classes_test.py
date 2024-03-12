from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import classes

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


if __name__ == '__main__':
  unittest.main()
