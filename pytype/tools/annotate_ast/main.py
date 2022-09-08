"""Call annotate_ast on a source file."""

import argparse
import sys

from pytype.ast import debug
from pytype.tools import arg_parser
from pytype.tools.annotate_ast import annotate_ast

# pylint: disable=g-import-not-at-top
if sys.version_info >= (3, 8):
  import ast as ast3
else:
  from typed_ast import ast3
# pylint: enable=g-import-not-at-top


def main():
  parser = argparse.ArgumentParser(usage='%(prog)s [options] input')
  args = arg_parser.Parser(parser).parse_args(sys.argv[1:])

  filename = args.pytype_opts.input
  with open(filename) as f:
    src = f.read()
  module = annotate_ast.annotate_source(src, ast3, args.pytype_opts)
  print(debug.dump(module, ast3))


if __name__ == '__main__':
  main()
