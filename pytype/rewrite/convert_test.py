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


class PytdFunctionToValueTest(ConverterTestBase):

  def test_basic(self):
    pytd_param = pytd.Parameter(
        name='x',
        type=pytd.AnythingType(),
        kind=pytd.ParameterKind.REGULAR,
        optional=False,
        mutated_type=None,
    )
    pytd_sig = pytd.Signature(
        params=(pytd_param,),
        starargs=None,
        starstarargs=None,
        return_type=pytd.AnythingType(),
        exceptions=(),
        template=(),
    )
    pytd_func = pytd.Function(
        name='f', signatures=(pytd_sig,), kind=pytd.MethodKind.METHOD)
    func = self.conv.pytd_function_to_value(pytd_func)
    self.assertIsInstance(func, abstract.PytdFunction)
    self.assertEqual(func.name, 'f')
    self.assertEqual(len(func.signatures), 1)
    self.assertEqual(repr(func.signatures[0]), 'def f(x: Any) -> Any')


if __name__ == '__main__':
  unittest.main()
