"""File and path utilities."""

import contextlib
import errno
import os
import shutil
import tempfile
import textwrap

from pytype import compat


def replace_extension(filename, new_extension):
  name, _ = os.path.splitext(filename)
  if new_extension.startswith("."):
    return name + new_extension
  else:
    return name + "." + new_extension


def get_versioned_path(subdir, python_version):
  major_version = python_version[0]
  assert(major_version == 2 or major_version == 3)
  return os.path.join(subdir, str(major_version))


def makedirs(path):
  """Create a nested directory, but don't fail if any of it already exists."""
  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno != errno.EEXIST:
      raise


class Tempdir:
  """Context handler for creating temporary directories."""

  def __enter__(self):
    self.path = tempfile.mkdtemp()
    return self

  def create_directory(self, filename):
    """Create a subdirectory in the temporary directory."""
    path = os.path.join(self.path, filename)
    makedirs(path)
    return path

  def create_file(self, filename, indented_data=None):
    """Create a file in the temporary directory. Dedents the data if needed."""
    filedir, filename = os.path.split(filename)
    if filedir:
      self.create_directory(filedir)
    path = os.path.join(self.path, filedir, filename)
    if isinstance(indented_data, bytes) and not isinstance(indented_data, str):
      # This is binary data rather than text.
      # TODO(rechen): The second isinstance() check can be dropped once we no
      # longer support running under Python 2.
      mode = "wb"
      data = indented_data
    else:
      mode = "w"
      data = textwrap.dedent(indented_data) if indented_data else indented_data
    with open(path, mode) as fi:
      if data:
        fi.write(data)
    return path

  def delete_file(self, filename):
    os.unlink(os.path.join(self.path, filename))

  def __exit__(self, error_type, value, tb):
    shutil.rmtree(path=self.path)
    return False  # reraise any exceptions

  def __getitem__(self, filename):
    """Get the full path for an entry in this directory."""
    return os.path.join(self.path, filename)


@contextlib.contextmanager
def cd(path):
  """Context manager. Change the directory, and restore it afterwards.

  Example usage:
    with cd("/path"):
      ...

  Arguments:
    path: The directory to change to. If empty, this function is a no-op.
  Yields:
    Executes your code, in a changed directory.
  """
  if not path:
    yield
    return
  curdir = os.getcwd()
  os.chdir(path)
  try:
    yield
  finally:
    os.chdir(curdir)


def is_pyi_directory_init(filename):
  """Checks if a pyi file is path/to/dir/__init__.pyi."""
  if filename is None:
    return False
  return os.path.splitext(os.path.basename(filename))[0] == "__init__"


def expand_path(path, cwd=None):
  """Fully expand a path, optionally with an explicit cwd."""

  expand = lambda path: os.path.realpath(os.path.expanduser(path))
  with cd(cwd):
    return expand(path)


def expand_paths(paths, cwd=None):
  """Fully expand a list of paths, optionally with an explicit cwd."""
  return [expand_path(x, cwd) for x in paths]


def expand_globpaths(globpaths, cwd=None):
  """Expand a list of glob expressions into a list of full paths."""
  with cd(cwd):
    paths = sum((compat.recursive_glob(p) for p in globpaths), [])
  return expand_paths(paths, cwd)


def expand_source_files(filenames, cwd=None):
  """Expand a space-separated string of filenames passed in as sources.

  This is a helper function for handling command line arguments that specify a
  list of source files and directories.

  Any directories in filenames will be scanned recursively for .py files.
  Any files that do not end with ".py" will be dropped.

  Args:
    filenames: A space-separated string of filenames to process.
    cwd: An optional working directory to expand relative paths
  Returns:
    A set of full paths to .py files
  """
  out = []
  for f in expand_globpaths(filenames.split(), cwd):
    if os.path.isdir(f):
      # If we have a directory, collect all the .py files within it.
      out += compat.recursive_glob(os.path.join(f, "**", "*.py"))
    elif f.endswith(".py"):
      out.append(f)
  return set(out)


def expand_pythonpath(pythonpath, cwd=None):
  """Expand a/b:c/d into [/path/to/a/b, /path/to/c/d]."""
  if pythonpath:
    return expand_paths(
        (path.strip() for path in pythonpath.split(os.pathsep)), cwd)
  else:
    return []
