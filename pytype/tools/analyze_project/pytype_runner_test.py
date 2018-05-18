"""Tests for pytype_runner.py."""

import os
import unittest
from pytype.tools.analyze_project import config
from pytype.tools.analyze_project import pytype_runner


class TestInferModuleName(unittest.TestCase):
  """Test PytypeRunner.infer_module_name."""

  def assert_module_equal(self, module, path, target, name):
    if path:
      path = os.path.abspath(path)
    self.assertEqual(module.path.rstrip(os.sep), path.rstrip(os.sep))
    self.assertEqual(module.target, target)
    self.assertEqual(module.name, name)

  def test_simple_name(self):
    conf = config.Config()
    conf.projects = ['foo']
    runner = pytype_runner.PytypeRunner([], conf)
    module = runner.infer_module_name(os.path.abspath('foo/bar.py'))
    self.assert_module_equal(module, 'foo', 'bar.py', 'bar')

  def test_name_in_package(self):
    conf = config.Config()
    conf.projects = ['foo']
    runner = pytype_runner.PytypeRunner([], conf)
    module = runner.infer_module_name(os.path.abspath('foo/bar/baz.py'))
    self.assert_module_equal(module, 'foo', 'bar/baz.py', 'bar.baz')

  def test_multiple_paths(self):
    conf = config.Config()
    conf.projects = ['foo', 'bar/baz', 'bar']
    runner = pytype_runner.PytypeRunner([], conf)
    module = runner.infer_module_name(os.path.abspath('bar/baz/qux.py'))
    self.assert_module_equal(module, 'bar/baz', 'qux.py', 'qux')
    module = runner.infer_module_name(os.path.abspath('bar/qux.py'))
    self.assert_module_equal(module, 'bar', 'qux.py', 'qux')

  def test_not_found(self):
    conf = config.Config()
    conf.projects = ['foo']
    runner = pytype_runner.PytypeRunner([], conf)
    module = runner.infer_module_name(os.path.abspath('bar/baz.py'))
    expected_target = os.path.abspath('bar/baz.py')
    expected_name, _ = os.path.splitext(expected_target.replace(os.sep, '.'))
    self.assert_module_equal(module, '', expected_target, expected_name)


if __name__ == '__main__':
  unittest.main()
