#!/usr/bin/python2.7
"""Tool for inferring types from Python programs.

'pytype' is a tool for generating pyi from Python programs.

Usage:
  pytype [flags] file.py
"""

from __future__ import print_function

import cProfile
import logging
import signal
import sys

from pytype import config
from pytype import io
from pytype import load_pytd
from pytype import metrics
from pytype import utils
from pytype.pytd import typeshed
from pytype.pytd.parse import node


log = logging.getLogger(__name__)


class _ProfileContext(object):
  """A context manager for optionally profiling code."""

  def __init__(self, output_path):
    """Initialize.

    Args:
      output_path: A pathname for the profiler output.  An empty string
          indicates that no profiling should be done.
    """
    self._output_path = output_path
    self._profile = cProfile.Profile() if self._output_path else None

  def __enter__(self):
    if self._profile:
      self._profile.enable()

  def __exit__(self, exc_type, exc_value, traceback):  # pylint: disable=redefined-outer-name
    if self._profile:
      self._profile.disable()
      self._profile.dump_stats(self._output_path)


def _generate_builtins_pickle(options):
  """Create a pickled file with the standard library (typeshed + builtins)."""
  loader = load_pytd.create_loader(options)
  t = typeshed.Typeshed()
  module_names = t.get_all_module_names(options.python_version)
  blacklist = set(t.blacklisted_modules(options.python_version))
  for m in sorted(module_names):
    if m not in blacklist:
      loader.import_name(m)
  loader.save_to_pickle(options.generate_builtins)


def main():
  try:
    options = config.Options(sys.argv[1:])
  except utils.UsageError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)

  if options.show_config:
    print(options)
    sys.exit(0)

  if options.version:
    print(io.get_pytype_version())
    sys.exit(0)

  node.SetCheckPreconditions(options.check_preconditions)

  if options.timeout is not None:
    signal.alarm(options.timeout)

  with _ProfileContext(options.profile):
    with metrics.MetricsContext(options.metrics):
      with metrics.StopWatch("total_time"):
        with metrics.Snapshot("memory", enabled=options.memory_snapshots):
          return _run_pytype(options)


def _run_pytype(options):
  """Run pytype with the given configuration options."""
  if options.generate_builtins:
    return _generate_builtins_pickle(options)
  elif options.parse_pyi:
    unused_ast = io.parse_pyi(options)
    return 0
  else:
    return io.process_one_file(options)


if __name__ == "__main__":
  sys.exit(main() or 0)
