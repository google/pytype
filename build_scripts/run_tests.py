#! /usr/bin/python
"""Script to run PyType tests.

Usage:

$> python run_tests.py [TARGET] [TARGET] ...

A TARGET is a fully qualified name of a test target within the PyType
source tree. If no target is specified, all test targets listed in the
CMake files will be run.
"""

from __future__ import print_function
import argparse
import sys

import build_utils

def parse_args():
  """Parse the args to this script and return them."""
  parser = argparse.ArgumentParser()
  parser.add_argument("targets", metavar="TARGET", nargs="*",
                      help="List of test targets to run.")
  parser.add_argument("--fail_fast", "-f", action="store_true", default=False,
                      help="Fail as soon as one build target fails.")
  parser.add_argument("--debug", "-d", action="store_true", default=False,
                      help="Build targets in the debug mode.")
  parser.add_argument("--verbose", "-v", action="store_true", default=False,
                      help="Print failing test logs to stderr.")
  args = parser.parse_args()
  for target in args.targets:
    if "." in target:
      _, target_name = target.rsplit(".", 1)
    else:
      target_name = target
    if not (target_name.startswith("test_") or target_name.endswith("_test")):
      sys.exit("The name '%s' is not a valid test target name." % target)
  return args


def main():
  opts = parse_args()
  targets = opts.targets or ["test_all"]
  if not build_utils.run_cmake(log_output=True, debug_build=opts.debug):
    sys.exit(1)
  fail_collector = build_utils.FailCollector()
  print("Running tests (build steps will be executed as required) ...\n")
  if not build_utils.run_ninja(
      targets, fail_collector, opts.fail_fast, opts.verbose):
    fail_collector.print_report(opts.verbose)
    sys.exit(1)
  print("!!! All tests passed !!!\n"
        "Some tests might not have been run because they were already passing.")


if __name__ == "__main__":
  main()
