"""Implementation of special members of typing_extensions."""
from pytype import overlay
from pytype.overlays import typing_overlay


class TypingExtensionsOverlay(overlay.Overlay):
  """A custom overlay for the 'typing_extensions' module."""

  def __init__(self, vm):
    member_map = {
        "Literal": typing_overlay.typing_overlay["Literal"],
        "Protocol": build_protocol,
        "runtime": build_runtime,  # alias for runtime_checkable
    }
    ast = vm.loader.import_name("typing_extensions")
    for pyval in ast.aliases + ast.classes + ast.constants + ast.functions:
      # Any public typing_extensions members that are not explicitly implemented
      # are unsupported.
      _, name = pyval.name.rsplit(".", 1)
      if name.startswith("_"):
        continue
      try:
        # This check is to avoid marking typing re-exports as unsupported.
        vm.loader.typing.Lookup(f"typing.{name}")
      except KeyError:
        if name not in member_map:
          member_map[name] = overlay.build(
              name, typing_overlay.not_supported_yet)
    super().__init__(vm, "typing_extensions", member_map, ast)

  def _convert_member(self, member):
    var = super()._convert_member(member)
    for val in var.data:
      # typing_extensions backports typing features to older versions.
      # Pretending that the backports are in typing is easier than remembering
      # to check for both typing.X and typing_extensions.X every time we match
      # on an abstract value.
      val.module = "typing"
    return var


def build_protocol(vm):
  return vm.convert.name_to_value("typing.Protocol")


def build_runtime(vm):
  return vm.convert.name_to_value("typing.runtime_checkable")
