#!/usr/bin/env python
"""A simple script to run CI build steps."""

import collections
import os
import sys

import build_utils


STEP = collections.namedtuple("STEP", ["name", "command"])


def _begin_step(s):
  print("")
  print(f"BEGIN_STEP: {s.name}")
  print(f"STEP_COMMAND: {' '.join(s.command)}")
  print("")


def _end_step(s):
  print(f"\nEND_STEP: {s.name}\n")


def _report_failure(s):
  print("")
  print(f">>> STEP_FAILED: {s.name}")
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
  s1 = STEP(name="Lint",
            command=["pylint", "build_scripts/", "pytype/",
                     "pytype_extensions/", "setup.py"])
  s2 = STEP(name="Build",
            command=["python", build_utils.build_script("build.py")])
  s3 = STEP(name="Run Tests",
            command=[
                "python", build_utils.build_script("run_tests.py"), "-f", "-v"])
  s4 = STEP(name="Run Extensions Tests",
            command=["python", "-m",
                     "pytype_extensions.test_pytype_extensions"])
  s5 = STEP(name="Type Check",
            command=(['python'] if sys.platform == 'win32' else []) +
               [os.path.join("out", "bin", "pytype"), "-j", "auto"])
  _run_steps([s1, s2, s3, s4, s5])
  print("\n*** All build steps completed successfully! ***\n")


if __name__ == "__main__":
  main()
