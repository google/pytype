"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import os

import importlab.output

from pytype.tools import runner
from pytype.tools import utils


class PytypeRunner(object):
  """Runs pytype over an import graph."""

  def __init__(self, import_graph, conf, typeshed, quiet):
    self.import_graph = import_graph
    self.output_dir = conf.output_dir
    self.deps = conf.deps
    self.projects = conf.projects
    self.pythonpath = conf.pythonpath
    self.python_version = conf.python_version
    self.system_env = {
        b'TYPESHED_HOME': typeshed.root.encode('utf-8')
    }
    self.pyi_dir = os.path.join(self.output_dir, 'pyi')
    utils.makedirs_or_die(self.output_dir,
                          'Could not create output directory')
    self.log_file = os.path.join(self.output_dir, 'pytype.log')
    self.logger = utils.setup_logging('pytype', self.log_file)
    self.quiet = quiet

  def infer_module_name(self, filename):
    """Convert a filename to a module name relative to pythonpath."""
    # We want '' in our lookup path, but we don't want it for prefix tests.
    for path in filter(bool, self.pythonpath):
      path = os.path.abspath(path)
      if not path.endswith(os.sep):
        path += os.sep
      if filename.startswith(path):
        filename = filename[len(path):]
        return (path, filename, utils.filename_to_module_name(filename))
    # We have not found filename relative to anywhere in pythonpath.
    return '', filename, utils.filename_to_module_name(filename)

  def run_pytype(self, filename, report_errors=True):
    """Run pytype over a single file."""
    path, target, module_name = self.infer_module_name(filename)
    out = target + 'i'
    err = target + '.errors'
    outfile = os.path.join(self.pyi_dir, out)
    errfile = os.path.join(self.pyi_dir, err)
    target_dir = os.path.join(self.pyi_dir, os.path.dirname(target))

    in_projects = any(path.startswith(d) for d in self.projects)
    in_deps = any(path.startswith(d) for d in self.deps)

    # Do not try to analyse files importlab has resolved via the system path.
    # Also, if importlab has returned a non-.py dependency, ignore it.
    if (not in_projects and not in_deps) or not target.endswith('.py'):
      print('  skipping file:', target)
      return

    # Report errors for files in projects (those we are analysing directly)
    if in_deps and not in_projects:
      report_errors = False
    if not report_errors:
      print('  %s*' % out)
    else:
      print('  %s' % out)

    # Create the output subdirectory for this file.
    try:
      utils.makedirs(target_dir)
    except OSError:
      self.logger.error('Could not create directory for output file: %s' % out)
      return

    run_cmd = [
        'pytype',
        '-P', self.pyi_dir,
        '-V', self.python_version,
        '-o', outfile,
        '--quick',
        '--module-name', module_name
    ]
    if not report_errors:
      run_cmd += ['--no-report-errors']
    run_cmd += [filename]
    self.logger.info('Running: ' + ' '.join(run_cmd))
    run = runner.BinaryRun(run_cmd, env=self.system_env)
    try:
      returncode, _, stderr = run.communicate()
    except OSError:
      self.logger.error('Could not run pytype.')
      return
    if returncode:
      print('    errors written to:', errfile)
      error = stderr.decode('utf-8')
      with open(errfile, 'w') as f:
        f.write(error)
      if not self.quiet:
        print(error)
      # Log as WARNING since this is a pytype error, not our error.
      self.logger.warning(error)

  def run(self):
    """Run pytype over the project."""
    deps = list(self.import_graph.sorted_source_files())
    print('Writing logs to:', self.log_file)
    print()
    print('Generating %d targets' % sum(len(x) for x in deps))
    self.logger.info('------------- Starting pytype run. -------------')
    self.logger.info('source tree:\n' +
                     importlab.output.formatted_deps_list(self.import_graph))
    for files in deps:
      if len(files) == 1:
        self.run_pytype(files[0])
      else:
        # If we have a cycle we run pytype over the files twice, ignoring errors
        # the first time so that we don't fail on missing dependencies.
        for f in files:
          self.run_pytype(f, report_errors=False)
        for f in files:
          self.run_pytype(f, report_errors=True)
