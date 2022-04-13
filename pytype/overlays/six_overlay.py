"""Implementation of special members of third_party/six."""

from pytype import metaclass
from pytype.overlays import overlay


class SixOverlay(overlay.Overlay):
  """A custom overlay for the 'six' module."""

  def __init__(self, ctx):
    member_map = {
        "add_metaclass": build_add_metaclass,
        "with_metaclass": build_with_metaclass,
        "string_types": build_string_types,
        "integer_types": build_integer_types,
        "PY2": build_version_bool(2),
        "PY3": build_version_bool(3),
    }
    ast = ctx.loader.import_name("six")
    super().__init__(ctx, "six", member_map, ast)


def build_add_metaclass(ctx):
  return metaclass.AddMetaclass.make("add_metaclass", ctx, "six")


def build_with_metaclass(ctx):
  return metaclass.WithMetaclass.make("with_metaclass", ctx, "six")


def build_version_bool(major):
  return lambda ctx: ctx.convert.bool_values[ctx.python_version[0] == major]


def build_string_types(ctx):
  # six.string_types is defined as a tuple, even though it's only a single value
  # in Py3.
  # We're following the pyi definition of string_types here, because the real
  # value in Py2 is `basestring`, which we don't have available.
  classes = [ctx.convert.str_type.to_variable(ctx.root_node)]
  return ctx.convert.tuple_to_value(classes)


def build_integer_types(ctx):
  # pytype treats `long` as an alias of `int`, so the value of integer_types can
  # be represented as just `(int,)` in both Py2 and Py3.
  return ctx.convert.tuple_to_value(
      (ctx.convert.int_type.to_variable(ctx.root_node),))
