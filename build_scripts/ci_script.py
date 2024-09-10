#!/usr/bin/env python
"""A simple script to run CI build steps."""

import collections
import os
import sys

import build_utils
import time


STEP = collections.namedtuple("STEP", ["name", "command"])


def _begin_step(s):
  print("")
  if os.getenv("GITHUB_ACTIONS"):
    print(f"::group::{s.name}")
  else:
    print(f"BEGIN_STEP: {s.name}")
  print(flush=True)


def _end_step(s):
  print("")
  if os.getenv("GITHUB_ACTIONS"):
    print("::endgroup::")
  else:
    print(f"END_STEP: {s.name}")
  print(flush=True)


def _report_failure(s):
  print("")
  if os.getenv("GITHUB_ACTIONS"):
    print(f"::error::STEP FAILED: {s.name}")
  else:
    print(f">>> STEP_FAILED: {s.name}")
  print(flush=True)


def _run_steps(steps):
  for s in steps:
    begin = time.time()
    _begin_step(s)
    try:
      returncode, _ = build_utils.run_cmd(s.command, pipe=False)
      if returncode != 0:
        _report_failure(s)
        sys.exit(1)
    finally:
      end = time.time()
      print("Took " + str(end - begin) + "s")
      _end_step(s)


def main():
  s1 = STEP(
      name="Lint",
      command=[
          "pylint",
          "build_scripts/",
          "pytype/",
          "pytype_extensions/",
          "setup.py",
      ],
  )
  s2 = STEP(
      name="Build", command=["python", build_utils.build_script("build.py")]
  )
  s3 = STEP(
      name="Run Tests",
      command=["python", build_utils.build_script("run_tests.py"), "-f", "-v"],
  )
  s4 = STEP(
      name="Type Check",
      command=(["python"] if sys.platform == "win32" else [])
      + [os.path.join("out", "bin", "pytype"), "-j", "auto"],
  )
  steps = [s1, s2, s3, s4]
  if os.environ.get("LINT") == "false":
    steps.remove(s1)
  _run_steps(steps)
  print("\n*** All build steps completed successfully! ***\n")


if __name__ == "__main__":
  main()
