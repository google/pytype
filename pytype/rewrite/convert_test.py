import sys

from pytype.pytd import pytd
from pytype.rewrite.abstract import abstract
from pytype.rewrite.tests import test_utils

import unittest


class ConverterTestBase(test_utils.ContextfulTestBase):

  def setUp(self):
    super().setUp()
    self.conv = self.ctx.abstract_converter


class GetModuleGlobalsTest(ConverterTestBase):

  def test_basic(self):
    module_globals = self.conv.get_module_globals(sys.version_info[:2])
    # Sanity check a random entry.
    self.assertIn('__name__', module_globals)


class PytdTypeToValueTest(ConverterTestBase):

  def test_class_type(self):
    pytd_class = pytd.Class(
        name='X', keywords=(), bases=(), methods=(), constants=(), classes=(),
        decorators=(), slots=None, template=())
    pytd_class_type = pytd.ClassType(name='X', cls=pytd_class)
    abstract_class = self.conv.pytd_type_to_value(pytd_class_type)
    self.assertIsInstance(abstract_class, abstract.SimpleClass)
    self.assertEqual(abstract_class.name, 'X')

  def test_anything_type(self):
    abstract_value = self.conv.pytd_type_to_value(pytd.AnythingType())
    self.assertEqual(abstract_value, self.ctx.singles.Any)

  def test_nothing_type(self):
    abstract_value = self.conv.pytd_type_to_value(pytd.NothingType())
    self.assertEqual(abstract_value, self.ctx.singles.Never)


if __name__ == '__main__':
  unittest.main()
