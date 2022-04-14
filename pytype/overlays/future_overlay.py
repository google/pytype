"""Implementation of special members of the future library."""

from pytype import metaclass
from pytype.overlays import overlay


class FutureUtilsOverlay(overlay.Overlay):
  """A custom overlay for the 'future' module."""

  def __init__(self, ctx):
    member_map = {
        "with_metaclass": build_with_metaclass,
    }
    ast = ctx.loader.import_name("future.utils")
    super().__init__(ctx, "future.utils", member_map, ast)


def build_with_metaclass(ctx):
  return metaclass.WithMetaclass.make("with_metaclass", ctx, "future.utils")
