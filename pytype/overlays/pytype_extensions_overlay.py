"""Implementation of special members of pytype_extensions."""

from pytype import special_builtins
from pytype.overlays import overlay


class PytypeExtensionsOverlay(overlay.Overlay):
  """A custom overlay for the 'pytype_extensions' module."""

  def __init__(self, ctx):
    member_map = {
        "assert_type": build_assert_type
    }
    ast = ctx.loader.import_name("pytype_extensions")
    super().__init__(ctx, "pytype_extensions", member_map, ast)


def build_assert_type(ctx):
  return special_builtins.AssertType.make_alias("assert_type", ctx,
                                                "pytype_extensions")
