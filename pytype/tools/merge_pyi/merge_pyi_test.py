import collections
import difflib
import logging
import os
import re
import sys

from pytype.tools.merge_pyi import merge_pyi
import unittest


__all__ = ('TestBuilder', 'load_tests')


PY, PYI = 'py', 'pyi'
OVERWRITE_EXPECTED = 0  # flip to regenerate expected files


def load_tests(unused_loader, standard_tests, unused_pattern):
  root = os.path.join(os.path.dirname(__file__), 'test_data')
  paths = [root]
  if sys.version_info >= (3, 6):
    paths.append(os.path.join(root, 'py36'))
  for path in paths:
    standard_tests.addTests(TestBuilder().build(path))
  return standard_tests


class TestBuilder(object):

  def build(self, data_dir):
    """Return a unittest.TestSuite with tests for the files in data_dir."""
    files_by_base = self._get_files_by_base(data_dir)

    args_list = [
        Args(as_comments=0),
        Args(as_comments=1),
    ]

    suite = unittest.TestSuite()
    for args in args_list:
      arg_suite = unittest.TestSuite()
      suite.addTest(arg_suite)

      for base, files_by_ext in sorted(files_by_base.items()):
        if not (PY in files_by_ext and PYI in files_by_ext):
          continue

        if not OVERWRITE_EXPECTED and args.expected_ext not in files_by_ext:
          continue

        py, pyi = [files_by_ext[x] for x in (PY, PYI)]
        outfile = os.path.join(data_dir, base + '.' + args.expected_ext)

        test = build_regression_test(args, py, pyi, outfile)
        arg_suite.addTest(test)

    return suite

  def _get_files_by_base(self, data_dir):
    files = os.listdir(data_dir)

    file_pat = re.compile(r'(?P<filename>(?P<base>.+?)\.(?P<ext>.*))$')
    matches = [m for m in map(file_pat.match, files) if m]
    ret = collections.defaultdict(dict)
    for m in matches:
      base, ext, filename = m.group('base'), m.group('ext'), m.group('filename')
      ret[base][ext] = os.path.join(data_dir, filename)

    return ret


class Args(object):

  def __init__(self, as_comments=False):
    self.as_comments = as_comments

  @property
  def expected_ext(self):
    """Extension of expected filename."""
    exts = {
        0: 'pep484',
        1: 'comment',
    }
    return exts[int(self.as_comments)] + '.py'


def build_regression_test(args, py, pyi, outfile):

  def regression_test(test_case):
    py_input, pyi_src = [_read_file(f) for f in (py, pyi)]

    output = merge_pyi.annotate_string(args, py_input, pyi_src)

    if OVERWRITE_EXPECTED:
      with open(outfile, 'w') as f:
        f.write(output)
    else:
      expected = _read_file(outfile)
      test_case.assertEqual(expected, output, _get_diff(expected, output))

  name = os.path.splitext(os.path.basename(outfile))[0].replace('.', '_')
  test = 'test_%s' % name
  case = type('RegressionTest', (unittest.TestCase,), {test: regression_test})
  return case(test)


def _read_file(filename):
  with open(filename) as f:
    return f.read()


def _get_diff(a, b):
  a, b = a.split('\n'), b.split('\n')

  diff = difflib.Differ().compare(a, b)
  return '\n'.join(diff)


if __name__ == '__main__':
  logging.basicConfig(level=logging.CRITICAL)
  unittest.main()
