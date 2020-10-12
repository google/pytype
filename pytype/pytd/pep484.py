"""PEP484 compatibility code."""

from pytype.pytd import pytd
from pytype.pytd import visitors


PEP484_NAMES = ["AbstractSet", "AnyStr", "AsyncGenerator", "BinaryIO",
                "ByteString", "Callable", "Container", "Dict", "FrozenSet",
                "Generator", "Generic", "Hashable", "IO", "ItemsView",
                "Iterable", "Iterator", "KeysView", "List", "Mapping",
                "MappingView", "Match", "MutableMapping", "MutableSequence",
                "MutableSet", "NamedTuple", "Optional", "Pattern",
                "Reversible", "Sequence", "Set", "Sized", "SupportsAbs",
                "SupportsFloat", "SupportsInt", "SupportsRound", "TextIO",
                "Tuple", "Type", "TypeVar", "Union"]


# Pairs of a type and a more generalized type.
COMPAT_ITEMS = [
    ("NoneType", "bool"),
    # pep484 allows None as an alias for NoneType in type annotations.
    ("None", "bool"),
    ("int", "float"),
    ("int", "complex"),
    ("float", "complex"),
    ("bytearray", "bytes"),
    ("memoryview", "bytes"),
]


PEP484_CAPITALIZED = frozenset({
    # The PEP 484 definition of built-in types.
    # E.g. "typing.List" is used to represent the "list" type.
    "List", "Dict", "Tuple", "Set", "FrozenSet", "Generator", "Type",
    "Coroutine", "AsyncGenerator"
})


def PEP484_MaybeCapitalize(name):  # pylint: disable=invalid-name
  for capitalized in PEP484_CAPITALIZED:
    if capitalized.lower() == name:
      return capitalized


class ConvertTypingToNative(visitors.Visitor):
  """Visitor for converting PEP 484 types to native representation."""

  def __init__(self, module):
    super().__init__()
    self.module = module

  def _GetModuleAndName(self, t):
    if isinstance(t, pytd.GenericType):
      return self._GetModuleAndName(t.base_type)
    elif isinstance(t, (pytd.ClassType, pytd.NamedType)) and "." in t.name:
      return t.name.rsplit(".", 1)
    else:
      return None, t.name

  def _IsTyping(self, module):
    return module == "typing" or (module is None and self.module == "typing")

  def _Convert(self, t):
    module, name = self._GetModuleAndName(t)
    if not module and name == "None":
      # PEP 484 allows "None" as an abbreviation of "NoneType".
      return pytd.NamedType("NoneType")
    elif self._IsTyping(module):
      if name in PEP484_CAPITALIZED:
        return pytd.NamedType(name.lower())  # "typing.List" -> "list" etc.
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

  def VisitGenericType(self, t):
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
    if self.module == "__builtin__":
      parents = []
      for old_parent, new_parent in zip(self.old_node.parents, node.parents):
        if (isinstance(new_parent, (pytd.GenericType, pytd.ClassType,
                                    pytd.NamedType)) and
            self._GetModuleAndName(new_parent)[1] == node.name):
          # Don't do conversions like class list(List) -> class list(list)
          parents.append(old_parent)
        else:
          parents.append(new_parent)
      return node.Replace(parents=tuple(parents))
    else:
      return node
