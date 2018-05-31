"""Argument parsing for analyze_project."""

import argparse

from pytype import config as pytype_config
from pytype.tools.analyze_project import config


class ParserWrapper(object):
  """Wrapper that adds arguments to a parser while recording their names."""

  def __init__(self, parser):
    self.parser = parser
    self.names = set()

  def add_argument(self, *args, **kwargs):
    try:
      self.parser.add_argument(*args, **kwargs)
    except argparse.ArgumentError:
      # We deliberately mask some pytype-single options with pytype-all ones.
      pass
    else:
      self.names.add(kwargs['dest'])


def parse_or_die(argv):
  """Parse command line args.

  Args:
    argv: sys.argv[1:]

  Returns:
    A tuple of pytype-all args and pytype-single args.
  """

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
  # Adds options that can also be set in a config file.
  types = config.make_converters()
  for short_arg, arg, dest in [('-V', '--python-version', 'python_version'),
                               ('-o', '--output', 'output'),
                               ('-P', '--pythonpath', 'pythonpath')]:
    # Without an explicit default, the argument defaults to None, allowing us
    # to tell whether it was passed or not.
    parser.add_argument(short_arg, arg, dest=dest, action='store',
                        type=types.get(dest), help=config.ITEMS[dest].comment)
  # Adds options from pytype-single and gets their names.
  wrapper = ParserWrapper(parser)
  pytype_config.add_basic_options(wrapper)
  pytype_single_names = wrapper.names
  # Parses everything and splits out the pytype-single options.
  args = parser.parse_args(argv)
  pytype_single_args = argparse.Namespace()
  pytype_config.Postprocessor(
      args, pytype_single_args, pytype_single_names).process()
  for name in pytype_single_names:
    delattr(args, name)
  return args, pytype_single_args
