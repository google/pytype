"""Conversion from pytd to abstract representations of Python values."""

from typing import Dict, Tuple

from pytype.rewrite.abstract import abstract
from pytype.rewrite.flow import variables


def get_module_globals(
    python_version: Tuple[int, int],
) -> Dict[str, variables.Variable[abstract.BaseValue]]:
  del python_version  # not yet used
  # TODO(b/241479600): Populate from builtins.pytd.
  return {
      '__name__': abstract.ANY.to_variable(),
  }
