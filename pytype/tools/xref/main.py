#!/usr/bin/env python

"""Generate cross references from a project."""

from __future__ import print_function

import argparse
import signal
import sys

from pytype import config as pytype_config
from pytype import utils
from pytype.pytd.parse import node

from pytype.tools import arg_parser

from pytype.tools.xref import debug
from pytype.tools.xref import indexer
from pytype.tools.xref import kythe
from pytype.tools.xref import output


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

  # Add options from pytype-single.
  wrapper = arg_parser.ParserWrapper(parser)
  pytype_config.add_basic_options(wrapper)
  return arg_parser.Parser(parser, wrapper.actions)


def main():
  parser = make_parser()
  try:
    args = parser.parse_args(sys.argv[1:])
    options = pytype_config.Options(args.inputs)
    options.tweak(**parser.get_pytype_kwargs(args))
  except utils.UsageError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)

  node.SetCheckPreconditions(options.check_preconditions)

  if options.timeout is not None:
    signal.alarm(options.timeout)

  kythe_args = kythe.Args(corpus=args.kythe_corpus, root=args.kythe_root)
  ix = indexer.process_file(options, kythe_args=kythe_args)
  if options.debug:
    debug.show_index(ix)
  else:
    output.output_kythe_graph(ix)


if __name__ == "__main__":
  sys.exit(main())
