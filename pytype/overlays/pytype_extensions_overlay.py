"""Implementation of special members of pytype_extensions."""

from pytype import overlay
from pytype import special_builtins


class PytypeExtensionsOverlay(overlay.Overlay):
  """A custom overlay for the 'pytype_extensions' module."""

  def __init__(self, vm):
    member_map = {
        "assert_type": build_assert_type
    }
    ast = vm.loader.import_name("pytype_extensions")
    super().__init__(vm, "pytype_extensions", member_map, ast)


def build_assert_type(vm):
  return special_builtins.AssertType.make_alias(
      "assert_type", vm, "pytype_extensions")
