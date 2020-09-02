"""Argument parsing for tools that pass args on to pytype_single."""

import argparse

from pytype import config as pytype_config
from pytype import datatypes
from pytype import utils as pytype_utils


def string_to_bool(s):
  return s == "True" if s in ("True", "False") else s


def convert_string(s):
  s = s.replace("\n", "")
  try:
    return int(s)
  except ValueError:
    return string_to_bool(s)


class Parser:
  """Parser that integrates tool and pytype-single args."""

  def __init__(self, parser, pytype_single_args):
    """Initialize a parser.

    Args:
      parser: An argparse.ArgumentParser or compatible object
      pytype_single_args: Iterable of args that will be passed to pytype_single
    """
    self.parser = parser
    self.pytype_single_args = pytype_single_args

  def create_initial_args(self, keys):
    """Creates the initial set of args.

    Args:
      keys: A list of keys to create args from

    Returns:
      An argparse.Namespace.
    """
    return argparse.Namespace(**{k: None for k in keys})

  def parse_args(self, argv):
    """Parses argv.

    Args:
      argv: sys.argv[1:]

    Returns:
      An argparse.Namespace.
    """
    args = self.create_initial_args(self.pytype_single_args)
    self.parser.parse_args(argv, args)
    self.postprocess(args)
    return args

  def postprocess(self, args, from_strings=False):
    """Postprocesses the subset of pytype_single_args that appear in args.

    Args:
      args: an argparse.Namespace.
      from_strings: Whether the args are all strings. If so, we'll do our best
        to convert them to the right types.
    """
    names = set()
    for k in self.pytype_single_args:
      if hasattr(args, k):
        names.add(k)
        if from_strings:
          setattr(args, k, convert_string(getattr(args, k)))
    pytype_config.Postprocessor(names, args).process()

  def get_pytype_kwargs(self, args):
    """Return a set of kwargs to pass to pytype.config.Options.

    Args:
      args: an argparse.Namespace.

    Returns:
      A dict of kwargs with pytype_single args as keys.
    """
    return {k: getattr(args, k) for k in self.pytype_single_args}


def add_pytype_and_parse(parser, argv):
  """Add basic pytype options and parse args.

  Useful to generate a quick CLI for a library.

  Args:
    parser: An argparse.ArgumentParser
    argv: Raw command line args, typically sys.argv[1:]

  Returns:
    A tuple of (
      parsed_args: argparse.Namespace,
      pytype_options: pytype.config.Options)
  """
  # Add default --debug and input arguments.
  parser.add_argument("--debug", action="store_true",
                      dest="debug", default=None,
                      help="Display debug output.")
  parser.add_argument("inputs", metavar="input", nargs=1,
                      help="A .py file to index")

  # Add options from pytype-single.
  wrapper = datatypes.ParserWrapper(parser)
  pytype_config.add_basic_options(wrapper)
  parser = Parser(parser, wrapper.actions)

  # Parse argv
  args = parser.parse_args(argv)
  cli_args = args.inputs.copy()

  # Make sure we have a valid set of CLI options to pytype

  ## If we are passed an imports map we should look for pickled files as well.
  if getattr(args, "imports_info", None):
    cli_args += ["--imports_info", args.imports_info,
                 "--use-pickled-files"]

  ## We need to set this when creating Options (b/128032570)
  if args.python_version:
    cli_args += ["-V", pytype_utils.format_version(args.python_version)]

  pytype_options = pytype_config.Options(cli_args, command_line=True)
  pytype_options.tweak(**parser.get_pytype_kwargs(args))
  return (args, pytype_options)
