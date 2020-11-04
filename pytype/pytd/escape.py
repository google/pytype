"""Utilities for quoting, name-mangling, etc."""


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
