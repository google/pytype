"""Initializes and checks the environment needed to run pytype."""

from __future__ import print_function

import os
import sys

from . import runner


def check_pytype_or_die():
  if not runner.can_run("pytype", "-h"):
    print("Cannot run pytype. Check that it is installed and in your path")
    sys.exit(1)


def check_python_version(exe, required):
  """Check if exe is a python executable with the required version."""
  try:
    # python --version outputs to stderr for earlier versions
    _, out, err = runner.BinaryRun([exe, "--version"]).communicate()  # pylint: disable=unpacking-non-sequence
    version = out or err
    version = version.decode("utf-8")
    if version.startswith("Python %s" % required):
      return True, None
    else:
      return False, version.rstrip()
  except OSError:
    return False, "Could not run"


def check_python_exe_or_die(required):
  """Check if a python executable with the required version is in path."""
  error = []
  for exe in ["python", "python%s" % required]:
    valid, out = check_python_version(exe, required)
    if valid:
      return exe
    else:
      error += ["%s: %s" % (exe, out)]
  print("Could not find a valid python%s interpreter in path:" % required)
  print("--------------------------------------------------------")
  print("\n".join(error))
  sys.exit(1)


def initialize_typeshed_or_die(opts):
  """Initialize a Typeshed object or die.

  Args:
    opts: an optparse.Values object

  Returns:
    An instance of Typeshed()

  See Typeshed.find_location() for details.
  """
  ret = Typeshed.find_location(opts)
  if not ret:
    opt = getattr(opts, Typeshed.OPTIONS_KEY, None)
    env = os.environ.get(Typeshed.ENVIRONMENT_VARIABLE)
    print("Cannot find a valid typeshed installation.")
    print("Searched in:")
    print("  %s argument: %s" % (Typeshed.OPTIONS_KEY, opt))
    print("  %s environment variable: %s" %
          (Typeshed.ENVIRONMENT_VARIABLE, env))
    sys.exit(1)
  return ret


class Typeshed(object):
  """Query a typeshed installation."""

  # Where the typeshed location is specified. The command line option overrides
  # the environment variable.
  #
  # Tools should ideally standardise on pointing to typeshed via
  #   - A --typeshed_location argument
  #   - The $TYPESHED_HOME environment variable
  # but if not you can subclass and override these variables.
  OPTIONS_KEY = "typeshed_location"
  ENVIRONMENT_VARIABLE = "TYPESHED_HOME"

  def __init__(self, root):
    self.root = root

  @classmethod
  def find_location(cls, opts):
    """Find a typeshed installation if present.

    Args:
      opts: an optparse.Values object

    Returns:
      A path to a valid typeshed installation, or None.
    """
    opt = getattr(opts, cls.OPTIONS_KEY)
    env = os.environ.get(cls.ENVIRONMENT_VARIABLE, None)
    ret = opt or env or ""
    if not os.path.isdir(os.path.join(ret, "stdlib")):
      return None
    return ret

  @classmethod
  def create_from_opts(cls, opts):
    root = cls.find_location(opts)
    if root:
      return cls(root)
    return None

  def get_paths(self, python_version):
    """Get the names of all modules in typeshed and pytype/pytd/builtins.

    Args:
      python_version: A tuple of (major, minor)

    Returns:
      A list of paths to typeshed subdirectories.
    """
    major, minor = python_version
    subdirs = [
        "stdlib/%d" % major,
        "stdlib/2and3",
    ]
    if major == 3:
      for i in range(0, minor + 1):
        # iterate over 3.0, 3.1, 3.2, ...
        subdirs.append("stdlib/3.%d" % i)
    return [os.path.join(self.root, d) for d in subdirs]
