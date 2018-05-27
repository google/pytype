"""Config file processing."""

from __future__ import print_function

import collections
import logging
import os
import sys
import textwrap

from pytype import file_utils
from pytype.tools import config


# A config item.
# Args:
#   default: the default value.
#   sample: a sample value.
#   comment: help text.
Item = collections.namedtuple('Item', ['default', 'sample', 'comment'])


# Generates both the default config and the sample config file.
ITEMS = {
    'python_version': Item(
        '3.6', '3.6',
        'Python version (major.minor) of the target code.'),
    'output_dir': Item(
        'pytype_output', 'pytype_output',
        'All pytype output goes here.'),
    'pythonpath': Item(
        [], ['/path/to/project', '/path/to/project'],
        'Paths to source code directories.')
}


class Config(object):
  """Configuration variables."""

  __slots__ = 'pythonpath', 'output_dir', 'python_version'

  def __init__(self):
    for k, v in ITEMS.items():
      setattr(self, k, v.default)

  def read_from_file(self, filepath):
    """Read config from an INI-style file with a [pytype] section."""

    keymap = {}
    for k, v in ITEMS.items():
      if isinstance(v.default, list):
        keymap[k] = config.get_list
      else:
        keymap[k] = None
    cfg = config.ConfigSection.create_from_file(filepath, 'pytype', keymap)
    if not cfg:
      return None
    self.populate_from(cfg)
    self.expand_paths(filepath)
    return filepath

  def expand_paths(self, base_path):
    cwd = os.path.dirname(base_path)
    self.pythonpath = file_utils.expand_paths(self.pythonpath, cwd)
    self.output_dir = file_utils.expand_path(self.output_dir, cwd)

  def populate_from(self, obj):
    """Populate self from an object with a dict-like get method."""
    for k in ITEMS:
      value = obj.get(k)
      if value is not None:
        setattr(self, k, value)

  def __str__(self):
    return '\n'.join('%s = %r' % (k, getattr(self, k)) for k in ITEMS)


def _format_sample_item(k, v):
  out = []
  if isinstance(v, list):
    out.append('%s =' % k)
    for entry in v:
      out.append('    %s,' % entry)
  else:
    out.append('%s = %s' % (k, v))
  return out


def generate_sample_config_or_die(filename):
  """Write out a sample config file."""

  if os.path.exists(filename):
    logging.critical('Not overwriting existing file: %s', filename)
    sys.exit(1)

  # Not using configparser's write method because it doesn't support comments.

  conf = [
      '# NOTE: All relative paths are relative to the location of this file.',
      '',
      '[pytype]'
  ]
  for key, item in ITEMS.items():
    conf.extend(textwrap.wrap(
        item.comment, 80, initial_indent='# ', subsequent_indent='# '))
    conf.extend(_format_sample_item(key, item.sample))
    conf.append('')
  try:
    with open(filename, 'w') as f:
      f.write('\n'.join(conf))
  except IOError as e:
    logging.critical('Cannot write to %s:\n%s', filename, str(e))
    sys.exit(1)


def read_config_file_or_die(filepath):
  """Read config from filepath or from setup.cfg."""

  ret = Config()
  if filepath:
    if not ret.read_from_file(filepath):
      logging.critical('Could not read config file: %s\n'
                       '  Generate a sample configuration via:\n'
                       '  pytype-all --generate-config sample.cfg', filepath)
      sys.exit(1)
  else:
    # Try reading from setup.cfg.
    filepath = config.find_config_file(os.getcwd())
    if filepath and ret.read_from_file(filepath):
      logging.info('Reading config from: %s', filepath)
    else:
      logging.info('No config file specified, and no [pytype] section in '
                   'setup.cfg. Using default configuration.')
  return ret
