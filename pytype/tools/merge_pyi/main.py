#!/usr/bin/env python

#   Copyright 2016 Google Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Merge .pyi file annotations into a .py file."""

from __future__ import print_function

import argparse
import difflib
import logging
import sys

from pytype.tools.merge_pyi import merge_pyi


def get_diff(a, b):
  a, b = a.split('\n'), b.split('\n')

  diff = difflib.Differ().compare(a, b)
  return '\n'.join(diff)


def parse_args(argv):
  """Process command line arguments using argparse."""

  parser = argparse.ArgumentParser(
      description='Populate file.py with type annotations from file.pyi.',
      epilog='Outputs merged file to stdout.')

  group = parser.add_mutually_exclusive_group()

  group.add_argument('-i', action='store_true', help='overwrite file.py')

  parser.add_argument(
      '--as-comments',
      action='store_true',
      help='insert type annotations as comments')

  group.add_argument('--diff', action='store_true', help='print out a diff')

  parser.add_argument(
      'py',
      type=argparse.FileType('r'),
      metavar='file.py',
      help='python file to annotate')

  parser.add_argument(
      'pyi',
      type=argparse.FileType('r'),
      metavar='file.pyi',
      help='PEP484 stub file with annotations for file.py')

  return parser.parse_args(argv[1:])


def main(argv=None):
  """Apply FixMergePyi to a source file without using the 2to3 main program.

  This is necessary so we can have our own options.

  Args:
    argv: Flags and files to process.
  """

  logging.basicConfig(level=logging.DEBUG)

  if argv is None:
    argv = sys.argv
  args = parse_args(argv)

  py_src = args.py.read()
  pyi_src = args.pyi.read()

  annotated_src = merge_pyi.annotate_string(args, py_src, pyi_src)
  src_changed = annotated_src != py_src

  if args.diff:
    if src_changed:
      diff = get_diff(py_src, annotated_src)
      print(diff)
  elif args.i:
    if src_changed:
      with open(args.py.name, 'w') as f:
        f.write(annotated_src)
      print('Merged types to %s from %s' % (args.py.name, args.pyi.name))
    else:
      print('No new types for %s in %s' % (args.py.name, args.pyi.name))
  else:
    sys.stdout.write(annotated_src)


if __name__ == '__main__':
  main()
