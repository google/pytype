"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import logging
import os
import sys

from pytype import config as pytype_config
from pytype import debug
from pytype import file_utils
from pytype import io
from pytype import module_utils
from pytype.tools.analyze_project import config


# Generate a default pyi for dependencies not in the pythonpath.
DEFAULT_PYI = """
from typing import Any
def __getattr__(name) -> Any: ...
"""


class Action(object):
  REPORT_ERRORS = 1
  IGNORE_ERRORS = 2
  GENERATE_DEFAULT = 3


def deps_from_import_graph(import_graph):
  """Construct PytypeRunner args from an importlab.ImportGraph instance.

  Kept as a separate function so PytypeRunner can be tested independently of
  importlab.

  Args:
    import_graph: An importlab.ImportGraph instance.

  Returns:
    A list of lists of source modules in dependency order.
  """
  def make_module(mod):
    full_path = mod.path
    target = mod.short_path
    path = full_path[:-len(target)]
    name = mod.module_name
    # We want to preserve __init__ in the module_name for pytype.
    if os.path.basename(full_path) == '__init__.py':
      name += '.__init__'
    return module_utils.Module(
        path=path, target=target, name=name, kind=mod.__class__.__name__)
  return [[make_module(import_graph.provenance[f]) for f in files]
          for files in import_graph.sorted_source_files()]


def _print_transient(msg):
  """Prints an overwritable terminal message.

  Prints a message that will be overwritten by the next one. Be warned that if
  the next message is shorter, then part of this message will still be visible
  on the right.

  Args:
    msg: A msg
  """
  if sys.stdout.isatty():
    print(msg + '\r', end='')


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
    self.sorted_sources = sorted_sources  # all source modules
    self.pythonpath = conf.pythonpath
    self.python_version = conf.python_version
    self.pyi_dir = conf.output
    self.custom_options = {
        k: getattr(conf, k) for k in set(conf.__slots__) - set(config.ITEMS)}

  def get_pytype_args(self, module, report_errors):
    """Get the options for running pytype on the given module."""
    return [
        '-P', self.pyi_dir,
        '-V', self.python_version,
        '-o', self._output_file(module),
        '--quick',
        '--module-name', module.name,
        '--analyze-annotated' if report_errors else '--no-report-errors',
        '--nofail',
        module.full_path,
    ]

  def _output_file(self, module):
    filename = _module_to_output_path(module) + '.pyi'
    return os.path.join(self.pyi_dir, filename)

  def create_output_dir(self, module):
    # Create the output subdirectory for this file.
    target_dir = os.path.dirname(self._output_file(module))
    try:
      file_utils.makedirs(target_dir)
    except OSError:
      logging.error('Could not create output directory: %s', target_dir)
      return
    return target_dir

  def write_default_pyi(self, module):
    """Write a default pyi file for the module."""
    self.create_output_dir(module)
    output = self._output_file(module)
    logging.info('Generating default pyi: %s', output)
    with open(output, 'w') as f:
      f.write(DEFAULT_PYI)

  def run_pytype(self, module, report_errors):
    """Run pytype over a single module."""
    self.create_output_dir(module)
    args = self.get_pytype_args(module, report_errors)
    logging.info('Running: pytype %s %s', ' '.join(args), self.custom_options)
    # TODO(rechen): Do we want to get rid of the --nofail option and use a
    # try/except here instead? We'd control the failure behavior (e.g. we could
    # potentially bring back the .errors file, or implement an "abort on first
    # error" flag for quick iterative typechecking).
    with debug.save_logging_level():  # pytype_config changes the logging level
      options = pytype_config.Options(args)
      # TODO(rechen): Do this tweaking in get_pytype_args so it can be tested.
      if report_errors:
        options.tweak(**self.custom_options)
      return io.process_one_file(options)

  def process_module(self, module, action):
    """Process a single module with the given action."""
    ret = None
    if action == Action.REPORT_ERRORS:
      msg = '%s' % module.target
      _print_transient(msg)
      ret = self.run_pytype(module, True)
    elif action == Action.IGNORE_ERRORS:
      msg = '%s*' % module.target
      _print_transient(msg)
      ret = self.run_pytype(module, False)
    elif action == Action.GENERATE_DEFAULT:
      msg = '%s#' % module.target
      _print_transient(msg)
      self.write_default_pyi(module)
      ret = 0
    else:
      logging.fatal('Unexpected action %r', action)
      return 1
    # Clears the message by overwriting it with whitespace.
    _print_transient(' ' * len(msg))
    return ret

  def yield_sorted_modules(self):
    """Yield modules from our sorted source files."""
    for group in self.sorted_sources:
      modules = []
      for module in group:
        f = module.full_path
        # Report errors for files we are analysing directly.
        if f in self.filenames:
          action = Action.REPORT_ERRORS
          report = logging.warning
        else:
          action = Action.IGNORE_ERRORS
          report = logging.info
        if not f.endswith('.py'):
          report('Skipping non-Python file: %s', f)
          continue
        # For builtin and system files, do not attempt to generate a pyi.
        if module.kind in ('Builtin', 'System'):
          report('Generating default pyi for %s file: %s', module.kind, f)
          action = Action.GENERATE_DEFAULT
        modules.append((module, action))
      if len(modules) == 1:
        yield modules[0]
      else:
        # If we have a cycle we run pytype over the files twice, ignoring errors
        # the first time so that we don't fail on missing dependencies.
        for module, action in modules:
          if action == Action.REPORT_ERRORS:
            action = Action.IGNORE_ERRORS
          yield module, action
        for module, action in modules:
          # We don't need to run generate_default twice
          if action != Action.GENERATE_DEFAULT:
            yield module, action

  def run(self):
    """Run pytype over the project."""
    logging.info('------------- Starting pytype run. -------------')
    modules = list(self.yield_sorted_modules())
    files_to_analyze = {m.full_path for m, _ in modules}
    num_sources = len(self.filenames & files_to_analyze)
    print('Analyzing %d sources with %d dependencies' %
          (num_sources, len(files_to_analyze) - num_sources))
    # set ret = 1 if any invocation of process_module returns an error.
    ret = 0
    for module, action in modules:
      status = self.process_module(module, action)
      ret = ret or status
    return ret
