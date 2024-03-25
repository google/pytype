"""Check and infer types."""

import dataclasses
import logging
from typing import Optional

from pytype import config
from pytype import load_pytd
from pytype.errors import errors
from pytype.pytd import pytd
from pytype.rewrite import vm as vm_lib

# How deep to follow call chains:
_INIT_MAXIMUM_DEPTH = 4  # during module loading
_MAXIMUM_DEPTH = 3  # during analysis of function bodies

log = logging.getLogger(__name__)


class Context:
  """Analysis context."""

  def __init__(self, errorlog: errors.ErrorLog):
    self.errorlog = errorlog


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
  """Checks types for the given source code."""
  del loader, init_maximum_depth, maximum_depth
  vm = vm_lib.VirtualMachine.from_source(src, options)
  errorlog = vm.analyze_all_defs()
  return Analysis(Context(errorlog), None, None)


def infer_types(
    src: str,
    options: config.Options,
    loader: load_pytd.Loader,
    init_maximum_depth: int = _INIT_MAXIMUM_DEPTH,
    maximum_depth: int = _MAXIMUM_DEPTH,
) -> Analysis:
  """Infers types for the given source code."""
  del init_maximum_depth, maximum_depth
  vm = vm_lib.VirtualMachine.from_source(src, options)
  errorlog, ast = vm.infer_stub()
  deps = loader.concat_all()
  return Analysis(Context(errorlog), ast, deps)
