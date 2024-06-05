#!/usr/bin/env python
"""A convenience script to build all pytype targets.

Usage:
  $> build.py [-c]

Specifying the -c option forces a clobber before building.
"""

import argparse
import sys

import build_utils

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("--clobber", "-c", action="store_true", default=False,
                      help="Force clobber before building.")
  parser.add_argument("--debug", "-d", action="store_true", default=False,
                      help="Build targets in the debug mode.")
  return parser.parse_args()


def main():
  options = parse_args()
  if not build_utils.run_cmake(force_clean=options.clobber, log_output=True,
                               debug_build=options.debug):
    sys.exit(1)
  print("Building all targets with Ninja ...\n")
  if not build_utils.run_ninja(["all"], fail_fast=True):
    sys.exit(1)
  print("Pytype built successfully!\n")


if __name__ == "__main__":
  main()
