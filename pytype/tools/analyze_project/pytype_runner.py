"""Use pytype to analyze and infer types for an entire project."""

from __future__ import print_function

import os
import sys

from pytype.tools import runner
from pytype.tools import utils


class PytypeRunner(object):
  """Runs pytype over an import graph."""

  def __init__(self, import_graph, importlab_env):
    self.import_graph = import_graph
    self.env = importlab_env
    cfg = self.env.config
    self.pythonpath = self.env.pythonpath.split(':')
    self.output_dir = cfg.output_dir
    self.deps = cfg.deps
    self.projects = cfg.projects
    self.system_env = {b'TYPESHED_HOME': self.env.typeshed.root.encode('utf-8')}
    self.pyi_dir = os.path.join(self.output_dir, 'pyi')
    if not os.path.exists(self.output_dir):
      try:
        os.makedirs(self.output_dir)
      except OSError:
        print('Could not create output directory:', self.output_dir)
        sys.exit(1)
    self.log_file = os.path.join(self.output_dir, 'pytype.log')
    self.logger = utils.setup_logging('pytype', self.log_file)

  def infer_module_name(self, filename):
    """Convert a filename to a module name relative to pythonpath."""
    filename, _ = os.path.splitext(filename)
    # We want '' in our lookup path, but we don't want it for prefix tests.
    for path in filter(bool, self.pythonpath):
      path = os.path.abspath(path)
      if not path.endswith(os.sep):
        path += os.sep
      if filename.startswith(path):
        filename = filename[len(path):]
        return (path, utils.filename_to_module_name(filename))
    # We have not found filename relative to anywhere in pythonpath.
    return '', utils.filename_to_module_name(filename)

  def run_pytype(self, filename, report_errors=True):
    """Run pytype over a single file."""
    path, module_name = self.infer_module_name(filename)
    target = os.path.relpath(filename, path)
    out = os.path.join(self.pyi_dir, target + 'i')
    err = os.path.join(self.pyi_dir, target + '.errors')
    in_projects = any(path.startswith(d) for d in self.projects)
    in_deps = any(path.startswith(d) for d in self.deps)
    if in_deps and not in_projects:
      report_errors = False
    if not report_errors:
      print('  %s*' % out)
    else:
      print('  %s' % out)
    try:
      os.makedirs(self.pyi_dir)
    except OSError:
      self.logger.error('Could not create directory for output file: %s' % out)
      return
    run_cmd = [
        'pytype',
        '-P', self.pyi_dir,
        '-V', self.env.python_version_string,
        '-o', out,
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
      print('    errors written to:', err)
      error = stderr.decode('utf-8')
      with open(err, 'w') as f:
        f.write(error)
      if not self.env.args.quiet:
        print(error)
      # Log as WARNING since this is a pytype error, not our error.
      self.logger.warning(error)

  def run(self):
    deps = list(self.import_graph.sorted_source_files())
    print('Writing logs to:', self.log_file)
    print()
    print('Generating %d targets' % sum(len(x) for x in deps))
    self.logger.info('------------- Starting pytype run. -------------')
    self.logger.info('source tree:\n' + self.import_graph.formatted_deps_list())
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
