"""Parse command line arguments for xref."""

import argparse

from pytype import config as pytype_config
from pytype import datatypes
from pytype import utils as pytype_utils
from pytype.tools import arg_parser
from pytype.tools.xref import kythe


def make_parser():
  """Make parser for command line args.

  Returns:
    A Parser object.
  """

  def add_kythe_field(parser, field):
    parser.add_argument(
        "--" + field, dest=field, type=str, action="store", default="",
        help="Part of kythe's file-level vname proto.")

  parser = argparse.ArgumentParser(usage="%(prog)s [options] input")
  add_kythe_field(parser, "kythe_corpus")
  add_kythe_field(parser, "kythe_root")
  parser.add_argument("inputs", metavar="input", nargs=1,
                      help="A .py file to index")
  parser.add_argument("--debug", action="store_true",
                      dest="debug", default=None,
                      help="Display debug output.")
  # TODO(b/124802213): There should be a cleaner way to do this.
  parser.add_argument(
      "--imports_info", type=str, action="store",
      dest="imports_info", default=None,
      help="Information for mapping import .pyi to files. ")
  # Add options from pytype-single.
  wrapper = datatypes.ParserWrapper(parser)
  pytype_config.add_basic_options(wrapper)
  return arg_parser.Parser(parser, wrapper.actions)


def parse_args(argv):
  """Parse command line args.

  Arguments:
    argv: Raw command line args, typically sys.argv[1:]

  Returns:
    A tuple of (
      parsed_args: argparse.Namespace,
      kythe_args: kythe.Args,
      pytype_options: pytype.config.Options)
  """

  parser = make_parser()
  args = parser.parse_args(argv)
  cli_args = args.inputs.copy()
  # If we are passed an imports map we should look for pickled files as well.
  if args.imports_info:
    cli_args += ["--imports_info", args.imports_info,
                 "--use-pickled-files"]

  # We need to set this when creating Options (b/128032570)
  if args.python_version:
    cli_args += ["-V", pytype_utils.format_version(args.python_version)]

  pytype_options = pytype_config.Options(cli_args, command_line=True)
  pytype_options.tweak(**parser.get_pytype_kwargs(args))
  kythe_args = kythe.Args(corpus=args.kythe_corpus, root=args.kythe_root)
  return (args, kythe_args, pytype_options)
