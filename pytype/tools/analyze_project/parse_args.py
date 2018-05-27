"""Argument parsing for analyze_project."""

import argparse

from pytype.tools.analyze_project import config


def parse_or_die(argv):
  """Parse command line args."""

  parser = argparse.ArgumentParser()
  parser.add_argument(
      'filenames', metavar='filename', type=str, nargs='*',
      help='input file(s)')
  modes = parser.add_mutually_exclusive_group()
  modes.add_argument(
      '--tree', dest='tree', action='store_true', default=False,
      help='Display import tree.')
  modes.add_argument(
      '--unresolved', dest='unresolved', action='store_true', default=False,
      help='Display unresolved dependencies.')
  modes.add_argument(
      '--generate-config', dest='generate_config', type=str, action='store',
      default='',
      help='Write out a dummy configuration file.')
  parser.add_argument(
      '-v', '--verbosity', dest='verbosity', type=int, action='store',
      default=1,
      help='Set logging level: 0=ERROR, 1 =WARNING (default), 2=INFO.')
  parser.add_argument(
      '--config', dest='config', type=str, action='store', default='',
      help='Configuration file.')
  types = config.make_converters()
  for short_arg, arg, dest in [('-V', '--python-version', 'python_version'),
                               ('-o', '--output', 'output'),
                               ('-P', '--pythonpath', 'pythonpath')]:
    # Without an explicit default, the argument defaults to None, allowing us
    # to tell whether it was passed or not.
    parser.add_argument(short_arg, arg, dest=dest, action='store',
                        type=types.get(dest), help=config.ITEMS[dest].comment)
  return parser.parse_args(argv)
