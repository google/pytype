"""Tests for parse_args.py."""

import os
import unittest

from pytype.tools.analyze_project import parse_args


class TestParseOrDie(unittest.TestCase):

  def test_parse_filenames(self):
    filenames = ['a.py', 'b.py']
    args, _ = parse_args.parse_or_die(filenames)
    self.assertSequenceEqual(args.filenames, filenames)

  def test_verbosity(self):
    self.assertEqual(parse_args.parse_or_die(
        ['--verbosity', '0'])[0].verbosity, 0)
    self.assertEqual(parse_args.parse_or_die(['-v1'])[0].verbosity, 1)

  def test_config(self):
    args, _ = parse_args.parse_or_die(['--config=test.cfg'])
    self.assertEqual(args.config, 'test.cfg')

  def test_tree(self):
    args, _ = parse_args.parse_or_die(['--tree'])
    self.assertTrue(args.tree)
    with self.assertRaises(SystemExit):
      parse_args.parse_or_die(['--tree', '--unresolved'])

  def test_unresolved(self):
    args, _ = parse_args.parse_or_die(['--unresolved'])
    self.assertTrue(args.unresolved)

  def test_generate_config(self):
    args, _ = parse_args.parse_or_die(['--generate-config', 'test.cfg'])
    self.assertEqual(args.generate_config, 'test.cfg')
    with self.assertRaises(SystemExit):
      parse_args.parse_or_die(['--generate-config', 'test.cfg', '--tree'])

  def test_python_version(self):
    self.assertEqual(parse_args.parse_or_die(
        ['-V2.7'])[0].python_version, '2.7')
    self.assertEqual(parse_args.parse_or_die(
        ['--python-version', '2.7'])[0].python_version, '2.7')

  def test_output(self):
    self.assertEqual(parse_args.parse_or_die(
        ['-o', 'pyi'])[0].output, os.path.join(os.getcwd(), 'pyi'))
    self.assertEqual(parse_args.parse_or_die(
        ['--output', 'pyi'])[0].output, os.path.join(os.getcwd(), 'pyi'))

  def test_pythonpath(self):
    d = os.getcwd()
    self.assertSequenceEqual(parse_args.parse_or_die(
        ['-P', ':foo'])[0].pythonpath, [d, os.path.join(d, 'foo')])
    self.assertSequenceEqual(parse_args.parse_or_die(
        ['--pythonpath', ':foo'])[0].pythonpath, [d, os.path.join(d, 'foo')])

  def test_defaults(self):
    args, _ = parse_args.parse_or_die([])
    for arg in ['python_version', 'output', 'pythonpath']:
      self.assertIsNone(getattr(args, arg))

  def test_pytype_single_args(self):
    args, pytype_single_args = parse_args.parse_or_die(
        ['--disable=import-error'])
    self.assertFalse(hasattr(args, 'disable'))
    self.assertSequenceEqual(pytype_single_args.disable, ['import-error'])

  def test_conflict(self):
    # Both pytype-all and pytype-single take a python version; the former
    # should take precedence.
    args, pytype_single_args = parse_args.parse_or_die(['--python-version=2.7'])
    self.assertEqual(args.python_version, '2.7')
    self.assertFalse(hasattr(pytype_single_args, 'python_version'))


if __name__ == '__main__':
  unittest.main()
