"""Utilities for dealing with project configuration."""

import collections
import os
from six.moves import configparser


Item = collections.namedtuple('Item', ['key', 'default', 'sample', 'comment'])


def find_config_file(path, filename='setup.cfg'):
  """Finds the first instance of filename in a prefix of path."""

  # Make sure path is a directory
  if not os.path.isdir(path):
    path = os.path.dirname(path)

  # Guard against symlink loops and /
  seen = set()
  while path and path not in seen:
    seen.add(path)
    f = os.path.join(path, filename)
    if os.path.exists(f) and os.path.isfile(f):
      return f
    path = os.path.dirname(path)

  return None


def get_list(string):
  """Split a list of lines, optionally removing terminal commas."""
  xs = string.strip().split('\n')
  xs = [x.strip().rstrip(', \t') for x in xs]
  return xs


class ConfigSection(object):
  """Read a given set of keys from a section of a config file."""

  def __init__(self, parser, section, keymap):
    self.parser = parser
    self.section = section
    self.keymap = keymap

  @classmethod
  def create_from_file(cls, filepath, section, keymap):
    """Create a ConfigSection if the file at filepath has section."""
    parser = configparser.ConfigParser()
    try:
      parser.read(filepath)
    except configparser.MissingSectionHeaderError:
      # We've read an improperly formatted config file.
      return None
    if parser.has_section(section):
      return cls(parser, section, keymap)
    return None

  def get(self, key):
    """Get the value for the given key."""
    try:
      # The 'fallback' option is Python 3-only, so we use a try/except.
      value = self.parser.get(self.section, key)
    except configparser.NoOptionError:
      value = None
    if not value:
      return None
    converter = self.keymap[key]
    if converter:
      value = converter(value)
    return value

  def populate_object(self, obj):
    """Populate an object that sets keys via setattr."""
    for k in self.keymap:
      value = self.get(k)
      if value:
        setattr(obj, k, value)
    return obj

  def to_hash(self):
    """Return the section as a hash."""
    return {k: self.get(k) for k in self.keymap}
