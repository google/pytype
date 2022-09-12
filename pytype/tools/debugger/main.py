"""Run pytype and display debug information."""

import argparse
import sys

from pytype import config as pytype_config
from pytype import datatypes
from pytype import io
from pytype.inspect import graph
from pytype.tools import arg_parser


def make_parser():
  """Make parser for command line args.

  Returns:
    A Parser object.
  """
  parser = argparse.ArgumentParser(usage="%(prog)s [options] input")
  parser.add_argument(
      "--output-cfg", type=str, action="store",
      dest="output_cfg", default=None,
      help="Output control flow graph as SVG.")
  parser.add_argument(
      "--output-typegraph", type=str, action="store",
      dest="output_typegraph", default=None,
      help="Output typegraph as SVG.")
  # Add options from pytype-single.
  wrapper = datatypes.ParserWrapper(parser)
  pytype_config.add_all_pytype_options(wrapper)
  return arg_parser.Parser(parser, pytype_single_args=wrapper.actions)


def output_graphs(options, program):
  if options.output_cfg:
    tg = graph.TypeGraph(program, set(), only_cfg=True)
    svg_file = options.output_cfg
    graph.write_svg_from_dot(svg_file, tg.to_dot())

  if options.output_typegraph:
    tg = graph.TypeGraph(program, set(), only_cfg=False)
    svg_file = options.output_typegraph
    graph.write_svg_from_dot(svg_file, tg.to_dot())


def validate_args(parser, args):
  if args.output_cfg and args.output_typegraph == args.output_cfg:
    msg = "--output-typegraph and --output-cfg cannot write to the same file."
    parser.error(msg)


def main():
  parser = make_parser()
  args = parser.parse_args(sys.argv[1:])
  validate_args(parser, args.tool_args)
  result = io.check_or_generate_pyi(args.pytype_opts)
  output_graphs(args.tool_args, result.ctx.program)


if __name__ == "__main__":
  sys.exit(main() or 0)
