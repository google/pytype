"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import collections
import logging
import os

from pytype import config as pytype_config
from pytype import file_utils
from pytype import io
from pytype import utils


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
    # TODO(mdemello): Deduplicate this one and the one in load_pytd.py
    # We want '' in our lookup path, but we don't want it for prefix tests.
    for path in filter(bool, self.pythonpath):
      if not path.endswith(os.sep):
        path += os.sep
      if filename.startswith(path):
        filename = filename[len(path):]
        return Module(path, filename,
                      utils.path_to_module_name(filename, preserve_init=True))
        # We have not found filename relative to anywhere in pythonpath.
    return Module('', filename,
                  utils.path_to_module_name(filename, preserve_init=True))

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
        '--nofail',
        os.path.join(module.path, module.target),
    ]

  def run_pytype(self, module, report_errors):
    """Run pytype over a single module."""
    # Create the output subdirectory for this file.
    target_dir = os.path.join(self.pyi_dir, os.path.dirname(module.target))
    try:
      file_utils.makedirs(target_dir)
    except OSError:
      logging.error('Could not create output directory: %s', target_dir)
      return

    if report_errors:
      print('%s' % module.target)
    else:
      print('%s*' % module.target)

    run_cmd = self.get_run_cmd(module, report_errors)
    logging.info('Running: %s', ' '.join(run_cmd))
    # TODO(rechen): Do we want to get rid of the --nofail option and use a
    # try/except here instead? We'd control the failure behavior (e.g. we could
    # potentially bring back the .errors file, or implement an "abort on first
    # error" flag for quick iterative typechecking).
    io.process_one_file(pytype_config.Options(run_cmd))

  def yield_sorted_modules(self):
    """Yield modules from our sorted source files."""
    for files in self.sorted_source_files:
      modules = []
      for f in files:
        # Report errors for files we are analysing directly.
        report_errors = f in self.filenames
        # We'll use this function to report skipped files.
        report = logging.warning if report_errors else logging.info
        if not f.endswith('.py'):
          report('Skipping non-Python file: %s', f)
          continue
        module = self.infer_module_name(f)
        if not any(module.path.startswith(d) for d in self.pythonpath):
          report('Skipping file not in pythonpath: %s', f)
          continue
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
    logging.info('------------- Starting pytype run. -------------')
    modules = list(self.yield_sorted_modules())
    files_to_analyze = {os.path.join(m.path, m.target) for m, _ in modules}
    num_sources = len(self.filenames & files_to_analyze)
    print('Analyzing %d sources with %d dependencies' %
          (num_sources, len(files_to_analyze) - num_sources))
    for module, report_errors in modules:
      self.run_pytype(module, report_errors)
