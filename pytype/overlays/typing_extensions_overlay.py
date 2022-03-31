"""Implementation of special members of typing_extensions."""
from pytype import overlay
from pytype.overlays import typing_overlay


class TypingExtensionsOverlay(overlay.Overlay):
  """A custom overlay for the 'typing_extensions' module."""

  def __init__(self, ctx):
    ast = ctx.loader.import_name("typing_extensions")
    member_map = {
        "runtime": _build("typing.runtime_checkable"),
    }
    for pyval in ast.aliases + ast.classes + ast.constants + ast.functions:
      # Any public typing_extensions members that are not explicitly implemented
      # are unsupported.
      _, name = pyval.name.rsplit(".", 1)
      if name.startswith("_"):
        continue
      if name in typing_overlay.typing_overlay:
        member_map[name] = typing_overlay.typing_overlay[name][0]
      elif f"typing.{name}" in ctx.loader.typing:
        member_map[name] = _build(f"typing.{name}")
      elif name not in member_map:
        member_map[name] = _build_not_supported_yet(name, ast)
    super().__init__(ctx, "typing_extensions", member_map, ast)

  def _convert_member(self, name, member, subst=None):
    var = super()._convert_member(name, member, subst)
    for val in var.data:
      # typing_extensions backports typing features to older versions.
      # Pretending that the backports are in typing is easier than remembering
      # to check for both typing.X and typing_extensions.X every time we match
      # on an abstract value.
      val.module = "typing"
    return var


def _build(name):
  return lambda ctx: ctx.convert.name_to_value(name)


def _build_not_supported_yet(name, ast):
  return lambda ctx: typing_overlay.not_supported_yet(name, ctx, ast=ast)
