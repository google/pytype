"""PEP484 compatibility code."""

from typing import TypeVar
from pytype.pytd import base_visitor
from pytype.pytd import pytd

_T0 = TypeVar("_T0")


ALL_TYPING_NAMES: list[str] = [
    "AbstractSet",
    "AnyStr",
    "AsyncGenerator",
    "BinaryIO",
    "ByteString",
    "Callable",
    "Container",
    "Dict",
    "FrozenSet",
    "Generator",
    "Generic",
    "Hashable",
    "IO",
    "ItemsView",
    "Iterable",
    "Iterator",
    "KeysView",
    "List",
    "Mapping",
    "MappingView",
    "Match",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "NamedTuple",
    "Optional",
    "Pattern",
    "Reversible",
    "Sequence",
    "Set",
    "Sized",
    "SupportsAbs",
    "SupportsFloat",
    "SupportsInt",
    "SupportsRound",
    "TextIO",
    "Tuple",
    "Type",
    "TypeVar",
    "Union",
]


# Pairs of a type and a more generalized type.
_COMPAT_ITEMS: list[tuple[str, str]] = [
    ("int", "float"),
    ("int", "complex"),
    ("float", "complex"),
    ("bytearray", "bytes"),
    ("memoryview", "bytes"),
]

# The PEP 484 definition of built-in types.
# E.g. "typing.List" is used to represent the "list" type.
BUILTIN_TO_TYPING: dict[str, str] = {
    t.lower(): t
    for t in [
        "List",
        "Dict",
        "Tuple",
        "Set",
        "FrozenSet",
        "Type",
    ]
}

TYPING_TO_BUILTIN: dict[str, str] = {v: k for k, v in BUILTIN_TO_TYPING.items()}


def get_compat_items(none_matches_bool=False) -> list[tuple[str, str]]:
  # pep484 allows None as an alias for NoneType in type annotations.
  extra = [("NoneType", "bool"), ("None", "bool")] if none_matches_bool else []
  return _COMPAT_ITEMS + extra


class ConvertTypingToNative(base_visitor.Visitor):
  """Visitor for converting PEP 484 types to native representation."""

  def __init__(self, module) -> None:
    super().__init__()
    self.module = module

  def _GetModuleAndName(self, t):
    if t.name and "." in t.name:
      return t.name.rsplit(".", 1)
    else:
      return None, t.name

  def _IsTyping(self, module):
    return module == "typing" or (module is None and self.module == "typing")

  def _Convert(self, t: _T0) -> pytd.AnythingType | pytd.NamedType | _T0:
    module, name = self._GetModuleAndName(t)
    if not module and name == "None":
      # PEP 484 allows "None" as an abbreviation of "NoneType".
      return pytd.NamedType("NoneType")
    elif self._IsTyping(module):
      if name in TYPING_TO_BUILTIN:
        # "typing.List" -> "list" etc.
        return pytd.NamedType(TYPING_TO_BUILTIN[name])
      elif name == "Any":
        return pytd.AnythingType()
      else:
        # IO, Callable, etc. (I.e., names in typing we leave alone)
        return t
    else:
      return t

  def VisitClassType(self, t):
    return self._Convert(t)

  def VisitNamedType(self, t):
    return self._Convert(t)

  def VisitGenericType(
      self, t: _T0
  ) -> pytd.IntersectionType | pytd.UnionType | _T0:
    module, name = self._GetModuleAndName(t)
    if self._IsTyping(module):
      if name == "Intersection":
        return pytd.IntersectionType(t.parameters)
      elif name == "Optional":
        return pytd.UnionType(t.parameters + (pytd.NamedType("NoneType"),))
      elif name == "Union":
        return pytd.UnionType(t.parameters)
    return t

  def VisitCallableType(self, t):
    return self.VisitGenericType(t)

  def VisitTupleType(self, t):
    return self.VisitGenericType(t)

  def VisitClass(self, node):
    if self.module == "builtins":
      bases = []
      for old_base, new_base in zip(self.old_node.bases, node.bases):
        if self._GetModuleAndName(new_base)[1] == node.name:
          # Don't do conversions like class list(List) -> class list(list)
          bases.append(old_base)
        else:
          bases.append(new_base)
      return node.Replace(bases=tuple(bases))
    else:
      return node
