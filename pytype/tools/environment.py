"""Initializes and checks the environment needed to run pytype."""

from __future__ import print_function

import sys

from . import runner
from pytype.pytd import typeshed


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


def initialize_typeshed_or_die():
  """Initialize a Typeshed object or die.

  Returns:
    An instance of Typeshed()
  """
  try:
    return typeshed.Typeshed()
  except IOError as e:
    print(str(e))
    sys.exit(1)
