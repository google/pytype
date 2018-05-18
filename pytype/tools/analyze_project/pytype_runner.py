"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import collections
import logging
import os

from pytype.tools import runner
from pytype.tools import utils


# Inferred information about a module.
# Args:
#   path: The path to the module, e.g., foo/.
#   target: The filename relative to the path, e.g., bar/baz.py.
#   name: The module name, e.g., bar.baz.
Module = collections.namedtuple('_', 'path target name')


class PytypeRunner(object):
  """Runs pytype over an import graph."""

  def __init__(self, filenames, sorted_source_files, conf):
    self.filenames = set(filenames)  # files to type-check
    self.sorted_source_files = sorted_source_files  # all source files
    self.pythonpath = conf.pythonpath
    self.python_version = conf.python_version
    self.pyi_dir = conf.output_dir

  def infer_module_name(self, filename):
    """Convert a filename to a module name relative to pythonpath."""
    # We want '' in our lookup path, but we don't want it for prefix tests.
    for path in filter(bool, self.pythonpath):
      if not path.endswith(os.sep):
        path += os.sep
      if filename.startswith(path):
        filename = filename[len(path):]
        return Module(path, filename, utils.filename_to_module_name(filename))
    # We have not found filename relative to anywhere in pythonpath.
    return Module('', filename, utils.filename_to_module_name(filename))

  def get_run_cmd(self, module, report_errors):
    """Get the command for running pytype on the given module."""
    return [
        'pytype',
        '-P', self.pyi_dir,
        '-V', self.python_version,
        '-o', os.path.join(self.pyi_dir, module.target + 'i'),
        '--quick',
        '--module-name', module.name,
        '--analyze-annotated' if report_errors else '--no-report-errors',
        os.path.join(module.path, module.target),
    ]

  def run_pytype(self, module, report_errors):
    """Run pytype over a single module."""
    # Create the output subdirectory for this file.
    target_dir = os.path.join(self.pyi_dir, os.path.dirname(module.target))
    try:
      utils.makedirs(target_dir)
    except OSError:
      logging.error('Could not create output directory: %s', target_dir)
      return

    if report_errors:
      print('  %s' % module.target)
    else:
      print('  %s*' % module.target)

    run_cmd = self.get_run_cmd(module, report_errors)
    logging.info('Running: %s', ' '.join(run_cmd))
    run = runner.BinaryRun(run_cmd)
    try:
      returncode, _, stderr = run.communicate()
    except OSError:
      logging.error('Could not run pytype.')
      return
    if returncode:
      errfile = os.path.join(self.pyi_dir, module.target + '.errors')
      print('    errors written to:', errfile)
      error = stderr.decode('utf-8')
      with open(errfile, 'w') as f:
        f.write(error)
      # Log as WARNING since this is a pytype error, not our error.
      logging.warning(error)

  def yield_sorted_modules(self):
    """Yield modules from our sorted source files."""
    for files in self.sorted_source_files:
      modules = []
      for f in files:
        if not f.endswith('.py'):
          logging.info('Skipping non-Python file: %s', f)
          continue
        module = self.infer_module_name(f)
        if not any(module.path.startswith(d) for d in self.pythonpath):
          logging.info('Skipping file not in pythonpath: %s', f)
          continue
        # Report errors for files we are analysing directly.
        report_errors = f in self.filenames
        modules.append((module, report_errors))
      if len(modules) == 1:
        yield modules[0]
      else:
        # If we have a cycle we run pytype over the files twice, ignoring errors
        # the first time so that we don't fail on missing dependencies.
        for module, _ in modules:
          yield module, False
        for module_and_report_errors in modules:
          yield module_and_report_errors

  def run(self):
    """Run pytype over the project."""
    print(
        'Generating %d targets' % sum(len(x) for x in self.sorted_source_files))
    logging.info('------------- Starting pytype run. -------------')
    for module, report_errors in self.yield_sorted_modules():
      self.run_pytype(module, report_errors)
