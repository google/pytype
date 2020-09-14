"""Tests for pytype_runner.py."""

import collections
import os

from pytype import config as pytype_config
from pytype import file_utils
from pytype import module_utils
from pytype.tools.analyze_project import parse_args
from pytype.tools.analyze_project import pytype_runner
import six
import unittest


# Convenience aliases.
# pylint: disable=invalid-name
Module = module_utils.Module
Action = pytype_runner.Action
Stage = pytype_runner.Stage
# pylint: enable=invalid-name


# named 'Local' to match importlab.resolve.Local
ImportlabModule = collections.namedtuple('Local', 'path short_path module_name')


ExpectedBuildStatement = collections.namedtuple(
    'ExpectedBuildStatement',
    ('output', 'action', 'input', 'deps', 'imports', 'module'))


# number of lines in the build.ninja preamble
_PREAMBLE_LENGTH = 6


class FakeImportGraph:
  """Just enough of the ImportGraph interface to run tests."""

  def __init__(self, source_files, provenance, source_to_deps):
    self.source_files = source_files
    self.provenance = provenance
    self.source_to_deps = source_to_deps

  def deps_list(self):
    return [(x, self.source_to_deps[x]) for x in reversed(self.source_files)]


def make_runner(sources, dep, conf):
  conf.inputs = [m.full_path for m in sources]
  return pytype_runner.PytypeRunner(conf, dep)


class TestResolvedFileToModule(unittest.TestCase):
  """Test resolved_file_to_module."""

  def test_basic(self):
    resolved_file = ImportlabModule('foo/bar.py', 'bar.py', 'bar')
    self.assertEqual(pytype_runner.resolved_file_to_module(resolved_file),
                     Module('foo/', 'bar.py', 'bar', 'Local'))

  def test_preserve_init(self):
    resolved_file = ImportlabModule(
        'foo/bar/__init__.py', 'bar/__init__.py', 'bar')
    self.assertEqual(pytype_runner.resolved_file_to_module(resolved_file),
                     Module('foo/', 'bar/__init__.py', 'bar.__init__', 'Local'))


class TestDepsFromImportGraph(unittest.TestCase):
  """Test deps_from_import_graph."""

  def setUp(self):
    super().setUp()
    init = ImportlabModule('/foo/bar/__init__.py', 'bar/__init__.py', 'bar')
    a = ImportlabModule('/foo/bar/a.py', 'bar/a.py', 'bar.a')
    b = ImportlabModule('/foo/bar/b.py', 'bar/b.py', 'bar.b')
    self.sources = [x.path for x in [init, a, b]]
    self.provenance = {x.path: x for x in [init, a, b]}

  def test_basic(self):
    graph = FakeImportGraph(self.sources, self.provenance,
                            collections.defaultdict(list))
    deps = pytype_runner.deps_from_import_graph(graph)
    expected = [
        ((Module('/foo/', 'bar/__init__.py', 'bar.__init__'),), ()),
        ((Module('/foo/', 'bar/a.py', 'bar.a'),), ()),
        ((Module('/foo/', 'bar/b.py', 'bar.b'),), ()),
    ]
    self.assertEqual(deps, expected)

  def test_duplicate_deps(self):
    graph = FakeImportGraph(
        self.sources, self.provenance,
        collections.defaultdict(lambda: [self.sources[0]] * 2))
    deps = pytype_runner.deps_from_import_graph(graph)
    init = Module('/foo/', 'bar/__init__.py', 'bar.__init__')
    expected = [
        ((init,), (init,)),
        ((Module('/foo/', 'bar/a.py', 'bar.a'),), (init,)),
        ((Module('/foo/', 'bar/b.py', 'bar.b'),), (init,)),
    ]
    self.assertEqual(deps, expected)

  def test_pyi_src(self):
    pyi_mod = ImportlabModule('/foo/bar/c.pyi', 'bar/c.pyi', 'bar.c')
    provenance = {pyi_mod.path: pyi_mod}
    provenance.update(self.provenance)
    graph = FakeImportGraph(self.sources + [pyi_mod.path], provenance,
                            collections.defaultdict(list))
    deps = pytype_runner.deps_from_import_graph(graph)
    expected = [
        ((Module('/foo/', 'bar/__init__.py', 'bar.__init__'),), ()),
        ((Module('/foo/', 'bar/a.py', 'bar.a'),), ()),
        ((Module('/foo/', 'bar/b.py', 'bar.b'),), ()),
    ]
    self.assertEqual(deps, expected)

  def test_pyi_dep(self):
    pyi_mod = ImportlabModule('/foo/bar/c.pyi', 'bar/c.pyi', 'bar.c')
    graph = FakeImportGraph(self.sources, self.provenance,
                            collections.defaultdict(lambda: [pyi_mod.path]))
    deps = pytype_runner.deps_from_import_graph(graph)
    expected = [
        ((Module('/foo/', 'bar/__init__.py', 'bar.__init__'),), ()),
        ((Module('/foo/', 'bar/a.py', 'bar.a'),), ()),
        ((Module('/foo/', 'bar/b.py', 'bar.b'),), ()),
    ]
    self.assertEqual(deps, expected)


class TestBase(unittest.TestCase):
  """Base class for tests using a parser."""

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls.parser = parse_args.make_parser()


class TestCustomOptions(TestBase):
  """Test PytypeRunner.set_custom_options."""

  def setUp(self):
    super().setUp()
    self.conf = self.parser.config_from_defaults()

  # --disable tests a flag with a string value.

  def test_disable(self):
    self.conf.disable = ['import-error', 'name-error']
    runner = make_runner([], [], self.conf)
    flags_with_values = {}
    runner.set_custom_options(flags_with_values, set())
    self.assertEqual(flags_with_values['--disable'], 'import-error,name-error')

  def test_no_disable(self):
    self.conf.disable = []
    runner = make_runner([], [], self.conf)
    flags_with_values = {}
    runner.set_custom_options(flags_with_values, set())
    self.assertFalse(flags_with_values)

  # --no-report-errors tests a binary flag with a custom to_command_line.

  def test_report_errors(self):
    self.conf.report_errors = True
    runner = make_runner([], [], self.conf)
    binary_flags = {'--no-report-errors'}
    runner.set_custom_options({}, binary_flags)
    self.assertFalse(binary_flags)

  def test_no_report_errors(self):
    self.conf.report_errors = False
    runner = make_runner([], [], self.conf)
    binary_flags = set()
    runner.set_custom_options({}, binary_flags)
    self.assertEqual(binary_flags, {'--no-report-errors'})

  def test_report_errors_default(self):
    self.conf.report_errors = True
    runner = make_runner([], [], self.conf)
    binary_flags = set()
    runner.set_custom_options({}, binary_flags)
    self.assertFalse(binary_flags)

  # --protocols tests a binary flag whose value is passed through transparently.

  def test_protocols(self):
    self.conf.protocols = True
    runner = make_runner([], [], self.conf)
    binary_flags = set()
    runner.set_custom_options({}, binary_flags)
    self.assertEqual(binary_flags, {'--protocols'})

  def test_no_protocols(self):
    self.conf.protocols = False
    runner = make_runner([], [], self.conf)
    binary_flags = {'--protocols'}
    runner.set_custom_options({}, binary_flags)
    self.assertFalse(binary_flags)

  def test_no_protocols_default(self):
    self.conf.protocols = False
    runner = make_runner([], [], self.conf)
    binary_flags = set()
    runner.set_custom_options({}, binary_flags)
    self.assertFalse(binary_flags)


class TestGetRunCmd(TestBase):
  """Test PytypeRunner.get_pytype_command_for_ninja()."""

  def setUp(self):
    super().setUp()
    self.runner = make_runner([], [], self.parser.config_from_defaults())

  def get_options(self, args):
    nargs = len(pytype_runner.PYTYPE_SINGLE)
    self.assertEqual(args[:nargs], pytype_runner.PYTYPE_SINGLE)
    args = args[nargs:]
    start, end = args.index('--imports_info'), args.index('$imports')
    self.assertEqual(end-start, 1)
    args.pop(end)
    args.pop(start)
    return pytype_config.Options(args, command_line=True)

  def get_basic_options(self, report_errors=False):
    return self.get_options(
        self.runner.get_pytype_command_for_ninja(report_errors))

  def test_python_version(self):
    self.assertEqual(
        self.get_basic_options().python_version,
        tuple(int(i) for i in self.runner.python_version.split('.')))

  def test_output(self):
    self.assertEqual(self.get_basic_options().output, '$out')

  def test_quick(self):
    self.assertTrue(self.get_basic_options().quick)

  def test_module_name(self):
    self.assertEqual(self.get_basic_options().module_name, '$module')

  def test_error_reporting(self):
    # Disable error reporting
    options = self.get_basic_options(report_errors=False)
    self.assertFalse(options.report_errors)
    self.assertFalse(options.analyze_annotated)
    # Enable error reporting
    options = self.get_basic_options(report_errors=True)
    self.assertTrue(options.report_errors)
    self.assertTrue(options.analyze_annotated)

  def test_custom_option(self):
    custom_conf = self.parser.config_from_defaults()
    custom_conf.disable = ['import-error', 'name-error']
    self.runner = make_runner([], [], custom_conf)
    args = self.runner.get_pytype_command_for_ninja(report_errors=True)
    options = self.get_options(args)
    self.assertEqual(options.disable, ['import-error', 'name-error'])


class TestGetModuleAction(TestBase):
  """Tests for PytypeRunner.get_module_action."""

  def test_check(self):
    sources = [Module('', 'foo.py', 'foo')]
    runner = make_runner(sources, [], self.parser.config_from_defaults())
    self.assertEqual(runner.get_module_action(sources[0]),
                     pytype_runner.Action.CHECK)

  def test_infer(self):
    runner = make_runner([], [], self.parser.config_from_defaults())
    self.assertEqual(runner.get_module_action(Module('', 'foo.py', 'foo')),
                     pytype_runner.Action.INFER)

  def test_generate_default(self):
    runner = make_runner([], [], self.parser.config_from_defaults())
    self.assertEqual(
        runner.get_module_action(Module('', 'foo.py', 'foo', 'System')),
        pytype_runner.Action.GENERATE_DEFAULT)


class TestYieldSortedModules(TestBase):
  """Tests for PytypeRunner.yield_sorted_modules()."""

  def normalize(self, d):
    return file_utils.expand_path(d).rstrip(os.sep) + os.sep

  def assert_sorted_modules_equal(self, mod_gen, expected_list):
    for (expected_mod,
         expected_report_errors,
         expected_deps,
         expected_stage) in expected_list:
      try:
        mod, actual_report_errors, actual_deps, actual_stage = next(mod_gen)
      except StopIteration as e:
        raise AssertionError('Not enough modules') from e
      self.assertEqual(mod, expected_mod)
      self.assertEqual(actual_report_errors, expected_report_errors)
      self.assertEqual(actual_deps, expected_deps)
      self.assertEqual(actual_stage, expected_stage)
    try:
      next(mod_gen)
    except StopIteration:
      pass
    else:
      # Too many modules
      raise AssertionError('Too many modules')

  def test_source(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    f = Module(d, 'bar.py', 'bar')
    runner = make_runner([f], [((f,), ())], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [(f, Action.CHECK, (), Stage.SINGLE_PASS)])

  def test_source_and_dep(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    src = Module(d, 'bar.py', 'bar')
    dep = Module(d, 'baz.py', 'baz')
    runner = make_runner([src], [((dep,), ()), ((src,), (dep,))], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [(dep, Action.INFER, (), Stage.SINGLE_PASS),
         (src, Action.CHECK, (dep,), Stage.SINGLE_PASS)])

  def test_cycle(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    conf.pythonpath = [d]
    src = Module(d, 'bar.py', 'bar')
    dep = Module(d, 'baz.py', 'baz')
    runner = make_runner([src], [((dep, src), ())], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [(dep, Action.INFER, (), Stage.FIRST_PASS),
         (src, Action.INFER, (), Stage.FIRST_PASS),
         (dep, Action.INFER, (dep, src), Stage.SECOND_PASS),
         (src, Action.CHECK, (dep, src), Stage.SECOND_PASS)])

  def test_system_dep(self):
    conf = self.parser.config_from_defaults()
    d = self.normalize('foo/')
    external = self.normalize('quux/')
    conf.pythonpath = [d]
    mod = (external, 'bar/baz.py', 'bar.baz', 'System')
    dep = Module(*mod)
    runner = make_runner([], [((dep,), ())], conf)
    self.assert_sorted_modules_equal(
        runner.yield_sorted_modules(),
        [(mod, Action.GENERATE_DEFAULT, (), Stage.SINGLE_PASS)])


class TestNinjaPreamble(TestBase):
  """Tests for PytypeRunner.write_ninja_preamble."""

  def test_write(self):
    conf = self.parser.config_from_defaults()
    with file_utils.Tempdir() as d:
      conf.output = d.path
      runner = make_runner([], [], conf)
      runner.write_ninja_preamble()
      with open(runner.ninja_file, 'r') as f:
        preamble = f.read().splitlines()
    self.assertEqual(len(preamble), _PREAMBLE_LENGTH)
    # The preamble consists of triples of lines of the format:
    # rule {name}
    #   command = pytype-single {args} $in
    #   description = {name} $module
    # Check that the lines cycle through these patterns.
    for i, line in enumerate(preamble):
      if not i % 3:
        six.assertRegex(self, line, r'rule \w*')
      elif i % 3 == 1:
        expected = r'  command = {} .* \$in'.format(
            ' '.join(pytype_runner.PYTYPE_SINGLE))
        six.assertRegex(self, line, expected)
      else:
        six.assertRegex(self, line, r'  description = \w* \$module')


class TestNinjaBuildStatement(TestBase):
  """Tests for PytypeRunner.write_build_statement."""

  def write_build_statement(self, *args, **kwargs):
    conf = self.parser.config_from_defaults()
    with file_utils.Tempdir() as d:
      conf.output = d.path
      runner = make_runner([], [], conf)
      output = runner.write_build_statement(*args, **kwargs)
      with open(runner.ninja_file, 'r') as f:
        return runner, output, f.read().splitlines()

  def assertOutputMatches(self, module, expected_output):
    runner, output, _ = self.write_build_statement(
        module, Action.CHECK, set(), 'imports', '')
    self.assertEqual(output, os.path.join(runner.pyi_dir, expected_output))

  def test_check(self):
    _, output, build_statement = self.write_build_statement(
        Module('', 'foo.py', 'foo'), Action.CHECK, set(), 'imports', '')
    self.assertEqual(build_statement[0], 'build %s: check foo.py' % output)

  def test_infer(self):
    _, output, build_statement = self.write_build_statement(
        Module('', 'foo.py', 'foo'), Action.INFER, set(), 'imports', '')
    self.assertEqual(build_statement[0], 'build %s: infer foo.py' % output)

  def test_deps(self):
    _, output, _ = self.write_build_statement(
        Module('', 'foo.py', 'foo'), Action.INFER, set(), 'imports', '')
    _, _, build_statement = self.write_build_statement(
        Module('', 'bar.py', 'bar'), Action.CHECK, {output}, 'imports', '')
    self.assertTrue(build_statement[0].endswith(' | ' + output))

  def test_imports(self):
    _, _, build_statement = self.write_build_statement(
        Module('', 'foo.py', 'foo'), Action.CHECK, set(), 'imports', '')
    self.assertIn('  imports = imports', build_statement)

  def test_module(self):
    _, _, build_statement = self.write_build_statement(
        Module('', 'foo.py', 'foo'), Action.CHECK, set(), 'imports', '')
    self.assertIn('  module = foo', build_statement)

  def test_suffix(self):
    runner, output, _ = self.write_build_statement(
        Module('', 'foo.py', 'foo'), Action.CHECK, set(), 'imports', '-1')
    self.assertEqual(os.path.join(runner.pyi_dir, 'foo.pyi-1'), output)

  def test_hidden_dir(self):
    self.assertOutputMatches(Module('', '.foo/bar.py', '.foo.bar'),
                             os.path.join('.foo', 'bar.pyi'))

  def test_hidden_file(self):
    self.assertOutputMatches(Module('', 'foo/.bar.py', 'foo..bar'),
                             os.path.join('foo', '.bar.pyi'))

  def test_hidden_file_with_path_prefix(self):
    self.assertOutputMatches(Module('', 'foo/.bar.py', '.bar'),
                             os.path.join('.bar.pyi'))

  def test_hidden_dir_with_path_mismatch(self):
    self.assertOutputMatches(Module('', 'symlinked/foo.py', '.bar'), '.bar.pyi')

  def test_path_mismatch(self):
    self.assertOutputMatches(Module('', 'symlinked/foo.py', 'bar.baz'),
                             os.path.join('bar', 'baz.pyi'))


class TestNinjaBody(TestBase):
  """Test PytypeRunner.setup_build."""

  def setUp(self):
    super().setUp()
    self.conf = self.parser.config_from_defaults()

  def assertBuildStatementMatches(self, build_statement, expected):
    self.assertEqual(build_statement[0],
                     'build {output}: {action} {input}{deps}'.format(
                         output=expected.output,
                         action=expected.action,
                         input=expected.input,
                         deps=expected.deps))
    self.assertEqual(set(build_statement[1:]),
                     {'  imports = %s' % expected.imports,
                      '  module = %s' % expected.module})

  def test_basic(self):
    src = Module('', 'foo.py', 'foo')
    dep = Module('', 'bar.py', 'bar')
    with file_utils.Tempdir() as d:
      self.conf.output = d.path
      runner = make_runner(
          [src], [((dep,), ()), ((src,), (dep,))], self.conf)
      runner.setup_build()
      with open(runner.ninja_file, 'r') as f:
        body = f.read().splitlines()[_PREAMBLE_LENGTH:]
    self.assertBuildStatementMatches(body[0:3], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'bar.pyi'),
        action=Action.INFER,
        input='bar.py',
        deps='',
        imports=os.path.join(runner.imports_dir, 'bar.imports'),
        module='bar'))
    self.assertBuildStatementMatches(body[3:], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'foo.pyi'),
        action=Action.CHECK,
        input='foo.py',
        deps=' | ' + os.path.join(runner.pyi_dir, 'bar.pyi'),
        imports=os.path.join(runner.imports_dir, 'foo.imports'),
        module='foo'))

  def test_generate_default(self):
    src = Module('', 'foo.py', 'foo')
    dep = Module('', 'bar.py', 'bar', 'System')
    with file_utils.Tempdir() as d:
      self.conf.output = d.path
      runner = make_runner(
          [src], [((dep,), ()), ((src,), (dep,))], self.conf)
      runner.setup_build()
      with open(runner.ninja_file, 'r') as f:
        body = f.read().splitlines()[_PREAMBLE_LENGTH:]
      with open(os.path.join(runner.imports_dir, 'foo.imports'), 'r') as f:
        imports_info, = f.read().splitlines()
    self.assertBuildStatementMatches(body, ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'foo.pyi'),
        action=Action.CHECK,
        input='foo.py',
        deps='',
        imports=os.path.join(runner.imports_dir, 'foo.imports'),
        module='foo'))
    short_bar_path, bar_path = imports_info.split(' ')
    self.assertEqual(short_bar_path, 'bar')
    self.assertEqual(bar_path, os.path.join(runner.imports_dir, 'default.pyi'))

  def test_cycle(self):
    src = Module('', 'foo.py', 'foo')
    dep = Module('', 'bar.py', 'bar')
    with file_utils.Tempdir() as d:
      self.conf.output = d.path
      runner = make_runner(
          [src], [((dep, src), ())], self.conf)
      runner.setup_build()
      with open(runner.ninja_file, 'r') as f:
        body = f.read().splitlines()[_PREAMBLE_LENGTH:]
    self.assertBuildStatementMatches(body[:3], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'bar.pyi-1'),
        action=Action.INFER,
        input='bar.py',
        deps='',
        imports=os.path.join(runner.imports_dir, 'bar.imports-1'),
        module='bar'))
    self.assertBuildStatementMatches(body[3:6], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'foo.pyi-1'),
        action=Action.INFER,
        input='foo.py',
        deps='',
        imports=os.path.join(runner.imports_dir, 'foo.imports-1'),
        module='foo'))
    self.assertBuildStatementMatches(body[6:9], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'bar.pyi'),
        action=Action.INFER,
        input='bar.py',
        deps=' | %s %s' % (os.path.join(runner.pyi_dir, 'bar.pyi-1'),
                           os.path.join(runner.pyi_dir, 'foo.pyi-1')),
        imports=os.path.join(runner.imports_dir, 'bar.imports'),
        module='bar'))
    self.assertBuildStatementMatches(body[9:], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'foo.pyi'),
        action=Action.CHECK,
        input='foo.py',
        deps=' | %s %s' % (os.path.join(runner.pyi_dir, 'bar.pyi'),
                           os.path.join(runner.pyi_dir, 'foo.pyi-1')),
        imports=os.path.join(runner.imports_dir, 'foo.imports'),
        module='foo'))

  def test_cycle_with_extra_action(self):
    src = Module('', 'foo.py', 'foo')
    dep = Module('', 'bar.py', 'bar')
    with file_utils.Tempdir() as d:
      self.conf.output = d.path
      # When `src` is analyzed before `dep`, the second infer action on `dep`
      # should be skipped.
      runner = make_runner([src], [((src, dep), ())], self.conf)
      runner.setup_build()
      with open(runner.ninja_file, 'r') as f:
        body = f.read().splitlines()[_PREAMBLE_LENGTH:]
    self.assertBuildStatementMatches(body[:3], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'foo.pyi-1'),
        action=Action.INFER,
        input='foo.py',
        deps='',
        imports=os.path.join(runner.imports_dir, 'foo.imports-1'),
        module='foo'))
    self.assertBuildStatementMatches(body[3:6], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'bar.pyi-1'),
        action=Action.INFER,
        input='bar.py',
        deps='',
        imports=os.path.join(runner.imports_dir, 'bar.imports-1'),
        module='bar'))
    self.assertBuildStatementMatches(body[6:], ExpectedBuildStatement(
        output=os.path.join(runner.pyi_dir, 'foo.pyi'),
        action=Action.CHECK,
        input='foo.py',
        deps=' | %s %s' % (os.path.join(runner.pyi_dir, 'foo.pyi-1'),
                           os.path.join(runner.pyi_dir, 'bar.pyi-1')),
        imports=os.path.join(runner.imports_dir, 'foo.imports'),
        module='foo'))


class TestImports(TestBase):
  """Test imports-related functionality."""

  def setUp(self):
    super().setUp()
    self.conf = self.parser.config_from_defaults()

  def test_write_default_pyi(self):
    with file_utils.Tempdir() as d:
      self.conf.output = d.path
      runner = make_runner([], [], self.conf)
      self.assertTrue(runner.make_imports_dir())
      output = runner.write_default_pyi()
      self.assertEqual(output, os.path.join(runner.imports_dir, 'default.pyi'))
      with open(output, 'r') as f:
        self.assertEqual(f.read(), pytype_runner.DEFAULT_PYI)

  def test_write_imports(self):
    with file_utils.Tempdir() as d:
      self.conf.output = d.path
      runner = make_runner([], [], self.conf)
      self.assertTrue(runner.make_imports_dir())
      output = runner.write_imports('mod', {'a': 'b'}, '')
      self.assertEqual(os.path.join(runner.imports_dir, 'mod.imports'), output)
      with open(output, 'r') as f:
        self.assertEqual(f.read(), 'a b\n')

  def test_get_imports_map(self):
    mod = Module('', 'foo.py', 'foo')
    deps = (mod,)
    module_to_imports_map = {mod: {'bar': '/dir/bar.pyi'}}
    module_to_output = {mod: '/dir/foo.pyi'}
    imports_map = pytype_runner.get_imports_map(
        deps, module_to_imports_map, module_to_output)
    self.assertEqual(imports_map,
                     {'foo': '/dir/foo.pyi', 'bar': '/dir/bar.pyi'})


if __name__ == '__main__':
  unittest.main()
