"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import logging
import os
import subprocess
import sys

from pytype import file_utils
from pytype import module_utils
from pytype.tools.analyze_project import config
import six


# Generate a default pyi for builtin and system dependencies.
DEFAULT_PYI = """
from typing import Any
def __getattr__(name) -> Any: ...
"""


class Action(object):
  CHECK = 'check'
  INFER = 'infer'
  GENERATE_DEFAULT = 'generate default'


class Stage(object):
  SINGLE_PASS = 'single pass'
  FIRST_PASS = 'first pass'
  SECOND_PASS = 'second pass'


FIRST_PASS_SUFFIX = '-1'


def _get_pytype_single_executable():
  custom_bin = os.path.join('out', 'bin', 'pytype')
  if sys.argv[0] == custom_bin:
    # The Travis type-check step uses custom pytype binaries in pytype/out/bin/.
    return [os.path.join(os.path.abspath(os.path.dirname(custom_bin)),
                         'pytype-single')]
  elif sys.executable is not None:
    return [sys.executable, '-m', 'pytype.single']
  else:
    return ['pytype-single']
PYTYPE_SINGLE = _get_pytype_single_executable()


def resolved_file_to_module(f):
  """Turn an importlab ResolvedFile into a pytype Module."""
  full_path = f.path
  target = f.short_path
  path = full_path[:-len(target)]
  name = f.module_name
  # We want to preserve __init__ in the module_name for pytype.
  if os.path.basename(full_path) == '__init__.py':
    name += '.__init__'
  return module_utils.Module(
      path=path, target=target, name=name, kind=f.__class__.__name__)


def deps_from_import_graph(import_graph):
  """Construct PytypeRunner args from an importlab.ImportGraph instance.

  Kept as a separate function so PytypeRunner can be tested independently of
  importlab.

  Args:
    import_graph: An importlab.ImportGraph instance.

  Returns:
    List of (tuple of source modules, tuple of direct deps) in dependency order.
  """
  def get_filenames(node):
    if isinstance(node, six.string_types):
      return (node,)
    else:
      # Make the build as deterministic as possible to minimize rebuilds.
      return tuple(sorted(node.nodes))
  def make_module(filename):
    return resolved_file_to_module(import_graph.provenance[filename])
  modules = []
  for node, deps in reversed(import_graph.deps_list()):
    files = tuple(
        make_module(f) for f in get_filenames(node) if not _is_type_stub(f))
    # flatten and dedup
    seen = set()
    final_deps = []
    for dep in deps:
      for d in get_filenames(dep):
        if d in seen:
          continue
        seen.add(d)
        if not _is_type_stub(d):
          final_deps.append(make_module(d))
    if files:
      modules.append((files, tuple(final_deps)))
  return modules


def _is_type_stub(f):
  _, ext = os.path.splitext(f)
  return ext in ('.pyi', '.pytd')


def _module_to_output_path(mod):
  """Convert a module to an output path."""
  path, _ = os.path.splitext(mod.target)
  if path.replace(os.path.sep, '.').endswith(mod.name):
    # Preferentially use the short path.
    return path[-len(mod.name):]
  else:
    # Fall back to computing the output path from the name, which is a last
    # resort because it messes up hidden files. Since such files aren't valid
    # python packages anyway, we preserve any leading '.' in order to not
    # create a file directly in / (which would likely cause a crash with a
    # permission error) and let the rest of the path be mangled.
    return mod.name[0] + mod.name[1:].replace('.', os.path.sep)


def get_imports_map(deps, module_to_imports_map, module_to_output):
  """Get a short path -> full path map for the given deps."""
  imports_map = {}
  for m in deps:
    if m in module_to_imports_map:
      imports_map.update(module_to_imports_map[m])
    imports_map[_module_to_output_path(m)] = module_to_output[m]
  return imports_map


class PytypeRunner(object):
  """Runs pytype over an import graph."""

  def __init__(self, conf, sorted_sources):
    self.filenames = set(conf.inputs)  # files to type-check
    # all source modules as a sequence of (module, direct_deps)
    self.sorted_sources = sorted_sources
    self.python_version = conf.python_version
    self.pyi_dir = os.path.join(conf.output, 'pyi')
    self.imports_dir = os.path.join(conf.output, 'imports')
    self.ninja_file = os.path.join(conf.output, 'build.ninja')
    self.custom_options = [
        (k, getattr(conf, k)) for k in set(conf.__slots__) - set(config.ITEMS)]
    self.keep_going = conf.keep_going
    self.jobs = conf.jobs

  def set_custom_options(self, flags_with_values, binary_flags):
    """Merge self.custom_options into flags_with_values and binary_flags."""
    for dest, value in self.custom_options:
      arg_info = config.get_pytype_single_item(dest).arg_info
      if arg_info.to_command_line:
        value = arg_info.to_command_line(value)
      if isinstance(value, bool):
        if value:
          binary_flags.add(arg_info.flag)
        else:
          binary_flags.discard(arg_info.flag)
      elif value:
        flags_with_values[arg_info.flag] = str(value)

  def get_pytype_command_for_ninja(self, report_errors):
    """Get the command line for running pytype."""
    exe = PYTYPE_SINGLE
    flags_with_values = {
        '--imports_info': '$imports',
        '-V': self.python_version,
        '-o': '$out',
        '--module-name': '$module',
    }
    binary_flags = {
        '--quick',
        '--analyze-annotated' if report_errors else '--no-report-errors',
        '--nofail',
    }
    if report_errors:
      self.set_custom_options(flags_with_values, binary_flags)
    # Order the flags so that ninja recognizes commands across runs.
    return (
        exe +
        list(sum(sorted(flags_with_values.items()), ())) +
        sorted(binary_flags) +
        ['$in']
    )

  def make_imports_dir(self):
    try:
      file_utils.makedirs(self.imports_dir)
    except OSError:
      logging.error('Could not create imports directory: %s', self.imports_dir)
      return False
    return True

  def write_default_pyi(self):
    """Write a default pyi file."""
    output = os.path.join(self.imports_dir, 'default.pyi')
    with open(output, 'w') as f:
      f.write(DEFAULT_PYI)
    return output

  def write_imports(self, module_name, imports_map, suffix):
    """Write a .imports file."""
    output = os.path.join(self.imports_dir, module_name + '.imports' + suffix)
    with open(output, 'w') as f:
      for item in imports_map.items():
        f.write('%s %s\n' % item)
    return output

  def get_module_action(self, module):
    """Get the action for the given module.

    Args:
      module: A module_utils.Module object.

    Returns:
      An Action object, or None for a non-Python file.
    """
    f = module.full_path
    # Report errors for files we are analysing directly.
    if f in self.filenames:
      action = Action.CHECK
      report = logging.warning
    else:
      action = Action.INFER
      report = logging.info
    # For builtin and system files, do not attempt to generate a pyi.
    if module.kind in ('Builtin', 'System'):
      action = Action.GENERATE_DEFAULT
      report('%s: %s module %s', action, module.kind, module.name)
    return action

  def yield_sorted_modules(self):
    """Yield modules from our sorted source files."""
    for group, deps in self.sorted_sources:
      modules = []
      for module in group:
        action = self.get_module_action(module)
        if action:
          modules.append((module, action))
      if len(modules) == 1:
        yield modules[0] + (deps, Stage.SINGLE_PASS)
      else:
        # If we have a cycle we run pytype over the files twice. So that we
        # don't fail on missing dependencies, we'll ignore errors the first
        # time and add the cycle itself to the dependencies the second time.
        second_pass_deps = []
        for module, action in modules:
          second_pass_deps.append(module)
          if action == Action.CHECK:
            action = Action.INFER
          yield module, action, deps, Stage.FIRST_PASS
        deps += tuple(second_pass_deps)
        for module, action in modules:
          # We don't need to run generate_default twice
          if action != Action.GENERATE_DEFAULT:
            yield module, action, deps, Stage.SECOND_PASS

  def write_ninja_preamble(self):
    """Write out the pytype-single commands that the build will call."""
    with open(self.ninja_file, 'w') as f:
      for action, report_errors in ((Action.INFER, False),
                                    (Action.CHECK, True)):
        command = ' '.join(
            self.get_pytype_command_for_ninja(report_errors=report_errors))
        logging.info('%s command: %s', action, command)
        f.write(
            'rule {action}\n'
            '  command = {command}\n'
            '  description = {action} $module\n'.format(
                action=action, command=command)
        )

  def write_build_statement(self, module, action, deps, imports, suffix):
    """Write a build statement for the given module.

    Args:
      module: A module_utils.Module object.
      action: An Action object.
      deps: The module's dependencies.
      imports: An imports file.
      suffix: An output file suffix.

    Returns:
      The expected output of the build statement.
    """
    output = os.path.join(self.pyi_dir,
                          _module_to_output_path(module) + '.pyi' + suffix)
    logging.info('%s %s\n  imports: %s\n  deps: %s\n  output: %s',
                 action, module.name, imports, deps, output)
    with open(self.ninja_file, 'a') as f:
      f.write('build {output}: {action} {input}{deps}\n'
              '  imports = {imports}\n'
              '  module = {module}\n'.format(
                  output=output,
                  action=action,
                  input=module.full_path,
                  deps=' | ' + ' '.join(deps) if deps else '',
                  imports=imports,
                  module=module.name))
    return output

  def setup_build(self):
    """Write out the full build.ninja file.

    Returns:
      All files with build statements.
    """
    if not self.make_imports_dir():
      return set()
    default_output = self.write_default_pyi()
    self.write_ninja_preamble()
    files = set()
    module_to_imports_map = {}
    module_to_output = {}
    for module, action, deps, stage in self.yield_sorted_modules():
      if files >= self.filenames:
        logging.info('skipped: %s %s (%s)', action, module.name, stage)
        continue
      if action == Action.GENERATE_DEFAULT:
        module_to_output[module] = default_output
        continue
      if stage == Stage.SINGLE_PASS:
        files.add(module.full_path)
        suffix = ''
      elif stage == Stage.FIRST_PASS:
        suffix = FIRST_PASS_SUFFIX
      else:
        assert stage == Stage.SECOND_PASS
        files.add(module.full_path)
        suffix = ''
      imports_map = module_to_imports_map[module] = get_imports_map(
          deps, module_to_imports_map, module_to_output)
      imports = self.write_imports(module.name, imports_map, suffix)
      # Don't depend on default.pyi, since it's regenerated every time.
      deps = tuple(module_to_output[m] for m in deps
                   if module_to_output[m] != default_output)
      module_to_output[module] = self.write_build_statement(
          module, action, deps, imports, suffix)
    return files

  def build(self):
    """Execute the build.ninja file."""
    # -k N     keep going until N jobs fail (0 means infinity)
    # -C DIR   change to DIR before doing anything else
    # -j N     run N jobs in parallel (0 means infinity)
    # -v       show all command lines while building
    k = '0' if self.keep_going else '1'
    c = os.path.dirname(self.ninja_file)
    command = ['ninja', '-k', k, '-C', c, '-j', str(self.jobs)]
    if logging.getLogger().isEnabledFor(logging.INFO):
      command.append('-v')
    return subprocess.call(command)

  def run(self):
    """Run pytype over the project."""
    logging.info('------------- Starting pytype run. -------------')
    files_to_analyze = self.setup_build()
    num_sources = len(self.filenames & files_to_analyze)
    print('Analyzing %d sources with %d local dependencies' %
          (num_sources, len(files_to_analyze) - num_sources))
    ret = self.build()
    if not ret:
      print('Success: no errors found')
    return ret
