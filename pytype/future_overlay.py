"""Implementation of special members of the future library."""

from pytype import metaclass
from pytype import overlay


class FutureUtilsOverlay(overlay.Overlay):
  """A custom overlay for the 'future' module."""

  def __init__(self, vm):
    member_map = {
        "with_metaclass": build_with_metaclass,
    }
    ast = vm.loader.import_name("future.utils")
    super(FutureUtilsOverlay, self).__init__(vm, "future.utils", member_map,
                                             ast)


def build_with_metaclass(name, vm):
  return metaclass.WithMetaclass.make(name, vm, "future.utils")
