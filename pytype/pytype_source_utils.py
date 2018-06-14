"""Utilities for working with pytype source files."""

# All functions with a dependence on __file__ should go here.
# This file should be kept under pytype/ so that __file__.dirname is the
# top-level pytype directory.

import atexit
import os
import tempfile


class NoSuchDirectory(Exception):
  pass


def pytype_source_dir():
  """The base directory of the pytype source tree."""
  return os.path.dirname(__file__)


def get_full_path(path):
  """Full path to a file or directory within the pytype source tree.

  Arguments:
    path: An absolute or relative path.

  Returns:
    path for absolute paths.
    full path resolved relative to pytype/ for relative paths.
  """
  # TODO(mdemello): Insist on relative paths here.
  return os.path.join(pytype_source_dir(), path)


def load_pytype_file(filename):
  """Get the contents of a data file from the pytype installation.

  Arguments:
    filename: the path, relative to "pytype/"
  Returns:
    The contents of the file as a bytestring
  Raises:
    IOError: if file not found
  """
  path = get_full_path(filename)
  # Check for a ResourceLoader (see comment under list_pytype_files).
  loader = globals().get("__loader__", None)
  if loader:
    # For an explanation of the args to loader.get_data, see
    # https://www.python.org/dev/peps/pep-0302/#optional-extensions-to-the-importer-protocol
    # https://docs.python.org/3/library/importlib.html#importlib.abc.ResourceLoader.get_data
    return loader.get_data(path)
  with open(path, "rb") as fi:
    return fi.read()


def list_pytype_files(suffix):
  """Recursively get the contents of a directory in the pytype installation.

  This reports files in said directory as well as all subdirectories of it.

  Arguments:
    suffix: the path, relative to "pytype/"
  Yields:
    The filenames, relative to pytype/{suffix}
  Raises:
    NoSuchDirectory: if the directory doesn't exist.
  """
  assert not suffix.endswith("/")
  loader = globals().get("__loader__", None)
  try:
    # List directory using __loader__.
    # __loader__ exists only when this file is in a Python archive in Python 2
    # but is always present in Python 3, so we can't use the presence or
    # absence of the loader to determine whether calling get_zipfile is okay.
    filenames = loader.get_zipfile().namelist()  # pytype: disable=attribute-error
  except AttributeError:
    basedir = get_full_path(suffix)
    # List directory using the file system
    if not os.path.isdir(basedir):
      raise NoSuchDirectory(basedir)
    directories = [""]
    while directories:
      d = directories.pop()
      for basename in os.listdir(os.path.join(basedir, d)):
        filename = os.path.join(d, basename)
        if os.path.isdir(os.path.join(basedir, filename)):
          directories.append(filename)
        elif os.path.exists(os.path.join(basedir, filename)):
          yield filename
  else:
    for filename in filenames:
      directory = "pytype/" + suffix + "/"
      try:
        i = filename.rindex(directory)
      except ValueError:
        pass
      else:
        yield filename[i + len(directory):]


