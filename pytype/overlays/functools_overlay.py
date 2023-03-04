"""Overlay for functools."""

from pytype.overlays import overlay
from pytype.overlays import special_builtins

_MODULE_NAME = "functools"


class FunctoolsOverlay(overlay.Overlay):
  """An overlay for the functools std lib module."""

  def __init__(self, ctx):
    member_map = {
        "cached_property": CachedProperty,
    }
    ast = ctx.loader.import_name(_MODULE_NAME)
    super().__init__(ctx, _MODULE_NAME, member_map, ast)


class CachedProperty(special_builtins.PropertyTemplate):

  def __init__(self, ctx):
    super().__init__(ctx, "cached_property", _MODULE_NAME)
