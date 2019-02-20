"""Argument parsing for tools that pass args on to pytype_single."""

import argparse

from pytype import config as pytype_config


class ParserWrapper(object):
  """Wrapper that adds arguments to a parser while recording them."""

  def __init__(self, parser, actions=None):
    self.parser = parser
    self.actions = {} if actions is None else actions

  def add_argument(self, *args, **kwargs):
    try:
      action = self.parser.add_argument(*args, **kwargs)
    except argparse.ArgumentError:
      # We might want to mask some pytype-single options.
      pass
    else:
      self.actions[action.dest] = action

  def add_argument_group(self, *args, **kwargs):
    group = self.parser.add_argument_group(*args, **kwargs)
    wrapped_group = self.__class__(group, actions=self.actions)
    return wrapped_group


def string_to_bool(s):
  return s == 'True' if s in ('True', 'False') else s


def convert_string(s):
  s = s.replace('\n', '')
  try:
    return int(s)
  except ValueError:
    return string_to_bool(s)


class Parser(object):
  """Parser that integrates tool and pytype-single args."""

  def __init__(self, parser, pytype_single_args):
    """Initialize a parser.

    Args:
      parser: An argparse.ArgumentParser or compatible object
      pytype_single_args: Iterable of args that will be passed to pytype_single
    """
    self.parser = parser
    self.pytype_single_args = pytype_single_args

  def create_initial_args(self, keys):
    """Creates the initial set of args.

    Args:
      keys: A list of keys to create args from

    Returns:
      An argparse.Namespace.
    """
    return argparse.Namespace(**{k: None for k in keys})

  def parse_args(self, argv):
    """Parses argv.

    Args:
      argv: sys.argv[1:]

    Returns:
      An argparse.Namespace.
    """
    args = self.create_initial_args(self.pytype_single_args)
    self.parser.parse_args(argv, args)
    self.postprocess(args)
    return args

  def postprocess(self, args, from_strings=False):
    """Postprocesses the subset of pytype_single_args that appear in args.

    Args:
      args: an argparse.Namespace.
      from_strings: Whether the args are all strings. If so, we'll do our best
        to convert them to the right types.
    """
    names = set()
    for k in self.pytype_single_args:
      if hasattr(args, k):
        names.add(k)
        if from_strings:
          setattr(args, k, convert_string(getattr(args, k)))
    pytype_config.Postprocessor(names, args).process()

  def get_pytype_kwargs(self, args):
    """Return a set of kwargs to pass to pytype.config.Options.

    Args:
      args: an argparse.Namespace.

    Returns:
      A dict of kwargs with pytype_single args as keys.
    """
    return {k: getattr(args, k) for k in self.pytype_single_args}
