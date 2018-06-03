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
      action = self.parser.add_argument(*args, **kwargs)
    except argparse.ArgumentError:
      # We deliberately mask some pytype-single options with pytype-all ones.
      pass
    else:
      self.names.add(action.dest)


def convert_string(s):
  s = s.replace('\n', '')
  try:
    return int(s)
  except ValueError:
    if s in ('True', 'False'):
      return s == 'True'
    else:
      return s


class Parser(object):
  """pytype-all parser."""

  def __init__(self, parser, pytype_single_names):
    self.parser = parser
    self.pytype_single_names = pytype_single_names

  def parse_args(self, argv):
    """Parses argv.

    Commandline-only args are parsed normally. File-configurable args appear in
    the parsed args only if explicitly present in argv.

    Args:
      argv: sys.argv[1:]

    Returns:
      An argparse.Namespace.
    """
    file_config_names = set(config.ITEMS) | self.pytype_single_names
    # Creates a namespace that we'll parse argv into, so that we can check for
    # a file configurable arg by whether the None default was overwritten.
    args = argparse.Namespace(**{k: None for k in file_config_names})
    self.parser.parse_args(argv, args)
    for k in file_config_names:
      if getattr(args, k) is None:
        delattr(args, k)
    self.postprocess(args)
    return args

  def config_from_defaults(self):
    defaults = self.parser.parse_args([])
    self.postprocess(defaults)
    conf = config.Config(*self.pytype_single_names)
    conf.populate_from(defaults)
    return conf

  def postprocess(self, args, from_strings=False):
    """Postprocesses the subset of pytype_single_names that appear in args.

    Args:
      args: an argparse.Namespace.
      from_strings: Whether the args are all strings. If so, we'll do our best
        to convert them to the right types.
    """
    names = set()
    for k in self.pytype_single_names:
      if hasattr(args, k):
        names.add(k)
        if from_strings:
          setattr(args, k, convert_string(getattr(args, k)))
    pytype_config.Postprocessor(names, args).process()


def make_parser():
  """Make parser for command line args.

  Returns:
    A Parser object.
  """

  parser = argparse.ArgumentParser(usage='%(prog)s [options] input [input ...]')
  parser.add_argument(
      'filenames', metavar='input', type=str, nargs='*',
      help='file or directory to process')
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
  # Adds options from the config file.
  types = config.make_converters()
  for short_arg, arg, dest in [('-V', '--python-version', 'python_version'),
                               ('-o', '--output', 'output'),
                               ('-P', '--pythonpath', 'pythonpath')]:
    parser.add_argument(short_arg, arg, dest=dest, type=types.get(dest),
                        action='store', default=config.ITEMS[dest].default,
                        help=config.ITEMS[dest].comment)
  # Adds options from pytype-single.
  wrapper = ParserWrapper(parser)
  pytype_config.add_basic_options(wrapper)
  return Parser(parser, wrapper.names)
