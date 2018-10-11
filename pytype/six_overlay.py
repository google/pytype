"""Implementation of special members of third_party/six."""

from pytype import metaclass
from pytype import overlay


class SixOverlay(overlay.Overlay):
  """A custom overlay for the 'six' module."""

  def __init__(self, vm):
    member_map = {
        "add_metaclass": AddMetaclass,
        "with_metaclass": WithMetaclass,
        "PY2": build_version_bool(2),
        "PY3": build_version_bool(3),
    }
    ast = vm.loader.import_name("six")
    super(SixOverlay, self).__init__(vm, "six", member_map, ast)


class AddMetaclass(metaclass.AddMetaclass):

  def __init__(self, name, vm):
    super(AddMetaclass, self).__init__(name, vm, "six")


class WithMetaclass(metaclass.WithMetaclass):

  def __init__(self, name, vm):
    super(WithMetaclass, self).__init__(name, vm, "six")


def build_version_bool(major):
  return lambda _, vm: vm.convert.bool_values[vm.python_version[0] == major]
