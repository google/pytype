"""Implementation of types from Python 2's collections library."""

from pytype.overlays import named_tuple
from pytype.overlays import overlay
from pytype.overlays import typing_overlay


class CollectionsOverlay(overlay.Overlay):
  """A custom overlay for the 'collections' module."""

  def __init__(self, ctx):
    """Initializes the CollectionsOverlay.

    This function loads the AST for the collections module, which is used to
    access type information for any members that are not explicitly provided by
    the overlay. See get_attribute in attribute.py for how it's used.

    Args:
      ctx: An instance of context.Context.
    """
    # collections_overlay contains all the members that have special definitions
    member_map = collections_overlay.copy()
    ast = ctx.loader.import_name("collections")
    super().__init__(ctx, "collections", member_map, ast)


collections_overlay = {
    "namedtuple": overlay.build(
        "namedtuple", named_tuple.NamedTupleBuilder.make),
}


class ABCOverlay(typing_overlay.Redirect):
  """A custom overlay for the 'collections.abc' module."""

  def __init__(self, ctx):
    super().__init__("collections.abc", {"Set": "typing.AbstractSet"}, ctx)
