"""Implementation of special members of sys."""

from pytype import abstract
from pytype import overlay


class SysOverlay(overlay.Overlay):
  """A custom overlay for the 'sys' module."""

  def __init__(self, vm):
    member_map = {
        "version_info": build_version_info
    }
    ast = vm.loader.import_name("sys")
    super(SysOverlay, self).__init__(vm, "sys", member_map, ast)


def build_version_info(name, vm):
  del name
  tup = tuple(vm.convert.constant_to_var(i) for i in vm.python_version)
  return abstract.Tuple(tup, vm)
