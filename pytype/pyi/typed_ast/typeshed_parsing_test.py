"""Test that the typed_ast based parser works identically to the current one."""

import difflib
import glob
import sys

from pytype import module_utils
from pytype.pyi import parser
from pytype.pyi.typed_ast import ast_parser
from pytype.pytd import pytd_utils


# Diffs that are either inconsequential or a bug in the old parser.
WONTFIX_BLOCKLIST = frozenset({
    # namedtuples generated within if-versioned-out code
    'third_party/py/typeshed/stdlib/2and3/_curses.pyi',
    'third_party/py/typeshed/stdlib/3/_thread.pyi',
    'third_party/py/typeshed/stdlib/3/inspect.pyi',
    'third_party/py/typeshed/stdlib/2and3/time.pyi',
    'third_party/py/typeshed/stdlib/3/importlib/metadata.pyi',
    'third_party/py/typeshed/stdlib/3/os/__init__.pyi',

    # outputs defs in the wrong order
    'third_party/py/typeshed/stdlib/2/urllib2.pyi',
    'third_party/py/typeshed/stdlib/2/functools.pyi',
    'third_party/py/typeshed/stdlib/3/json/decoder.pyi',
    'third_party/py/typeshed/stdlib/3/unittest/mock.pyi',
    'third_party/py/typeshed/third_party/3/six/__init__.pyi',
    'third_party/py/typeshed/third_party/2/six/__init__.pyi',
    'third_party/py/typeshed/stdlib/3/asyncio/windows_events.pyi',

    # some typing imports are not reexported in the old parser
    'third_party/py/typeshed/third_party/2and3/typing_extensions.pyi',

    # old parser raises an error
    'third_party/py/typeshed/stdlib/2/typing.pyi',
    'third_party/py/typeshed/stdlib/3/typing.pyi',
})

# Diffs that are a bug in the new parser.
OTHER_BLOCKLIST = frozenset({
    'third_party/py/typeshed/stdlib/3.9/zoneinfo/__init__.pyi',
})

BLOCKLIST = WONTFIX_BLOCKLIST | OTHER_BLOCKLIST


def test_file(filename):
  with open(filename, 'r') as f:
    src = f.read()

  version = sys.version_info[:2]

  # get module name from filename
  mod = module_utils.path_to_module_name(filename)
  if mod.startswith('third_party.py.typeshed'):
    mod = mod.split('.')[5:]
    mod = '.'.join(mod)

  # Parse using typed ast parser
  out = ast_parser.parse_pyi(src, filename=filename, module_name=mod,
                             python_version=version)
  new = pytd_utils.Print(out).replace('"', "'").splitlines(True)

  # Parse using bison parser
  pytd = parser.old_parse_string(src, name=mod, filename=filename,
                                 python_version=version)
  old = pytd_utils.Print(pytd).replace('"', "'").splitlines(True)

  if old != new:
    print(''.join(old))
    diff = difflib.unified_diff(old, new, fromfile=filename, tofile=filename)
    # Display first diff we find and exit.
    sys.stdout.writelines(diff)
    print()
    print(f"FAILED: '{filename}'")
    sys.exit(1)


def test_all(basedir, ext):
  for f in glob.glob(f'{basedir}/**/*.{ext}', recursive=True):
    if f in BLOCKLIST:
      print('SKIPPED:', f)
      continue
    print('TESTING:', f)
    test_file(f)


if __name__ == '__main__':
  if len(sys.argv) > 1:
    test_file(sys.argv[1])
  else:
    test_all('third_party/py/typeshed/stdlib', 'pyi')
    test_all('third_party/py/typeshed/third_party', 'pyi')
    test_all('third_party/py/pytype/pytd', 'pytd')
