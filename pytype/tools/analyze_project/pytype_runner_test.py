"""Tests for pytype_runner.py."""

import collections
import os

from pytype import config as pytype_config
from pytype import file_utils
from pytype import module_utils
from pytype.tools.analyze_project import parse_args
from pytype.tools.analyze_project import pytype_runner
import unittest


# Convenience aliases.
# pylint: disable=invalid-name
Module = module_utils.Module
Action = pytype_runner.Action
# pylint: enable=invalid-name


# named 'Local' to match importlab.resolve.Local
ImportlabModule = collections.namedtuple('Local', 'path short_path module_name')


class FakeImportGraph(object):
  """Just enough of the ImportGraph interface to run tests."""

  def __init__(self, source_files, provenance):
    self.source_files = source_files
    self.provenance = provenance

  def sorted_source_files(self):
    return [[x] for x in self.source_files]


class TestDepsFromImportGraph(unittest.TestCase):
  """Test deps_from_import_graph."""

  def setUp(self):
    init = ImportlabModule('/foo/bar/__init__.py', 'bar/__init__.py', 'bar')
    a = ImportlabModule('/foo/bar/a.py', 'bar/a.py', 'bar.a')
    b = ImportlabModule('/foo/bar/b.py', 'bar/b.py', 'bar.b')
    self.sources = [x.path for x in [init, a, b]]
    self.provenance = {x.path: x for x in [init, a, b]}
    self.graph = FakeImportGraph(self.sources, self.provenance)

  def testBasic(self):
    deps = pytype_runner.deps_from_import_graph(self.graph)
    expected = [
        [Module('/foo/', 'bar/__init__.py', 'bar.__init__')],
        [Module('/foo/', 'bar/a.py', 'bar.a')],
        [Module('/foo/', 'bar/b.py', 'bar.b')]
    ]
    self.assertEqual(deps, expected)


class TestBase(unittest.TestCase):
  """Base class for tests using a parser."""

  @classmethod
  def setUpClass(cls):
    cls.parser = parse_args.make_parser()


class TestGetRunCmd(TestBase):
  """Test PytypeRunner.get_pytype_args()."""

  def setUp(self):
    self.runner = pytype_runner.PytypeRunner(
        self.parser.config_from_defaults(), [])

  def get_basic_options(self, report_errors=False):
    module = Module('foo', 'bar.py', 'bar')
    args = self.runner.get_pytype_args(module, report_errors)
    return pytype_config.Options(args)

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
    # Disable error reporting
    options = self.get_basic_options(report_errors=False)
    self.assertFalse(options.report_errors)
    self.assertFalse(options.analyze_annotated)
    # Enable error reporting
    options = self.get_basic_options(report_errors=True)
    self.assertTrue(options.report_errors)
    self.assertTrue(options.analyze_annotated)

  def test_hidden_dir(self):
    module = Module('', '.foo/bar.py', '.foo.bar')
    args = self.runner.get_pytype_args(module, report_errors=False)
    options = pytype_config.Options(args)
    self.assertEqual(options.output,
                     os.path.join(self.runner.pyi_dir, '.foo', 'bar.pyi'))

  def test_hidden_file(self):
    module = Module('', 'foo/.bar.py', 'foo..bar')
    args = self.runner.get_pytype_args(module, report_errors=False)
    options = pytype_config.Options(args)
    self.assertEqual(options.output,
                     os.path.join(self.runner.pyi_dir, 'foo', '.bar.pyi'))

  def test_hidden_file_with_path_prefix(self):
    module = Module('', 'foo/.bar.py', '.bar')
    args = self.runner.get_pytype_args(module, report_errors=False)
    options = pytype_config.Options(args)
    self.assertEqual(options.output,
                     os.path.join(self.runner.pyi_dir, '.bar.pyi'))

  def test_hidden_dir_with_path_mismatch(self):
    module = Module('', 'symlinked/foo.py', '.bar')
    args = self.runner.get_pytype_args(module, report_errors=False)
    options = pytype_config.Options(args)
    self.assertEqual(options.output,
                     os.path.join(self.runner.pyi_dir, '.bar.pyi'))

  def test_path_mismatch(self):
    module = Module('', 'symlinked/foo.py', 'bar.baz')
    args = self.runner.get_pytype_args(module, report_errors=False)
    options = pytype_config.Options(args)
    self.assertEqual(options.output,
                     os.path.join(self.runner.pyi_dir, 'bar', 'baz.pyi'))


class TestYieldSortedModules(TestBase):
  """Tests for PytypeRunner.yield_sorted_modules()."""

  def normalize(self, d):
    return file_utils.expand_path(d).rstrip(os.sep) + os.sep

  def assert_sorted_modules_equal(self, mod_gen, expected_list):
    for expected_module, expected_report_errors in expected_list:
      try:
        module, actual_report_errors = next(mod_gen)
      except StopIteration:
        raise AssertionError('Not enough modules')
      self.assertEqual(module, Module(*expected_module))
      self.assertEqual(actual_report_errors, expected_report_errors)
    try:
      next(mod_gen)
    except StopIteration:
      pass
    else:
      # Too many modules
      raise AssertionError('Too many modules')

  def make_runner(self, sources, dep, conf):
    """Allow source filenames to be passed in as modules."""
    conf.inputs = [m.full_path for m in sources]
    return pytype_runner.PytypeRunner(conf, dep)

  def test_source(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    f = Module(d, 'bar.py', 'bar')
    runner = self.make_runner([f], [[f]], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [((d, 'bar.py', 'bar'), Action.REPORT_ERRORS)])

  def test_source_and_dep(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    src = Module(d, 'bar.py', 'bar')
    dep = Module(d, 'baz.py', 'baz')
    runner = self.make_runner([src], [[dep], [src]], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [((d, 'baz.py', 'baz'), Action.IGNORE_ERRORS),
         ((d, 'bar.py', 'bar'), Action.REPORT_ERRORS)])

  def test_cycle(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    src = Module(d, 'bar.py', 'bar')
    dep = Module(d, 'baz.py', 'baz')
    runner = self.make_runner([src], [[dep, src]], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [((d, 'baz.py', 'baz'), Action.IGNORE_ERRORS),
         ((d, 'bar.py', 'bar'), Action.IGNORE_ERRORS),
         ((d, 'baz.py', 'baz'), Action.IGNORE_ERRORS),
         ((d, 'bar.py', 'bar'), Action.REPORT_ERRORS)])

  def test_non_py_dep(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    dep = Module(d, 'bar.so', 'bar')
    runner = self.make_runner([], [[dep]], conf)
    self.assert_sorted_modules_equal(runner.yield_sorted_modules(), [])

  def test_system_dep(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    external = self.normalize('quux/')
    conf.pythonpath = [d]
    mod = (external, 'bar/baz.py', 'bar.baz', 'System')
    dep = Module(*mod)
    runner = self.make_runner([], [[dep]], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(), [(mod, Action.GENERATE_DEFAULT)])


if __name__ == '__main__':
  unittest.main()
