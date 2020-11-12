"""Utilities for quoting, name-mangling, etc."""

import re

from typing import List


PARTIAL = "~"
UNKNOWN = PARTIAL + "unknown"


def pack_partial(name: str) -> str:
  """Pack a name, for unpacking with unpack_partial()."""
  return PARTIAL + name.replace(".", PARTIAL)


def unpack_partial(name: str) -> str:
  """Convert e.g. "~int" to "int"."""
  assert isinstance(name, str)
  assert name.startswith(PARTIAL)
  return name[len(PARTIAL):].replace(PARTIAL, ".")


def is_partial(cls) -> bool:
  """Returns True if this is a partial class, e.g. "~list"."""
  if isinstance(cls, str):
    return cls.startswith(PARTIAL)
  elif hasattr(cls, "name"):
    return cls.name.startswith(PARTIAL)
  else:
    return False


def is_complete(cls) -> bool:
  return not is_partial(cls)


def unknown(idcode: int) -> str:
  return UNKNOWN + str(idcode)


def is_unknown(name: str) -> bool:
  return name.startswith(UNKNOWN)


def preprocess_pytd(text: str) -> str:
  """Replace ~ in a text pytd with PARTIAL."""
  return text.replace("~", PARTIAL)


def pack_namedtuple(name: str, fields: List[str]) -> str:
  """Generate a name for a namedtuple proxy class."""
  return "namedtuple_%s_%s" % (name, "_".join(fields))


def pack_namedtuple_base_class(name: str, index: int) -> str:
  """Generate a name for a namedtuple proxy base class."""
  return "namedtuple_%s_%d" % (name, index)


def unpack_namedtuple(name: str) -> str:
  """Retrieve the original namedtuple class name."""
  return re.sub(r"\bnamedtuple[-_]([^-_]+)[-_\w]*", r"\1", name)
