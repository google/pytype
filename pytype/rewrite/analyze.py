"""Check and infer types."""

import dataclasses
from typing import Optional

from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype.pytd import pytd


# How deep to follow call chains:
_INIT_MAXIMUM_DEPTH = 4  # during module loading
_MAXIMUM_DEPTH = 3  # during analysis of function bodies


class Context:
  """Analysis context."""

  def __init__(self):
    # TODO(b/241479600): This is a placeholder to make everything compile and
    # run for now, but we'll need to write a new version of errors.py.
    self.errorlog = errors.ErrorLog()


@dataclasses.dataclass
class Analysis:
  """Analysis results."""

  context: Context
  ast: Optional[pytd.TypeDeclUnit]
  ast_deps: Optional[pytd.TypeDeclUnit]


def check_types(
    src: str,
    options: config.Options,
    loader: load_pytd.Loader,
    init_maximum_depth: int = _INIT_MAXIMUM_DEPTH,
    maximum_depth: int = _MAXIMUM_DEPTH,
) -> Analysis:
  """Check types for the given source code."""
  del src, options, loader, init_maximum_depth, maximum_depth
  return Analysis(Context(), None, None)


def infer_types(
    src: str,
    options: config.Options,
    loader: load_pytd.Loader,
    init_maximum_depth: int = _INIT_MAXIMUM_DEPTH,
    maximum_depth: int = _MAXIMUM_DEPTH,
) -> Analysis:
  """Infer types for the given source code."""
  del src, options, loader, init_maximum_depth, maximum_depth
  ast = pytd.TypeDeclUnit("inferred + unknowns", (), (), (), (), ())
  deps = pytd.TypeDeclUnit("<all>", (), (), (), (), ())
  return Analysis(Context(), ast, deps)
