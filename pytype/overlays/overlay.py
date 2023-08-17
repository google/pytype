"""Base class for module overlays."""

from typing import Any, Callable, Dict, Optional

from pytype import datatypes
from pytype.abstract import abstract
from pytype.typegraph import cfg

# The first argument type is pytype.context.Context, but we can't import context
# here due to a circular dependency.
BuilderType = Callable[[Any, str], abstract.BaseValue]


class Overlay(abstract.Module):
  """A layer between pytype and a module's pytd definition.

  An overlay pretends to be a module, but provides members that generate extra
  typing information that cannot be expressed in a pytd file. For example,
  collections.namedtuple is a factory method that generates class definitions
  at runtime. An overlay is needed for Pytype to generate these classes.

  An Overlay will typically import its underlying module in its __init__, e.g.
  by calling ctx.loader.import_name(). Due to this, Overlays should only be used
  when their underlying module is imported by the Python script being analyzed!
  A subclass of Overlay should have an __init__ with the signature:
    def __init__(self, ctx)

  Attributes:
    real_module: An abstract.Module wrapping the AST for the underlying module.
  """

  def __init__(self, ctx, name, member_map, ast):
    """Initialize the overlay.

    Args:
      ctx: Instance of context.Context.
      name: A string containing the name of the underlying module.
      member_map: Dict of str to abstract.BaseValues that provide type
        information not available in the underlying module.
      ast: An pytd.TypeDeclUnit containing the AST for the underlying module.
        Used to access type information for members of the module that are not
        explicitly provided by the overlay.
    """
    super().__init__(ctx, name, member_map, ast)
    self.real_module = ctx.convert.constant_to_value(
        ast, subst=datatypes.AliasingDict(), node=ctx.root_node)

  def _convert_member(
      self, name: str, member: BuilderType,
      subst: Optional[Dict[str, cfg.Variable]] = None) -> cfg.Variable:
    val = member(self.ctx, self.name)
    val.module = self.name
    return val.to_variable(self.ctx.root_node)

  def get_module(self, name):
    """Returns the abstract.Module for the given name."""
    if name in self._member_map:
      return self
    else:
      return self.real_module

  def items(self):
    items = super().items()
    items += [(name, item) for name, item in self.real_module.items()
              if name not in self._member_map]
    return items


def add_name(name, builder):
  """Turns (name, ctx, module) -> val signatures into (ctx, module) -> val."""
  return lambda ctx, module: builder(name, ctx, module)


def drop_module(builder):
  """Turns (ctx) -> val signatures into (ctx, module) -> val."""
  return lambda ctx, module: builder(ctx)
