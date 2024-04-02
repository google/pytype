"""Loads abstract representations of imported objects."""

from typing import Any, Dict, Type

from pytype import load_pytd
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins


class AbstractLoader:
  """Abstract loader."""

  def __init__(self, ctx: abstract.ContextType, pytd_loader: load_pytd.Loader):
    self._ctx = ctx
    self._pytd_loader = pytd_loader

  def get_module_globals(self) -> Dict[str, abstract.BaseValue]:
    """Gets a module's initial global namespace, including builtins."""
    # TODO(b/324464265): Populate from builtins.pytd.
    return {
        '__name__': self._ctx.singles.Any,
        'assert_type': special_builtins.AssertType(self._ctx),
        'int': abstract.SimpleClass(
            self._ctx, name='int', module='builtins', members={}),
    }

  def raw_type_to_value(self, typ: Type[Any]) -> abstract.BaseValue:
    """Converts a raw type to an abstract value.

    Args:
      typ: The type.

    Returns:
      The abstract representation of the type. For example, when passed `int`,
      this function returns `abstract.SimpleClass(int)`.
    """
    return abstract.SimpleClass(self._ctx, typ.__name__, {}, typ.__module__)
