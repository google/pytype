#! /usr/bin/python
"""Script to run PyType tests.

Usage:

$> python run_tests.py [MODULE] [MODULE] ...

A MODULE is a fully qualified name of a test module within the PyType
source tree. If no module is specified, all test targets listed in the
CMake files will be run.
"""

from __future__ import print_function
import argparse
import os
import shutil
import subprocess
import sys

import test_module


PYTYPE_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PYTYPE_SRC_ROOT, "out")


def current_py_version():
  """Return the Python version under which this script is being run."""
  return "%d.%d" % (sys.version_info.major, sys.version_info.minor)


class PyVersionCache(object):
  """Utility class to manage the Python version cache."""

  VERSION_CACHE = os.path.join(OUT_DIR, ".python_version")

  @classmethod
  def read(cls):
    if os.path.exists(cls.VERSION_CACHE):
      with open(cls.VERSION_CACHE, "r") as f:
        return f.readline().strip()
    else:
      # There is no python version cache file during the very first run.
      return ""

  @classmethod
  def cache(cls):
    with open(cls.VERSION_CACHE, "w") as f:
      f.write(current_py_version())


def parse_args():
  """Parse the args to this script and return the list of modules passed."""
  parser = argparse.ArgumentParser()
  parser.add_argument("modules", metavar="MODULE", nargs="*",
                      help="List of test modules to run.")
  args = parser.parse_args()
  for module in args.modules:
    if "." in module:
      _, mod_name = module.rsplit(".", 1)
    else:
      mod_name = module
    if not (mod_name.startswith("test_") or mod_name.endswith("_test")):
      sys.exit("The name '%s' is not a valid test module name." % module)
    path = module.replace(".", os.path.sep) + ".py"
    if not os.path.exists(os.path.join(PYTYPE_SRC_ROOT, path)):
      sys.exit("Module '%s' does not exist.")
  return args.modules


class FailCollector(object):
  """A class to collect failures."""

  def __init__(self):
    self._failures = []

  def add_failure(self, mod_name, log_file):
    self._failures.append((mod_name, log_file))

  def print_report(self):
    num_failures = len(self._failures)
    if num_failures == 0:
      return
    print("\n%d module(s) failed: \n" % num_failures)
    for mod_name, log_file in self._failures:
      print("** %s - %s" % (mod_name, log_file))


def _clean_out_dir():
  for item in os.listdir(OUT_DIR):
    path = os.path.join(OUT_DIR, item)
    if os.path.isdir(path):
      shutil.rmtree(path)
    elif item != "README.md":
      os.remove(path)


def run_cmake():
  """Run cmake in the 'out' directory."""
  current_version = current_py_version()
  if PyVersionCache.read() != current_version:
    print("Previous Python version is not %s; cleaning 'out' directory.\n" %
          current_version)
    _clean_out_dir()

  if os.path.exists(os.path.join(OUT_DIR, "build.ninja")):
    # Run CMake if it was not already run. If CMake was already run, it
    # generates a build.ninja file in the "out" directory.
    print("Running CMake skipped ...\n")
    return True

  print("Running CMake ...\n")
  cmd = ["cmake", PYTYPE_SRC_ROOT, "-G", "Ninja",
         "-DPython_ADDITIONAL_VERSIONS=%s" % current_version]
  process = subprocess.Popen(cmd, cwd=OUT_DIR, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
  stdout, _ = process.communicate()
  # Cache the Python version for which the build files have been generated.
  PyVersionCache.cache()
  if process.returncode != 0:
    print("Running %s failed:\n%s" % (cmd, stdout))
    return False
  return True


def run_ninja(targets, fail_collector):
  """Run ninja over the list of specified targets.

  Arguments:
    targets: The list of test targets to run.
    fail_collector: A FailCollector object to collect failures.

  Returns:
    True if no target fails. False, otherwise.
  """
  # The -k option to ninja, set to a very high value, makes it run until it
  # detects all failures.
  cmd = ["ninja", "-k", "100000"] + targets
  process = subprocess.Popen(cmd, cwd=OUT_DIR,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  have_failures = False
  while True:
    # process.stdout.readline() always returns a 'bytes' object.
    l = process.stdout.readline().decode("utf-8")
    if not l:
      break
    mod_name, log_file = test_module.get_module_and_log_file_from_result_msg(l)
    if mod_name:
      print(l)
    if log_file:
      have_failures = True
      if fail_collector:
        fail_collector.add_failure(mod_name, log_file)
  process.wait()
  if process.returncode == 0:
    return True
  else:
    if not have_failures:
      print("Running %s failed." % cmd)
    return False


def main():
  modules = parse_args()
  if not modules:
    modules = ["test_all"]
  if not run_cmake():
    sys.exit(1)
  fail_collector = FailCollector()
  # PyType's target names use the dotted name convention. So, the fully
  # qualified test module names are actually ninja target names.
  print("Building ...\n")
  if not run_ninja(["all"], None):
    sys.exit(1)
  print("Running tests ...\n")
  if not run_ninja(modules, fail_collector):
    fail_collector.print_report()
    sys.exit(1)


if __name__ == "__main__":
  main()
