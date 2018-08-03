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


def main():
  opts = parse_args()
  modules = opts.modules or ["test_all"]
  if not build_utils.run_cmake(log_output=True):
    sys.exit(1)
  fail_collector = build_utils.FailCollector()
  # PyType's target names use the dotted name convention. So, the fully
  # qualified test module names are actually ninja target names.
  print("Running tests (build steps will be executed as required) ...\n")
  if not build_utils.run_ninja(modules, fail_collector, opts.fail_fast):
    fail_collector.print_report()
    sys.exit(1)
  print("!!! All tests passed !!!\n"
        "Some tests might not have been run because they were already passing.")


if __name__ == "__main__":
  main()
