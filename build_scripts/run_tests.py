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
import subprocess
import sys

import build_utils
import test_module

NINJA_FAILURE_PREFIX = "FAILED: "


def parse_args():
  """Parse the args to this script and return the list of modules passed."""
  parser = argparse.ArgumentParser()
  parser.add_argument("modules", metavar="MODULE", nargs="*",
                      help="List of test modules to run.")
  parser.add_argument("--fail_fast", "-f", action="store_true", default=False,
                      help="Fail as soon as one build target fails.")
  args = parser.parse_args()
  for module in args.modules:
    if "." in module:
      _, mod_name = module.rsplit(".", 1)
    else:
      mod_name = module
    if not (mod_name.startswith("test_") or mod_name.endswith("_test")):
      sys.exit("The name '%s' is not a valid test module name." % module)
    path = module.replace(".", os.path.sep) + ".py"
    if not os.path.exists(os.path.join(build_utils.PYTYPE_SRC_ROOT, path)):
      sys.exit("Module '%s' does not exist.")
  return args


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
    print("\n%d test module(s) failed: \n" % num_failures)
    for mod_name, log_file in self._failures:
      print("** %s - %s" % (mod_name, log_file))


def run_ninja(targets, fail_collector, fail_fast=False):
  """Run ninja over the list of specified targets.

  Arguments:
    targets: The list of test targets to run.
    fail_collector: A FailCollector object to collect failures.
    fail_fast: If True, abort at the first target failure.

  Returns:
    True if no target fails. False, otherwise.
  """
  # The -k option to ninja, set to a very high value, makes it run until it
  # detects all failures. So, we set it to a high value unless |fail_fast| is
  # True.
  cmd = ["ninja", "-k", "1" if fail_fast else "100000"] + targets
  process = subprocess.Popen(cmd, cwd=build_utils.OUT_DIR,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  failed_targets = []
  with open(build_utils.NINJA_LOG, "w") as ninja_log:
    while True:
      line = process.stdout.readline()
      if not line:
        break
      if sys.version_info.major >= 3:
        # process.stdout.readline() always returns a 'bytes' object.
        line = line.decode("utf-8")
      ninja_log.write(line)
      if line.startswith(NINJA_FAILURE_PREFIX):
        # This is a failed ninja target.
        failed_targets.append(line[len(NINJA_FAILURE_PREFIX):].strip())
      modname, logfile = test_module.get_module_and_log_file_from_result_msg(line)
      if modname:
        print(line)
      if logfile:
        assert modname
        if fail_collector:
          fail_collector.add_failure(modname, logfile)
    if failed_targets:
      # For convenience, we will print the list of failed targets.
      summary_hdr = ">>> Detected Ninja target failures:"
      print("\n" + summary_hdr)
      ninja_log.write("\n" + summary_hdr + "\n")
      for t in failed_targets:
        target = "    - %s" % t
        print(target)
        ninja_log.write(target + "\n")
  process.wait()
  if process.returncode == 0:
    return True
  else:
    # Ninja output can be a lot. Printing it here will clutter the output of
    # this script. So, just tell the user how to repro the error.
    print(">>> FAILED: Ninja command '%s'." % " ".join(cmd))
    print(">>>         Run it in the 'out' directory to reproduce.")
    print(">>>         Full Ninja output is available in '%s'." %
          build_utils.NINJA_LOG)
    print(">>>         Failing test modules (if any) will be reported below.")
    return False


def main():
  opts = parse_args()
  modules = opts.modules or ["test_all"]
  if not build_utils.run_cmake(log_output=True):
    sys.exit(1)
  fail_collector = FailCollector()
  # PyType's target names use the dotted name convention. So, the fully
  # qualified test module names are actually ninja target names.
  print("Running tests (build steps will be executed as required) ...\n")
  if not run_ninja(modules, fail_collector, fail_fast=opts.fail_fast):
    fail_collector.print_report()
    sys.exit(1)
  print("!!! All tests passed !!!\n"
        "Some tests might not have been run because they were already passing.")


if __name__ == "__main__":
  main()
