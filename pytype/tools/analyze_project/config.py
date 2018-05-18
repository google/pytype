"""Config file processing."""

from __future__ import print_function

import os
import sys
import textwrap

from pytype.tools import config
from pytype.tools import utils


# Convenience alias
Item = config.Item  # pylint: disable=invalid-name


# Generates both the default config and the sample config file.
SAMPLE = [
    Item('python_version', '3.6', '3.6',
         'Python version (major.minor) of the target code.'),
    Item('output_dir', 'pytype_output', 'pytype_output',
         'All pytype output goes here.'),
    Item('pythonpath', [], ['/path/to/project', '/path/to/project'],
         'Paths to source code directories.')
]

DEFAULT = {item.key: item.default for item in SAMPLE}


class Config(object):
  """Configuration variables."""

  __slots__ = 'pythonpath', 'output_dir', 'python_version'

  def __init__(self):
    for k, v in DEFAULT.items():
      setattr(self, k, v)

  def _validate_keys(self, consts):
    """Check keys against default config."""

    valid = set(DEFAULT)
    invalid = set(consts) - valid
    if invalid:
      err = """
          Invalid config variables: {}
          Valid options are: {}

          To generate a complete sample config file, run:
            pytype-all --generate-config sample.cfg
      """.format(', '.join(invalid), ', '.join(valid))
      print(textwrap.dedent(err))
      sys.exit(0)

  def read_from_setup_cfg(self, starting_path):
    """Read config from the first setup.cfg file found upwards from path.

    Arguments:
      starting_path: The path to start searching from (typically cwd).

    Returns:
      A path to the config file if one was read successfully, otherwise None.
    """

    filepath = config.find_config_file(starting_path)
    if not filepath:
      return None
    return self.read_from_file(filepath)

  def read_from_file(self, filepath):
    """Read config from an INI-style file with a [pytype] section."""

    keymap = {}
    for k, v in DEFAULT.items():
      if isinstance(v, list):
        keymap[k] = config.get_list
      else:
        keymap[k] = None
    cfg = config.ConfigSection.create_from_file(filepath, 'pytype', keymap)
    if not cfg:
      return None
    cfg.populate_object(self)
    self.expand_paths(filepath)
    return filepath

  def expand_paths(self, base_path):
    cwd = os.path.dirname(base_path)
    self.pythonpath = utils.expand_paths(self.pythonpath, cwd)
    self.output_dir = utils.expand_path(self.output_dir, cwd)

  def show(self):
    for k in DEFAULT:
      print('%s = %r' % (k, getattr(self, k)))


def _format_sample_item(k, v):
  out = []
  if isinstance(v, list):
    out.append('%s =' % k)
    for entry in v:
      out.append('    %s,' % entry)
  else:
    out.append('%s = %s' % (k, v))
  return out


def generate_sample_config(filename):
  """Write out a sample config file."""

  if os.path.exists(filename):
    print('Not overwriting existing file: %s' % filename)
    sys.exit(0)

  # Not using configparser's write method because it doesn't support comments.

  conf = [
      '# NOTE: All relative paths are relative to the location of this file.',
      '',
      '[pytype]'
  ]
  for item in SAMPLE:
    conf.extend(textwrap.wrap(
        item.comment, 80, initial_indent='# ', subsequent_indent='# '))
    conf.extend(_format_sample_item(item.key, item.sample))
    conf.append('')
  with open(filename, 'w') as f:
    f.write('\n'.join(conf))
