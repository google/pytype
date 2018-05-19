"""Tests for utils.py."""

import os
import unittest

from pytype import utils as pytype_utils
from pytype.tools import utils


class TestFileToModule(unittest.TestCase):
  """Tests for utils.filename_to_module_name."""

  def test_pardir(self):
    self.assertIsNone(utils.filename_to_module_name('../foo.py'))

  def test_file(self):
    self.assertEqual(utils.filename_to_module_name('foo/bar/baz.py'),
                     'foo.bar.baz')


class TestSetupLoggingOrDie(unittest.TestCase):
  """Tests for utils.setup_logging_or_die."""

  def test_negative_verbosity(self):
    with self.assertRaises(SystemExit):
      utils.setup_logging_or_die(-1)

  def test_excessive_verbosity(self):
    with self.assertRaises(SystemExit):
      utils.setup_logging_or_die(3)

  def test_set_level(self):
    # Log level can't actually be set in a test, so we're just testing that the
    # code doesn't blow up.
    utils.setup_logging_or_die(0)
    utils.setup_logging_or_die(1)
    utils.setup_logging_or_die(2)


class TestPathExpansion(unittest.TestCase):
  """Tests for utils.expand_path(s?)."""

  def test_expand_one_path(self):
    full_path = os.path.join(os.getcwd(), 'foo.py')
    self.assertEqual(utils.expand_path('foo.py'), full_path)

  def test_expand_two_paths(self):
    full_path1 = os.path.join(os.getcwd(), 'foo.py')
    full_path2 = os.path.join(os.getcwd(), 'bar.py')
    self.assertEqual(utils.expand_paths(['foo.py', 'bar.py']),
                     [full_path1, full_path2])

  def test_expand_with_cwd(self):
    with pytype_utils.Tempdir() as d:
      f = d.create_file('foo.py')
      self.assertEqual(utils.expand_path('foo.py', d.path), f)


class TestSplitVersion(unittest.TestCase):
  """Tests for utils.split_version()."""

  def test_split(self):
    self.assertEqual(utils.split_version('2.7'), (2, 7))


class TestMakeDirsOrDie(unittest.TestCase):
  """Tests for utils.makedirs_or_die()."""

  def test_make(self):
    with pytype_utils.Tempdir() as d:
      subdir = os.path.join(d.path, 'some/path')
      utils.makedirs_or_die(subdir, '')
      self.assertTrue(os.path.isdir(subdir))

  def test_die(self):
    with self.assertRaises(SystemExit):
      utils.makedirs_or_die('/nonexistent/path', '')


if __name__ == '__main__':
  unittest.main()
