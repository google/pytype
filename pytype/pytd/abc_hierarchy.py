"""Abstract base class hierarchy for both Python 2 and Python 3."""

from pytype import utils


# (We specify the below manually, instead of extracting it out of abc.py,
#  because we need support for Python 2 as well as Python 3 without having to
#  depend on the "host" Python)


# class -> list of superclasses
SUPERCLASSES = {
    # "mixins" (don't derive from object)
    "Hashable": [],
    "Iterable": [],
    "Sized": [],
    "Callable": [],
    "Iterator": ["Iterable"],

    # Classes (derive from object). Same for Python 2 and 3.
    "Container": ["object"],
    "Number": ["object"],
    "Complex": ["Number"],
    "Real": ["Complex"],
    "Rational": ["Real"],
    "Integral": ["Rational"],
    "Set": ["Sized", "Iterable", "Container"],
    "MutableSet": ["Set"],
    "Mapping": ["Sized", "Iterable", "Container"],
    "MappingView": ["Sized"],
    "KeysView": ["MappingView", "Set"],
    "ItemsView": ["MappingView", "Set"],
    "ValuesView": ["MappingView"],
    "MutableMapping": ["Mapping"],
    "Sequence": ["Sized", "Iterable", "Container"],
    "MutableSequence": ["Sequence"],

    # Builtin types. Python 2 and 3 agree on these:
    "set": ["MutableSet"],
    "frozenset": ["Set"],
    "dict": ["MutableMapping"],
    "tuple": ["Sequence"],
    "list": ["MutableSequence"],
    "complex": ["Complex"],
    "float": ["Real"],
    "int": ["Integral"],
    "bool": ["int"],

    # In Python 3, str is registered directly with Sequence. In Python 2,
    # str inherits from basestring, which inherits from Sequence. We simplify
    # things by just letting str inherit from Sequence everywhere.
    "str": ["Sequence"],
    "basestring": ["Sequence"],
    "bytes": ["Sequence"],

    # Types that exist in Python 2, but not in Python 3:
    "buffer": ["Sequence"],
    "xrange": ["Sequence"],
    "unicode": ["Sequence"],

    # Types that exist in Python 3, but not in Python 2:
    "range": ["Sequence"],  # "range" is a function, not a type, in Python 2

    # Omitted: "bytearray". It inherits from ByteString (which only exists in
    # Python 3) and MutableSequence. The latter exists in Python 2, but
    # bytearray isn't registered with it.

    # Python 2 + 3 types that can only be constructed indirectly.
    # (See EOL comments for the definition)
    "bytearray_iterator": ["Iterator"],  # type(iter(bytearray()))
    "dict_keys": ["KeysView"],  # type({}.viewkeys()) or type({}.keys()).
    "dict_items": ["ItemsView"],  # type({}.viewitems()) or type({}.items()).
    "dict_values": ["ValuesView"],  # type({}.viewvalues()) or type({}.values())

    # Python 2 types that can only be constructed indirectly.
    "dictionary-keyiterator": ["Iterator"],  # type(iter({}.viewkeys()))
    "dictionary-valueiterator": ["Iterator"],  # type(iter({}.viewvalues()))
    "dictionary-itemiterator": ["Iterator"],  # type(iter({}.viewitems()))
    "listiterator": ["Iterator"],  # type(iter([]))
    "listreverseiterator": ["Iterator"],  # type(iter(reversed([])))
    "rangeiterator": ["Iterator"],  # type(iter(xrange(0)))
    "setiterator": ["Iterator"],  # type(iter(set()))
    "tupleiterator": ["Iterator"],  # type(iter(()))

    # Python 3 types that can only be constructed indirectly.
    "dict_keyiterator": ["Iterator"],  # type(iter({}.keys()))
    "dict_valueiterator": ["Iterator"],  # type(iter({}.values()))
    "dict_itemiterator": ["Iterator"],  # type(iter({}.items()))
    "list_iterator": ["Iterator"],  # type(iter([]))
    "list_reverseiterator": ["Iterator"],  # type(iter(reversed([])))
    "range_iterator": ["Iterator"],  # type(iter(range(0)))
    "set_iterator": ["Iterator"],  # type(iter(set()))
    "tuple_iterator": ["Iterator"],  # type(iter(()))
    "str_iterator": ["Iterator"],  # type(iter("")). Python 2: just "iterator"
    "zip_iterator": ["Iterator"],  # type(iter(zip())). Python 2: listiterator
    "bytes_iterator": ["Iterator"],  # type(iter(b'')). Python 2: bytes == str
}


def GetSuperClasses():
  """Get a Python type hierarchy mapping.

  This generates a dictionary that can be used to look up the parents of
  a type in the abstract base class hierarchy.

  Returns:
    A dictionary mapping a type, as string, to a list of base types (also
    as strings). E.g. "float" -> ["Real"].
  """

  return SUPERCLASSES.copy()


def GetSubClasses():
  """Get a reverse Python type hierarchy mapping.

  This generates a dictionary that can be used to look up the (known)
  subclasses of a type in the abstract base class hierarchy.

  Returns:
    A dictionary mapping a type, as string, to a list of direct
    subclasses (also as strings).
    E.g. "Sized" -> ["Set", "Mapping", "MappingView", "Sequence"].
  """

  return utils.invert_dict(GetSuperClasses())
