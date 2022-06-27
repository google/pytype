"""Testing code to run the typed_ast based pyi parser."""

import sys

from pytype import module_utils
from pytype.pyi import parser
from pytype.pyi.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pytd_utils


if __name__ == '__main__':
  filename = sys.argv[1]
  with open(filename) as f:
    src = f.read()

  module_name = module_utils.path_to_module_name(filename)

  try:
    out, _ = parser.parse_pyi_debug(src, filename, module_name)
  except ParseError as e:
    print(e)
    sys.exit(1)

  print('------pytd--------------')
  print(out)

  print('------round trip--------------')
  print(pytd_utils.Print(out))
