"""Utility functions."""

from __future__ import print_function

import logging
import shutil
import sys

from pytype import file_utils


def setup_logging_or_die(verbosity):
  """Set the logging level or die."""
  if verbosity == 0:
    level = logging.ERROR
  elif verbosity == 1:
    level = logging.WARNING
  elif verbosity == 2:
    level = logging.INFO
  else:
    logging.critical('Bad verbosity level: %s', verbosity)
    sys.exit(1)
  logging.basicConfig(level=level, format='%(levelname)s %(message)s')


def _manipulate_path_or_die(manipulate, path, message):
  try:
    manipulate(path)
  except OSError:
    logging.critical('%s: %s', message, path)
    sys.exit(1)


def rmdir_or_die(path, message):
  _manipulate_path_or_die(shutil.rmtree, path, message)


def makedirs_or_die(path, message):
  _manipulate_path_or_die(file_utils.makedirs, path, message)
