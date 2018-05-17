"""Tests for config.py."""

import os
import unittest

from pytype import utils
from pytype.tools.analyze_project import config


PYTYPE_CFG = """
  [pytype]
  python_version = 2.7
  deps =
    /foo/bar
    baz/quux
  projects =
    .
    /a/b/c
"""

RANDOM_CFG = """
  [some_section]
  foo = bar
  baz = quux
"""

SETUP_CFG = RANDOM_CFG + '\n' + PYTYPE_CFG


class TestConfig(unittest.TestCase):
  """Test Config"""

  def _validate_file_contents(self, conf, path):
    self.assertEqual(conf.python_version, u'2.7')
    self.assertEqual(conf.projects, [path, u'/a/b/c'])
    self.assertEqual(conf.deps, [
        u'/foo/bar',
        os.path.join(path, u'baz/quux')
    ])
    # This should be picked up from defaults since we haven't set it
    self.assertEqual(conf.output_dir, os.path.join(path, 'pytype_output'))

  def test_config_file(self):
    with utils.Tempdir() as d:
      f = d.create_file('test.cfg', PYTYPE_CFG)
      conf = config.Config()
      path = conf.read_from_file(f)
      self.assertEqual(path, f)
      self._validate_file_contents(conf, d.path)

  def test_setup_cfg(self):
    with utils.Tempdir() as d:
      f = d.create_file('setup.cfg', SETUP_CFG)
      conf = config.Config()
      path = conf.read_from_setup_cfg(d.path)
      self.assertEqual(path, f)
      self._validate_file_contents(conf, d.path)

  def test_setup_cfg_from_subdir(self):
    with utils.Tempdir() as d:
      f = d.create_file('setup.cfg', SETUP_CFG)
      sub = d.create_directory('x/y/z')
      conf = config.Config()
      path = conf.read_from_setup_cfg(sub)
      self.assertEqual(path, f)
      self._validate_file_contents(conf, d.path)

  def test_missing_setup_cfg_section(self):
    with utils.Tempdir() as d:
      d.create_file('setup.cfg', RANDOM_CFG)
      conf = config.Config()
      path = conf.read_from_setup_cfg(d.path)
      self.assertEqual(path, None)
      self.assertEqual(conf.python_version, u'3.6')

  def test_missing_config_file_section(self):
    with utils.Tempdir() as d:
      f = d.create_file('test.cfg', RANDOM_CFG)
      conf = config.Config()
      path = conf.read_from_file(f)
      self.assertEqual(path, None)
      self.assertEqual(conf.python_version, u'3.6')

if __name__ == '__main__':
  unittest.main()
