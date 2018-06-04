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
        '3.6', '3.6', 'Python version (major.minor) of the target code.'),
    'output': Item(
        'pytype_output', 'pytype_output', 'All pytype output goes here.'),
    'pythonpath': Item(
        '', '/path/to/project:/path/to/project',
        'Paths to source code directories, separated by %r.' % os.pathsep)
}


def make_converters(cwd=None):
  """For items that need coaxing into their internal representations."""
  return {
      'output': lambda v: file_utils.expand_path(v, cwd),
      'pythonpath': lambda v: file_utils.expand_pythonpath(v, cwd)
  }


def get_formatters():
  """For items that need special print formatting."""
  def format_pythonpath(p):
    out = []
    out.append('pythonpath =')
    # Breaks the pythonpath after each ':'.
    for entry in p.replace(os.pathsep, os.pathsep + '\n').split('\n'):
      out.append('    %s' % entry)
    return out
  return {'pythonpath': format_pythonpath}


def Config(*extra_variables):  # pylint: disable=invalid-name
  """Builds a Config class and returns an instance of it."""

  class Config(object):  # pylint: disable=redefined-outer-name
    """Configuration variables.

    A lightweight configuration class that reads in attributes from other
    objects and prettyprints itself. The intention is for each source of
    attributes (e.g., FileConfig) to do its own processing, then for Config to
    copy in the final results in the right order.
    """

    __slots__ = ('pythonpath', 'output', 'python_version') + extra_variables

    def populate_from(self, obj):
      """Populate self from another object's attributes."""
      for k in self.__slots__:
        if hasattr(obj, k):
          setattr(self, k, getattr(obj, k))

    def __str__(self):
      return '\n'.join(
          '%s = %r' % (k, getattr(self, k, None)) for k in self.__slots__)

  return Config()


class FileConfig(object):
  """Configuration variables from a file."""

  def read_from_file(self, filepath):
    """Read config from an INI-style file with a [pytype] section."""

    cfg = config.ConfigSection.create_from_file(filepath, 'pytype')
    if not cfg:
      return None
    converters = make_converters(cwd=os.path.dirname(filepath))
    for k, v in cfg.items():
      if k in converters:
        v = converters[k](v)
      setattr(self, k, v)
    return filepath


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
  formatters = get_formatters()
  # TODO(rechen): Add the pytype-single arguments.
  for key, item in ITEMS.items():
    conf.extend(textwrap.wrap(
        item.comment, 80, initial_indent='# ', subsequent_indent='# '))
    if key in formatters:
      conf.extend(formatters[key](item.sample))
    else:
      conf.append('%s = %s' % (key, item.sample))
    conf.append('')
  try:
    with open(filename, 'w') as f:
      f.write('\n'.join(conf))
  except IOError as e:
    logging.critical('Cannot write to %s:\n%s', filename, str(e))
    sys.exit(1)


def read_config_file_or_die(filepath):
  """Read config from filepath or from setup.cfg."""

  ret = FileConfig()
  if filepath:
    if not ret.read_from_file(filepath):
      logging.critical('Could not read config file: %s\n'
                       '  Generate a sample configuration via:\n'
                       '  pytype --generate-config sample.cfg', filepath)
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
