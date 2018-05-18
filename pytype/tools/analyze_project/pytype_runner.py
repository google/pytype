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

  def __init__(self, sorted_source_files, conf):
    self.sorted_source_files = sorted_source_files
    self.output_dir = conf.output_dir
    self.deps = conf.deps
    self.projects = conf.projects
    self.pythonpath = conf.pythonpath
    self.python_version = conf.python_version
    self.pyi_dir = os.path.join(self.output_dir, 'pyi')

  def infer_module_name(self, filename):
    """Convert a filename to a module name relative to pythonpath."""
    # We want '' in our lookup path, but we don't want it for prefix tests.
    for path in filter(bool, self.pythonpath):
      path = os.path.abspath(path)
      if not path.endswith(os.sep):
        path += os.sep
      if filename.startswith(path):
        filename = filename[len(path):]
        return Module(path, filename, utils.filename_to_module_name(filename))
    # We have not found filename relative to anywhere in pythonpath.
    return Module('', filename, utils.filename_to_module_name(filename))

  def get_cmd_options(self, module, report_errors):
    """Get the command-line options for running pytype on the given module."""
    outfile = os.path.join(self.pyi_dir, module.target + 'i')
    options = [
        '-P', self.pyi_dir,
        '-V', self.python_version,
        '-o', outfile,
        '--quick',
        '--module-name', module.name
    ]
    if not report_errors:
      options.append('--no-report-errors')
    return options

  def run_pytype(self, filename, report_errors=True):
    """Run pytype over a single file."""
    module = self.infer_module_name(filename)
    in_projects = any(module.path.startswith(d) for d in self.projects)
    in_deps = any(module.path.startswith(d) for d in self.deps)

    # Do not try to analyse files importlab has resolved via the system path.
    # Also, if importlab has returned a non-.py dependency, ignore it.
    if (not in_projects and not in_deps) or not module.target.endswith('.py'):
      print('  skipping file:', module.target)
      return

    # Create the output subdirectory for this file.
    target_dir = os.path.join(self.pyi_dir, os.path.dirname(module.target))
    try:
      utils.makedirs(target_dir)
    except OSError:
      logging.error('Could not create output directory: %s', target_dir)
      return

    # Report errors for files in projects (those we are analysing directly)
    report_errors = in_projects and report_errors
    if report_errors:
      print('  %s' % module.target)
    else:
      print('  %s*' % module.target)

    cmd_options = self.get_cmd_options(module, report_errors)
    run_cmd = ['pytype'] + cmd_options + [filename]
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

  def run(self):
    """Run pytype over the project."""
    print(
        'Generating %d targets' % sum(len(x) for x in self.sorted_source_files))
    logging.info('------------- Starting pytype run. -------------')
    for files in self.sorted_source_files:
      if len(files) == 1:
        self.run_pytype(files[0])
      else:
        # If we have a cycle we run pytype over the files twice, ignoring errors
        # the first time so that we don't fail on missing dependencies.
        for f in files:
          self.run_pytype(f, report_errors=False)
        for f in files:
          self.run_pytype(f, report_errors=True)
