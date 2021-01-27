# python3

"""Testing code to run the typed_ast based pyi parser."""

import sys

from pytype import module_utils
from pytype.pyi import parser
from pytype.pyi.typed_ast import ast_parser
from pytype.pyi.typed_ast.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pytd_utils


if __name__ == '__main__':
  filename = sys.argv[1]
  with open(filename, 'r') as f:
    src = f.read()

  module_name = module_utils.path_to_module_name(filename)

  version = (3, 6)
  try:
    out, _ = ast_parser.parse_pyi_debug(
        src, filename, module_name, version, None)
  except ParseError as e:
    print(e)
    sys.exit(1)

  print('------round trip--------------')
  print(pytd_utils.Print(out))

  # print out the pytd tree so we can compare it to the output from ast_parser
  pytd = parser.old_parse_string(src, filename=filename, python_version=version,
                                 name=module_name)
  print('------pytd--------------')
  print(pytd)
  print('------pytd--------------')
  print(pytd_utils.Print(pytd))

  print('------round trip--------------')
  print(pytd_utils.Print(pytd))
