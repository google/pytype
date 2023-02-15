"""Overlay for functools."""

from pytype.overlays import overlay
from pytype.overlays import special_builtins


class FunctoolsOverlay(overlay.Overlay):
  """An overlay for the functools std lib module."""

  MODULE_NAME = "functools"

  def __init__(self, ctx):
    member_map = {
        "cached_property": special_builtins.Property
    }
    ast = ctx.loader.import_name(self.MODULE_NAME)
    super().__init__(ctx, self.MODULE_NAME, member_map, ast)
