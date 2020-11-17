"""Implementation of special members of third_party/six."""

from pytype import metaclass
from pytype import overlay


class SixOverlay(overlay.Overlay):
  """A custom overlay for the 'six' module."""

  def __init__(self, vm):
    member_map = {
        "add_metaclass": build_add_metaclass,
        "with_metaclass": build_with_metaclass,
        "string_types": build_string_types,
        "integer_types": build_integer_types,
        "PY2": build_version_bool(2),
        "PY3": build_version_bool(3),
    }
    ast = vm.loader.import_name("six")
    super().__init__(vm, "six", member_map, ast)


def build_add_metaclass(vm):
  return metaclass.AddMetaclass.make("add_metaclass", vm, "six")


def build_with_metaclass(vm):
  return metaclass.WithMetaclass.make("with_metaclass", vm, "six")


def build_version_bool(major):
  return lambda vm: vm.convert.bool_values[vm.python_version[0] == major]


def build_string_types(vm):
  # six.string_types is defined as a tuple, even though it's only a single value
  # in Py3.
  # We're following the pyi definition of string_types here, because the real
  # value in Py2 is `basestring`, which we don't have available.
  node = vm.root_cfg_node
  classes = [vm.convert.str_type.to_variable(node)]
  if vm.PY2:
    classes.append(vm.convert.unicode_type.to_variable(node))
  return vm.convert.tuple_to_value(classes)


def build_integer_types(vm):
  # pytype treats `long` as an alias of `int`, so the value of integer_types can
  # be represented as just `(int,)` in both Py2 and Py3.
  return vm.convert.tuple_to_value(
      (vm.convert.int_type.to_variable(vm.root_cfg_node),))
