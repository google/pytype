#!/usr/bin/env python
"""Script to run a C++ unit test binary.

Usage:

$> python run_cc_test.py -t TARGET -b BINARY [-l LOGFILE]

TARGET is the fully qualified name of the test target. BINARY is the test
binary. If LOGFILE is specified, then the test output is logged into it.
"""

from __future__ import print_function

import argparse
import sys

import build_utils

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("-t", "--target", required=True, type=str,
                      help="Name of the test target.")
  parser.add_argument("-b", "--binary", required=True, type=str,
                      help="Path to the test binary.")
  parser.add_argument("-l", "--logfile", type=str,
                      help="Path to log file to log test output.")
  return parser.parse_args()


def main():
  options = parse_args()
  returncode, stdout = build_utils.run_cmd([options.binary])
  if options.logfile:
    with open(options.logfile, "w") as logfile:
      logfile.write(stdout)
  if returncode == 0:
    print(build_utils.pass_msg(options.target))
  else:
    print(build_utils.failure_msg(options.target, options.logfile))
    sys.exit(1)


if __name__ == "__main__":
  main()
