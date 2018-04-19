"""Support for running pytype from an external tool."""

from __future__ import print_function

import os
import subprocess
import sys


class BinaryRun(object):
  """Convenience wrapper around subprocess.

  Use as:
    ret, out, err = BinaryRun([exe, arg, ...]).communicate()
  """

  def __init__(self, args, dry_run=False, env=None):
    self.args = args
    self.results = None

    if dry_run:
      self.results = (0, "", "")
    else:
      if env is not None:
        full_env = os.environ.copy()
        full_env.update(env)
      else:
        full_env = None
      self.proc = subprocess.Popen(
          self.args,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          env=full_env)

  def communicate(self):
    if self.results:
      # We are running in dry-run mode.
      return self.results

    stdout, stderr = self.proc.communicate()
    self.results = self.proc.returncode, stdout, stderr
    return self.results


def can_run(exe, *args):
  """Check if running exe with args works."""
  try:
    BinaryRun([exe] + list(args)).communicate()
    return True
  except OSError:
    return False


def check_pytype_or_die():
  if not can_run("pytype", "-h"):
    print("Cannot run pytype. Check that it is installed and in your path")
    sys.exit(1)


def check_python_version(exe, required):
  """Check if exe is a python executable with the required version."""
  try:
    # python --version outputs to stderr for earlier versions
    _, out, err = BinaryRun([exe, "--version"]).communicate()  # pylint: disable=unpacking-non-sequence
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


def get_typeshed_location(opts):
  """Find a typeshed installation if present.

  Tools should standardise on pointing to typeshed via
    - A --typeshed_location argument
    - The $TYPESHED_HOME environment variable

  Args:
    opts: an optparse.Values object

  Returns:
    A path to a valid typeshed installation, or None.
  """
  opt = opts.typeshed_location
  env = os.environ.get("TYPESHED_HOME", None)
  ret = opt or env or ""
  if not os.path.isdir(os.path.join(ret, "stdlib")):
    return None
  return ret


def get_typeshed_location_or_die(opts):
  """Return the typeshed location or die.

  Args:
    opts: an optparse.Values object

  Returns:
    A path to a valid typeshed installation.

  See get_typeshed_location() for details.
  """
  ret = get_typeshed_location(opts)
  if not ret:
    opt = opts.typeshed_location
    env = os.environ.get("TYPESHED_HOME", None)
    print("Cannot find a valid typeshed installation.")
    print("Searched in:")
    print("  --typeshed-location argument: ", opt)
    print("  TYPESHED_HOME environment variable: ", env)
    sys.exit(1)
  return ret
