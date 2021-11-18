"""Call annotate_ast on a source file."""

import argparse
import sys

from pytype.ast import debug
from pytype.tools import arg_parser
from pytype.tools.annotate_ast import annotate_ast
from typed_ast import ast3


def main():
  parser = argparse.ArgumentParser(usage='%(prog)s [options] input')
  args, options = arg_parser.add_pytype_and_parse(parser, sys.argv[1:])

  filename = args.inputs[0]
  with open(filename, 'r') as f:
    src = f.read()
  module = annotate_ast.annotate_source(src, ast3, options)
  print(debug.dump(module, ast3))


if __name__ == '__main__':
  main()
