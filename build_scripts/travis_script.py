#!/usr/bin/env python
"""A simple script to run Travis build steps."""

from __future__ import print_function

import collections
import os
import sys

import build_utils

def _ismod(f):
  """Return True if f is a Python module but not a test module."""
  return f.endswith(".py") and not f.endswith("_test.py")


STEP = collections.namedtuple("STEP", ["name", "command"])

PYTYPE_COMMAND = os.path.join("out", "bin", "pytype")
PYC_DIR = os.path.join(build_utils.PYTYPE_SRC_ROOT, "pytype", "pyc")
PYC_FILES = [os.path.join(PYC_DIR, f) for f in os.listdir(PYC_DIR) if _ismod(f)]
TYPECHECK_FILES = [
    "pytype/compat.py", "pytype/debug.py", "pytype/utils.py"] + PYC_FILES


def _begin_step(s):
  print("")
  print("BEGIN_STEP: %s" % s.name)
  print("STEP_COMMAND: %s" % ' '.join(s.command))
  print("")


def _end_step(s):
  print("\nEND_STEP: %s\n" % s.name)


def _report_failure(s):
  print("")
  print(">>> STEP_FAILED: %s" % s.name)
  print("")


def _run_steps(steps):
  for s in steps:
    _begin_step(s)
    returncode, _ = build_utils.run_cmd(s.command, pipe=False)
    if returncode != 0:
      _report_failure(s)
      sys.exit(1)
    _end_step(s)
    

def main():
  s1 = STEP(name="Build",
            command=["python", build_utils.build_script("build.py")])
  s2 = STEP(name="Run Tests",
            command=["python", build_utils.build_script("run_tests.py"), "-f"])
  s3 = STEP(name="Type Check",
            command=[PYTYPE_COMMAND] + TYPECHECK_FILES)
  _run_steps([s1, s2, s3])
  print("\n*** All build steps completed successfully! ***\n")


if __name__ == "__main__":
  main()
