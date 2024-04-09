import numbers

from pytype.rewrite.abstract import abstract
from pytype.rewrite.tests import test_utils

import unittest


class GetModuleGlobalsTest(test_utils.ContextfulTestBase):

  def test_basic(self):
    module_globals = self.ctx.abstract_loader.get_module_globals()
    # Sanity check a random entry.
    self.assertIn('__name__', module_globals)


class LoadBuiltinByNameTest(test_utils.ContextfulTestBase):

  def test_class(self):
    int_cls = self.ctx.abstract_loader.load_builtin_by_name('int')
    self.assertIsInstance(int_cls, abstract.SimpleClass)
    self.assertEqual(int_cls.name, 'int')

  def test_function(self):
    abs_func = self.ctx.abstract_loader.load_builtin_by_name('abs')
    self.assertIsInstance(abs_func, abstract.PytdFunction)
    self.assertEqual(abs_func.name, 'abs')

  def test_constant(self):
    ellipsis = self.ctx.abstract_loader.load_builtin_by_name('Ellipsis')
    self.assertIsInstance(ellipsis, abstract.PythonConstant)
    self.assertEqual(ellipsis.constant, Ellipsis)

  def test_none(self):
    self.assertIs(self.ctx.abstract_loader.load_builtin_by_name('None'),
                  self.ctx.consts[None])
    self.assertIs(self.ctx.abstract_loader.load_builtin_by_name('NoneType'),
                  self.ctx.consts[None])


class LoadRawTypeTest(test_utils.ContextfulTestBase):

  def test_builtin_type(self):
    t = self.ctx.abstract_loader.load_raw_type(int)
    self.assertIsInstance(t, abstract.SimpleClass)
    self.assertEqual(t.name, 'int')
    self.assertEqual(t.module, 'builtins')

  def test_stdlib_type(self):
    t = self.ctx.abstract_loader.load_raw_type(numbers.Number)
    self.assertIsInstance(t, abstract.SimpleClass)
    self.assertEqual(t.name, 'Number')
    self.assertEqual(t.module, 'numbers')

  def test_nonetype(self):
    t = self.ctx.abstract_loader.load_raw_type(type(None))
    self.assertIs(t, self.ctx.consts[None])


if __name__ == '__main__':
  unittest.main()
