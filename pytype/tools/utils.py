"""Utility functions."""

from contextlib import contextmanager
import logging
import os


def filename_to_module_name(filename):
  if os.path.dirname(filename).startswith(os.pardir):
    # Don't try to infer a module name for filenames starting with ../
    return None
  return filename.replace(os.sep, '.')


def setup_logging(name, log_file, level=logging.INFO):
  formatter = logging.Formatter(
      fmt='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
  handler = logging.FileHandler(log_file)
  handler.setFormatter(formatter)
  logger = logging.getLogger(name)
  logger.setLevel(level)
  logger.addHandler(handler)
  return logger


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
