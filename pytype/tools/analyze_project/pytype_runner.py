"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import logging
import os
import subprocess

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
    return (node,) if isinstance(node, six.string_types) else tuple(node.nodes)
  def make_module(filename):
    return resolved_file_to_module(import_graph.provenance[filename])
  modules = []
  for node, deps in reversed(import_graph.deps_list()):
    files = tuple(make_module(f) for f in get_filenames(node))
    # flatten and dedup
    seen = set()
    deps = tuple(make_module(d) for dep in deps for d in get_filenames(dep)
                 if d not in seen and not seen.add(d))
    modules.append((files, deps))
  return modules


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


class PytypeRunner(object):
  """Runs pytype over an import graph."""

  def __init__(self, conf, sorted_sources):
    self.filenames = set(conf.inputs)  # files to type-check
    # all source modules as a sequence of (module, direct_deps)
    self.sorted_sources = sorted_sources
    self.python_version = conf.python_version
    self.pyi_dir = os.path.join(conf.output, 'pyi')
    # directory for first-pass pyi files, for cycle resolution
    self.pyi_1_dir = os.path.join(conf.output, 'pyi_1')
    self.ninja_file = os.path.join(conf.output, 'build.ninja')
    self.custom_options = [
        (k, getattr(conf, k)) for k in set(conf.__slots__) - set(config.ITEMS)]

  def set_custom_options(self, flags_with_values, binary_flags):
    """Merge self.custom_options into flags_with_values and binary_flags."""
    for dest, value in self.custom_options:
      arg_info = config.PYTYPE_SINGLE_ITEMS[dest].arg_info
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
    exe = 'pytype-single'
    flags_with_values = {
        '-P': '$pythonpath',
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
    return (
        [exe] +
        list(sum(flags_with_values.items(), ())) +
        list(binary_flags) +
        ['$in']
    )

  def _output_file(self, module, pyi_dir):
    filename = _module_to_output_path(module) + '.pyi'
    return os.path.join(pyi_dir, filename)

  def generate_default_pyi(self, module):
    """Write a default pyi file for the module."""
    output = self._output_file(module, self.pyi_dir)
    # Create the output subdirectory for this file.
    output_dir = os.path.dirname(output)
    try:
      file_utils.makedirs(output_dir)
    except OSError:
      logging.error('Could not create output directory: %s', output_dir)
      return
    with open(output, 'w') as f:
      f.write(DEFAULT_PYI)
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
    if not f.endswith('.py'):
      report('skipped: non-Python file %s', f)
      return None
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
        f.write('rule %s\n  command = %s\n' % (action, command))

  def write_build_statement(self, module, action, deps, output_dir=None,
                            additional_pythonpath_dir=None):
    """Write a build statement for the given module.

    Args:
      module: A module_utils.Module object.
      action: An Action object.
      deps: The module's dependencies.
      output_dir: Optionally, the output dir. Defaults to pytype_output/pyi/.
      additional_pythonpath_dir: Optionally, a dir in which to look for previous
        output, in addition to pytype_output/pyi/.

    Returns:
      The expected output of the build statement.
    """
    output_dir = output_dir or self.pyi_dir
    output = self._output_file(module, output_dir)
    pythonpath_dirs = [self.pyi_dir]
    if additional_pythonpath_dir:
      pythonpath_dirs.append(additional_pythonpath_dir)
    logging.info('%s %s\n  pythonpath: %s\n  deps: %s\n  output: %s',
                 action, module.name, pythonpath_dirs, deps, output)
    with open(self.ninja_file, 'a') as f:
      f.write('build {output}: {action} {input}{deps}\n'
              '  pythonpath = {pythonpath}\n'
              '  module = {module}\n'.format(
                  output=output,
                  action=action,
                  input=module.full_path,
                  deps=' | ' + ' '.join(deps) if deps else '',
                  pythonpath=':'.join(pythonpath_dirs),
                  module=module.name))
    return output

  def setup_build(self):
    """Write out the full build.ninja file.

    Returns:
      All files with build statements.
    """
    self.write_ninja_preamble()
    files = set()  # all files with build statements
    module_to_output = {}  # mapping from module to expected output
    for module, action, deps, stage in self.yield_sorted_modules():
      if files >= self.filenames:
        logging.info('skipped: %s %s (%s)', action, module.name, stage)
        continue
      if action == Action.GENERATE_DEFAULT:
        # TODO(rechen): generating default pyis here breaks the separation
        # between staging and execution. We should either generate these files
        # during the ninja build or map them all to one canonical file.
        module_to_output[module] = self.generate_default_pyi(module)
        continue
      if stage == Stage.SINGLE_PASS:
        files.add(module.full_path)
        output_dir = additional_pythonpath_dir = None
      elif stage == Stage.FIRST_PASS:
        output_dir = self.pyi_1_dir
        additional_pythonpath_dir = None
      else:
        assert stage == Stage.SECOND_PASS
        files.add(module.full_path)
        output_dir = None
        additional_pythonpath_dir = self.pyi_1_dir
      module_to_output[module] = self.write_build_statement(
          module, action, tuple(module_to_output[m] for m in deps), output_dir,
          additional_pythonpath_dir)
    return files

  def build(self):
    """Execute the build.ninja file."""
    # -k N     keep going until N jobs fail (0 means infinity)
    # -C DIR   change to DIR before doing anything else
    # TODO(rechen): The user should be able to customize -k.
    return subprocess.call(
        ['ninja', '-k', '0', '-C', os.path.dirname(self.ninja_file)])

  def run(self):
    """Run pytype over the project."""
    logging.info('------------- Starting pytype run. -------------')
    files_to_analyze = self.setup_build()
    num_sources = len(self.filenames & files_to_analyze)
    print('Analyzing %d sources with %d dependencies' %
          (num_sources, len(files_to_analyze) - num_sources))
    return self.build()
