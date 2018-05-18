"""Utility functions."""

from __future__ import print_function

from contextlib import contextmanager
import logging
import os
import sys


def filename_to_module_name(filename):
  if os.path.dirname(filename).startswith(os.pardir):
    # Don't try to infer a module name for filenames starting with ../
    return None
  filename, _ = os.path.splitext(filename)
  return filename.replace(os.sep, '.')


def setup_logging(level):
  logging.basicConfig(level=level,
                      format='%(asctime)s %(levelname)s %(message)s')


@contextmanager
def cd(path):
  old = os.getcwd()
  os.chdir(os.path.expanduser(path))
  try:
    yield
  finally:
    os.chdir(old)


def expand_path(path, cwd=None):
  expand = lambda path: os.path.realpath(os.path.expanduser(path))
  if cwd:
    with cd(cwd):
      return expand(path)
  else:
    return expand(path)


def expand_paths(paths, cwd=None):
  return [expand_path(x, cwd) for x in paths]


def split_version(version):
  return tuple(int(v) for v in version.split('.'))


def makedirs(path):
  if os.path.exists(path):
    return
  os.makedirs(path)


def makedirs_or_die(path, message):
  try:
    makedirs(path)
  except OSError:
    print(message + ': ' + path)
    sys.exit(1)
