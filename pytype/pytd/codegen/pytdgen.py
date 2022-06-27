"""Utilities to generate some basic types."""

from typing import Tuple

from pytype.pytd import pytd


_STRING_TYPES = ("str", "bytes", "unicode")


# Type aliases
Parameters = Tuple[pytd.Type, ...]


def pytd_list(typ: str) -> pytd.Type:
  if typ:
    return pytd.GenericType(
        pytd.NamedType("typing.List"), (pytd.NamedType(typ),))
  else:
    return pytd.NamedType("typing.List")


def is_any(val) -> bool:
  if isinstance(val, pytd.AnythingType):
    return True
  elif isinstance(val, pytd.NamedType):
    return val.name == "typing.Any"
  else:
    return False


def is_none(t) -> bool:
  return isinstance(t, pytd.NamedType) and t.name in ("None", "NoneType")


def heterogeneous_tuple(
    base_type: pytd.NamedType,
    parameters: Parameters
) -> pytd.Type:
  return pytd.TupleType(base_type=base_type, parameters=parameters)


def pytd_type(value: pytd.Type) -> pytd.Type:
  return pytd.GenericType(pytd.NamedType("type"), (value,))


def pytd_callable(
    base_type: pytd.NamedType,
    parameters: Parameters
) -> pytd.Type:
  """Create a pytd.CallableType."""
  if isinstance(parameters[0], list):
    if len(parameters) > 2:
      raise TypeError(
          "Expected 2 parameters to Callable, got %d" % len(parameters))
    if len(parameters) == 1:
      # We're usually happy to treat omitted parameters as "Any", but we
      # need a return type for CallableType, or we wouldn't know whether the
      # last parameter is an argument or return type.
      parameters += (pytd.AnythingType(),)
    if not parameters[0] or parameters[0] == [pytd.NothingType()]:
      # Callable[[], ret] -> pytd.CallableType(ret)
      parameters = parameters[1:]
    else:
      # Callable[[x, ...], ret] -> pytd.CallableType(x, ..., ret)
      parameters = tuple(parameters[0]) + parameters[1:]
    return pytd.CallableType(base_type=base_type, parameters=parameters)
  else:
    # Fall back to a generic Callable if first param is Any
    assert parameters
    if not is_any(parameters[0]):
      msg = ("First argument to Callable must be a list of argument types "
             "(got %r)" % parameters[0])
      raise TypeError(msg)
    return pytd.GenericType(base_type=base_type, parameters=parameters)
