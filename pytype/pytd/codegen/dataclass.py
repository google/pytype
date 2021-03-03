"""Generate code for dataclasses."""

from pytype.pytd import pytd
from pytype.pytd.codegen import function


def make_dataclass(cls: pytd.Class) -> pytd.Class:
  _check_defaults(cls)
  init = _make_init(cls)
  methods = cls.methods + tuple(function.merge_method_signatures([init]))
  return cls.Replace(methods=methods)


def _check_defaults(cls: pytd.Class):
  has_default = False
  for c in cls.constants:
    if c.value is not None:
      has_default = True
    elif has_default:
      raise TypeError(
          f"In dataclass {cls.name}: "
          f"non-default argument {c.name} follows default arguments")


def _make_param(attr: pytd.Constant) -> function.Param:
  return function.Param(
      name=attr.name, type=attr.type, default=attr.value).to_pytd()


def _make_init(cls: pytd.Class) -> function.NameAndSig:
  """Build an __init__ method for a dataclass."""
  self_arg = function.Param("self", pytd.AnythingType()).to_pytd()
  params = (self_arg,) + tuple(_make_param(c) for c in cls.constants)
  ret = pytd.NamedType("NoneType")
  sig = pytd.Signature(params=params, return_type=ret,
                       starargs=None, starstarargs=None,
                       exceptions=(), template=())
  return function.NameAndSig("__init__", sig)
