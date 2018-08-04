#!/usr/bin/env python
"""A convenience script to build all pytype targets.

Usage:
  $> build.py [-c]

Specifying the -c option forces a clobber before building.
"""

import argparse

import build_utils

def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument("--clobber", "-c", action="store_true", default=False,
                      help="Force clobber before building.")
  return parser.parse_args()


def main():
  options = parse_args()
  if not build_utils.run_cmake(force_clean=options.clobber):
    return 1
  if not build_utils.run_ninja(["all"], fail_fast=True):
    return 1


if __name__ == "__main__":
  main()
