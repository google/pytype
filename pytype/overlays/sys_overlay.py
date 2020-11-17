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
    super().__init__(vm, "sys", member_map, ast)


class VersionInfo(abstract.Tuple):

  ATTRIBUTES = ("major", "minor", "micro", "releaselevel", "serial")

  def get_special_attribute(self, node, name, valself):
    try:
      index = self.ATTRIBUTES.index(name)
    except ValueError:
      return None
    return self.pyval[index]


def build_version_info(vm):
  """Build sys.version_info."""
  version = []
  # major, minor
  for i in vm.python_version:
    version.append(vm.convert.constant_to_var(i))
  # micro, releaselevel, serial
  for t in (int, str, int):
    version.append(
        vm.convert.primitive_class_instances[t].to_variable(vm.root_cfg_node))
  return VersionInfo(tuple(version), vm)
