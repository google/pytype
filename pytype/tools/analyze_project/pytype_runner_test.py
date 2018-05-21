"""Tests for pytype_runner.py."""

import os
import unittest

from pytype import config as pytype_config
from pytype import file_utils
from pytype.tools.analyze_project import config
from pytype.tools.analyze_project import pytype_runner


expand = file_utils.expand_path


class TestInferModuleName(unittest.TestCase):
  """Test PytypeRunner.infer_module_name."""

  def assert_module_equal(self, module, path, target, name):
    self.assertEqual(module.path.rstrip(os.sep), path.rstrip(os.sep))
    self.assertEqual(module.target, target)
    self.assertEqual(module.name, name)

  def test_simple_name(self):
    conf = config.Config()
    conf.pythonpath = [expand('foo')]
    runner = pytype_runner.PytypeRunner([], [], conf)
    module = runner.infer_module_name(expand('foo/bar.py'))
    self.assert_module_equal(module, expand('foo'), 'bar.py', 'bar')

  def test_name_in_package(self):
    conf = config.Config()
    conf.pythonpath = [expand('foo')]
    runner = pytype_runner.PytypeRunner([], [], conf)
    module = runner.infer_module_name(expand('foo/bar/baz.py'))
    self.assert_module_equal(module, expand('foo'), 'bar/baz.py', 'bar.baz')

  def test_multiple_paths(self):
    conf = config.Config()
    conf.pythonpath = [expand('foo'), expand('bar/baz'), expand('bar')]
    runner = pytype_runner.PytypeRunner([], [], conf)
    module = runner.infer_module_name(expand('bar/baz/qux.py'))
    self.assert_module_equal(module, expand('bar/baz'), 'qux.py', 'qux')
    module = runner.infer_module_name(expand('bar/qux.py'))
    self.assert_module_equal(module, expand('bar'), 'qux.py', 'qux')

  def test_not_found(self):
    conf = config.Config()
    conf.pythonpath = ['foo']
    runner = pytype_runner.PytypeRunner([], [], conf)
    module = runner.infer_module_name(expand('bar/baz.py'))
    expected_target = expand('bar/baz.py')
    expected_name, _ = os.path.splitext(expected_target.replace(os.sep, '.'))
    self.assert_module_equal(module, '', expected_target, expected_name)


class TestGetRunCmd(unittest.TestCase):
  """Test PytypeRunner.get_run_cmd()."""

  def setUp(self):
    self.runner = pytype_runner.PytypeRunner([], [], config.Config())

  def get_basic_options(self):
    module = pytype_runner.Module('foo', 'bar.py', 'bar')
    return pytype_config.Options(self.runner.get_run_cmd(module, False))

  def test_pythonpath(self):
    self.assertEqual(self.get_basic_options().pythonpath, [self.runner.pyi_dir])

  def test_python_version(self):
    self.assertEqual(
        self.get_basic_options().python_version,
        tuple(int(i) for i in self.runner.python_version.split('.')))

  def test_output(self):
    self.assertEqual(self.get_basic_options().output,
                     os.path.join(self.runner.pyi_dir, 'bar.pyi'))

  def test_quick(self):
    self.assertTrue(self.get_basic_options().quick)

  def test_module_name(self):
    self.assertEqual(self.get_basic_options().module_name, 'bar')

  def test_error_reporting(self):
    module = pytype_runner.Module('foo', 'bar.py', 'bar')
    options = pytype_config.Options(
        self.runner.get_run_cmd(module, report_errors=False))
    self.assertFalse(options.report_errors)
    self.assertFalse(options.analyze_annotated)
    options = pytype_config.Options(
        self.runner.get_run_cmd(module, report_errors=True))
    self.assertTrue(options.report_errors)
    self.assertTrue(options.analyze_annotated)


class TestYieldSortedModules(unittest.TestCase):
  """Tests for PytypeRunner.yield_sorted_modules()."""

  def normalize(self, d):
    return expand(d).rstrip(os.sep) + os.sep

  def assert_sorted_modules_equal(self, mod_gen, expected_list):
    for path, target, name, expected_report_errors in expected_list:
      try:
        module, actual_report_errors = next(mod_gen)
      except StopIteration:
        raise AssertionError('Not enough modules')
      self.assertEqual(module, pytype_runner.Module(path, target, name))
      self.assertEqual(actual_report_errors, expected_report_errors)
    try:
      next(mod_gen)
    except StopIteration:
      pass
    else:
      # Too many modules
      raise AssertionError('Too many modules')

  def test_source(self):
    conf = config.Config()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    f = os.path.join(d, 'bar.py')
    runner = pytype_runner.PytypeRunner([f], [[f]], conf)
    self.assert_sorted_modules_equal(runner.yield_sorted_modules(),
                                     [(d, 'bar.py', 'bar', True)])

  def test_source_and_dep(self):
    conf = config.Config()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    source = os.path.join(d, 'bar.py')
    dep = os.path.join(d, 'baz.py')
    runner = pytype_runner.PytypeRunner([source], [[dep], [source]], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [(d, 'baz.py', 'baz', False), (d, 'bar.py', 'bar', True)])

  def test_cycle(self):
    conf = config.Config()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    source = os.path.join(d, 'bar.py')
    dep = os.path.join(d, 'baz.py')
    runner = pytype_runner.PytypeRunner([source], [[dep, source]], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [(d, 'baz.py', 'baz', False), (d, 'bar.py', 'bar', False),
         (d, 'baz.py', 'baz', False), (d, 'bar.py', 'bar', True)])

  def test_non_py_dep(self):
    conf = config.Config()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    dep = os.path.join(d, 'bar.so')
    runner = pytype_runner.PytypeRunner([], [[dep]], conf)
    self.assert_sorted_modules_equal(runner.yield_sorted_modules(), [])

  def test_non_pythonpath_dep(self):
    conf = config.Config()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    dep = expand('bar/baz.py')
    runner = pytype_runner.PytypeRunner([], [[dep]], conf)
    self.assert_sorted_modules_equal(runner.yield_sorted_modules(), [])


if __name__ == '__main__':
  unittest.main()
