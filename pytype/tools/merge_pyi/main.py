"""Merge .pyi file annotations into a .py file."""

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

  def check_verbosity(v):
    v = int(v)  # may raise ValueError
    if -1 <= v <= 4:
      return v
    raise ValueError()
  parser.add_argument(
      '-v', '--verbosity', type=check_verbosity, action='store', default=1,
      help=('Set logging verbosity: '
            '-1=quiet, 0=fatal, 1=error (default), 2=warn, 3=info, 4=debug'))

  group = parser.add_mutually_exclusive_group()

  group.add_argument(
      '-i', '--in-place', action='store_true', help='overwrite file.py')

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

  if argv is None:
    argv = sys.argv
  args = parse_args(argv)

  # Log levels range from 10 (DEBUG) to 50 (CRITICAL) in increments of 10. A
  # level >50 prevents anything from being logged.
  logging.basicConfig(level=50-args.verbosity*10)

  py_src = args.py.read()
  pyi_src = args.pyi.read()

  annotated_src = merge_pyi.annotate_string(args, py_src, pyi_src)
  src_changed = annotated_src != py_src

  if args.diff:
    if src_changed:
      diff = get_diff(py_src, annotated_src)
      print(diff)
  elif args.in_place:
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
