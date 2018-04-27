"""Config file processing."""

from __future__ import print_function

import collections
import imp
import os
import sys
import textwrap

from . import utils

Item = collections.namedtuple('Item', ['key', 'default', 'sample', 'comment'])

# Generates both the default config and the sample config file.
SAMPLE = [
    Item('python_version', '3.6', '3.6',
         'Python version ("major.minor") of the target code.'),
    Item('output_dir', 'pytype_output', 'pytype_output',
         'All pytype output goes here.'),
    Item('projects', [], ['/path/to/project'],
         'Dependencies within these directories will be checked for type '
         'errors.'),
    Item('deps', [], ['/path/to/project'],
         'Dependencies within these directories will have type inference '
         'run on them, but will not be checked for errors.'),
]

DEFAULT = {item.key: item.default for item in SAMPLE}


class Config(object):
  """Configuration variables."""

  __slots__ = 'projects', 'deps', 'output_dir', 'python_version'

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

  def read_from_file(self, path):
    """Read config from a file."""

    path = utils.expand_path(path)
    mod = imp.load_source('config_file', path)
    consts = {k: v for k, v in mod.__dict__.items() if not k.startswith('__')}
    self._validate_keys(consts)
    for k in DEFAULT:
      setattr(self, k, consts.get(k, DEFAULT[k]))
    cwd = os.path.dirname(path)
    self.projects = utils.expand_paths(self.projects, cwd)
    self.deps = utils.expand_paths(self.deps, cwd)
    self.output_dir = utils.expand_path(self.output_dir, cwd)

  def make_pythonpath(self):
    return ':'.join(self.projects + self.deps)

  def show(self):
    for k in DEFAULT:
      print('%s = %r' % (k, getattr(self, k)))


def _format_sample_item(k, v):
  out = []
  if isinstance(v, list):
    out.append('%s = [' % k)
    for entry in v:
      out.append('    %r,' % entry)
    out.append(']')
  else:
    out.append('%s = %r' % (k, v))
  return out


def generate_sample_config(filename):
  """Write out a sample config file."""

  if os.path.exists(filename):
    print('Not overwriting existing file: %s' % filename)
    sys.exit(0)

  config = [
      '# NOTE: All relative paths are relative to the location of this file.',
      ''
  ]
  for item in SAMPLE:
    config.extend(textwrap.wrap('# ' + item.comment, 80))
    config.extend(_format_sample_item(item.key, item.sample))
    config.append('')
  with open(filename, 'w') as f:
    f.write('\n'.join(config))
