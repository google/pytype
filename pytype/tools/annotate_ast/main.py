"""Call annotate_ast on a source file."""

import argparse
import sys

from pytype.ast import debug
from pytype.tools import arg_parser
from pytype.tools.annotate_ast import annotate_ast
from typed_ast import ast27 as ast27
from typed_ast import ast3


def get_ast(options):
  major = options.python_version[0]
  return {2: ast27, 3: ast3}[major]


def main():
  parser = argparse.ArgumentParser(usage='%(prog)s [options] input')
  args, options = arg_parser.add_pytype_and_parse(parser, sys.argv[1:])

  filename = args.inputs[0]
  with open(filename, 'r') as f:
    src = f.read()
  module = annotate_ast.annotate_source(src, get_ast, options)
  ast = get_ast(options)
  print(debug.dump(module, ast))


if __name__ == '__main__':
  main()
