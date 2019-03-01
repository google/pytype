"""Utilities for xref."""

import os


def get_module_filepath(module):
  """Recover the path to the py file from a module pyi path."""

  def _clean(path):
    """Change extension to .py."""
    prefix, fname = os.path.split(path)
    fname, _ = os.path.splitext(fname)
    path = os.path.join(prefix, fname + ".py")
    return path

  return _clean(module.filename)
