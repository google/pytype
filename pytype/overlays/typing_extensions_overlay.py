"""Implementation of special members of typing_extensions."""
from pytype import overlay
from pytype.overlays import typing_overlay
from pytype.pytd import pytd


class TypingExtensionsOverlay(overlay.Overlay):
  """A custom overlay for the 'typing_extensions' module."""

  def __init__(self, ctx):
    ast = ctx.loader.import_name("typing_extensions")
    member_map = {
        "Annotated": typing_overlay.typing_overlay["Annotated"],
        "final": typing_overlay.typing_overlay["final"],
        "Final": typing_overlay.typing_overlay["Final"],
        "Literal": typing_overlay.typing_overlay["Literal"],
        "Protocol": _build("typing.Protocol"),
        "runtime": _build("typing.runtime_checkable"),
        "SupportsIndex": _build("typing_extensions.SupportsIndex", ast),
        "TypedDict": typing_overlay.typing_overlay["TypedDict"],
    }
    for pyval in ast.aliases + ast.classes + ast.constants + ast.functions:
      # Any public typing_extensions members that are not explicitly implemented
      # are unsupported.
      _, name = pyval.name.rsplit(".", 1)
      if name.startswith("_"):
        continue
      if f"typing.{name}" not in ctx.loader.typing:
        if name not in member_map:
          member_map[name] = _build_not_supported_yet(
              f"typing_extensions.{name}", ast)
    super().__init__(ctx, "typing_extensions", member_map, ast)

  def _convert_member(self, member, subst=None):
    var = super()._convert_member(member, subst)
    for val in var.data:
      # typing_extensions backports typing features to older versions.
      # Pretending that the backports are in typing is easier than remembering
      # to check for both typing.X and typing_extensions.X every time we match
      # on an abstract value.
      val.module = "typing"
    return var


def _build(name, ast=None):
  return lambda ctx: ctx.convert.name_to_value(name, ast=ast)


def _build_not_supported_yet(name, ast):

  def build(ctx):
    # Returns the actual type instead of just Any so that users can still get
    # some utility out of unsupported features.
    ctx.errorlog.not_supported_yet(ctx.vm.frames, name)
    pytd_type = pytd.ToType(ast.Lookup(name), True, True, True)
    return ctx.convert.constant_to_value(pytd_type, node=ctx.root_node)

  return build
