"""Implementation of special members of third_party/six."""

from pytype import metaclass
from pytype import overlay


class SixOverlay(overlay.Overlay):
  """A custom overlay for the 'six' module."""

  def __init__(self, vm):
    member_map = {
        "add_metaclass": build_add_metaclass,
        "with_metaclass": build_with_metaclass,
        "PY2": build_version_bool(2),
        "PY3": build_version_bool(3),
    }
    ast = vm.loader.import_name("six")
    super(SixOverlay, self).__init__(vm, "six", member_map, ast)


def build_add_metaclass(name, vm):
  return metaclass.AddMetaclass.make(name, vm, "six")


def build_with_metaclass(name, vm):
  return metaclass.WithMetaclass.make(name, vm, "six")


def build_version_bool(major):
  return lambda _, vm: vm.convert.bool_values[vm.python_version[0] == major]
