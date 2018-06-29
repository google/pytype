"""Tests for config.py."""

import os

from pytype import datatypes
from pytype import file_utils
from pytype.tools.analyze_project import config
import unittest


PYTYPE_CFG = """
  [pytype]
  python_version = 2.7
  pythonpath =
    .:
    /foo/bar:
    baz/quux
"""

RANDOM_CFG = """
  [some_section]
  foo = bar
  baz = quux
"""

SETUP_CFG = RANDOM_CFG + '\n' + PYTYPE_CFG


class TestBase(unittest.TestCase):
  """Base for config tests."""

  def _validate_file_contents(self, conf, path):
    self.assertEqual(conf.python_version, u'2.7')
    self.assertEqual(conf.pythonpath, [
        path,
        u'/foo/bar',
        os.path.join(path, u'baz/quux')
    ])
    # output shouldn't be present since we haven't set it.
    self.assertFalse(hasattr(conf, 'output'))

  def _validate_empty_contents(self, conf):
    for k in config.ITEMS:
      self.assertFalse(hasattr(conf, k))


class TestFileConfig(TestBase):
  """Test FileConfig."""

  def test_config_file(self):
    with file_utils.Tempdir() as d:
      f = d.create_file('test.cfg', PYTYPE_CFG)
      conf = config.FileConfig()
      path = conf.read_from_file(f)
      self.assertEqual(path, f)
      self._validate_file_contents(conf, d.path)

  def test_missing_config_file_section(self):
    with file_utils.Tempdir() as d:
      f = d.create_file('test.cfg', RANDOM_CFG)
      conf = config.FileConfig()
      path = conf.read_from_file(f)
      self.assertEqual(path, None)
      self._validate_empty_contents(conf)

  def test_read_nonexistent(self):
    conf = config.FileConfig()
    self.assertIsNone(conf.read_from_file('/does/not/exist/test.cfg'))
    self._validate_empty_contents(conf)

  def test_read_bad_format(self):
    conf = config.FileConfig()
    with file_utils.Tempdir() as d:
      f = d.create_file('test.cfg', 'ladadeda := squirrels')
      self.assertIsNone(conf.read_from_file(f))
    self._validate_empty_contents(conf)


class TestConfig(TestBase):
  """Test Config."""

  def test_populate_from(self):
    conf = config.Config()
    self._validate_empty_contents(conf)
    conf.populate_from(
        datatypes.SimpleNamespace(**{k: 42 for k in config.ITEMS}))
    for k in config.ITEMS:
      self.assertEqual(getattr(conf, k), 42)

  def test_populate_from_none(self):
    conf = config.Config()
    self._validate_empty_contents(conf)
    # None is a valid value.
    conf.populate_from(
        datatypes.SimpleNamespace(**{k: None for k in config.ITEMS}))
    for k in config.ITEMS:
      self.assertIsNone(getattr(conf, k))

  def test_populate_from_empty(self):
    conf = config.Config()
    conf.populate_from(object())
    self._validate_empty_contents(conf)

  def test_str(self):
    str(config.Config())  # smoke test


class TestGenerateConfig(unittest.TestCase):
  """Test config.generate_sample_config_or_die."""

  def test_bad_location(self):
    with self.assertRaises(SystemExit):
      config.generate_sample_config_or_die('/does/not/exist/sample.cfg')

  def test_existing_file(self):
    with file_utils.Tempdir() as d:
      f = d.create_file('sample.cfg')
      with self.assertRaises(SystemExit):
        config.generate_sample_config_or_die(f)

  def test_generate(self):
    conf = config.FileConfig()
    with file_utils.Tempdir() as d:
      f = os.path.join(d.path, 'sample.cfg')
      config.generate_sample_config_or_die(f)
      # Test that we've generated a valid config and spot-check pythonpath.
      conf.read_from_file(f)
      self.assertEqual(
          conf.pythonpath, config.ITEMS['pythonpath'].sample.split(os.pathsep))


class TestReadConfig(TestBase):
  """Test config.read_config_file_or_die()."""

  def test_config_file(self):
    with file_utils.Tempdir() as d:
      f = d.create_file('test.cfg', PYTYPE_CFG)
      conf = config.read_config_file_or_die(f)
      self._validate_file_contents(conf, d.path)

  def test_missing_config_file_section(self):
    with file_utils.Tempdir() as d:
      f = d.create_file('test.cfg', RANDOM_CFG)
      with self.assertRaises(SystemExit):
        config.read_config_file_or_die(f)

  def test_setup_cfg(self):
    with file_utils.Tempdir() as d:
      d.create_file('setup.cfg', SETUP_CFG)
      with file_utils.cd(d.path):
        conf = config.read_config_file_or_die(None)
        self._validate_file_contents(conf, d.path)

  def test_setup_cfg_from_subdir(self):
    with file_utils.Tempdir() as d:
      d.create_file('setup.cfg', SETUP_CFG)
      sub = d.create_directory('x/y/z')
      conf = config.Config()
      with file_utils.cd(sub):
        conf = config.read_config_file_or_die(None)
        self._validate_file_contents(conf, d.path)

  def test_missing_setup_cfg_section(self):
    with file_utils.Tempdir() as d:
      d.create_file('setup.cfg', RANDOM_CFG)
      with file_utils.cd(d.path):
        conf = config.read_config_file_or_die(None)
        self._validate_empty_contents(conf)


if __name__ == '__main__':
  unittest.main()
