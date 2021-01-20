"""Class definitions in pyi files."""

import collections

from typing import Dict, Optional, List, Tuple

from pytype.pyi.typed_ast.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pytd
from pytype.pytd.parse import node as pytd_node
from pytype.pytd.parse import parser_constants  # pylint: disable=g-importing-member

from typed_ast import ast3


_TYPED_DICT_ALIASES = (
    "typing.TypedDict",
    parser_constants.EXTERNAL_NAME_PREFIX + "typing_extensions.TypedDict")


def get_parents(
    bases: List[ast3.AST]
) -> Tuple[List[pytd_node.Node], Optional[int]]:
  """Collect base classes and namedtuple index."""

  parents = []
  namedtuple_index = None
  for i, p in enumerate(bases):
    if _is_parameterized_protocol(p):
      # From PEP 544: "`Protocol[T, S, ...]` is allowed as a shorthand for
      # `Protocol, Generic[T, S, ...]`."
      # https://www.python.org/dev/peps/pep-0544/#generic-protocols
      parents.append(p.base_type)
      parents.append(p.Replace(base_type=pytd.NamedType("typing.Generic")))
    elif isinstance(p, pytd.NamedType) and p.name == "typing.NamedTuple":
      if namedtuple_index is not None:
        raise ParseError("cannot inherit from bare NamedTuple more than once")
      namedtuple_index = i
      parents.append(p)
    elif isinstance(p, pytd.Type):
      parents.append(p)
    else:
      msg = "Unexpected class base:" + p
      raise ParseError(msg)

  return parents, namedtuple_index


def get_metaclass(keywords: List[ast3.AST], parents: List[pytd_node.Node]):
  """Scan keywords for a metaclass."""

  for k in keywords:
    keyword, value = k.arg, k.value
    if keyword not in ("metaclass", "total"):
      raise ParseError("Unexpected classdef kwarg %r" % keyword)
    elif keyword == "total" and not any(
        isinstance(parent, pytd.NamedType) and
        parent.name in _TYPED_DICT_ALIASES for parent in parents):
      raise ParseError(
          "'total' allowed as classdef kwarg only for TypedDict subclasses")
    if keyword == "metaclass":
      return value
  return None


def get_decorators(decorators: List[str], type_map: Dict[str, pytd_node.Node]):
  """Process a class decorator list."""

  # Drop the @type_check_only decorator from classes
  # TODO(mdemello): Workaround for the bug that typing.foo class decorators
  # don't add the import, since typing.type_check_only is the only one.
  decorators = [x for x in decorators if x != "type_check_only"]

  # Check for some function/method-only decorators
  nonclass = {"property", "classmethod", "staticmethod", "overload"}
  unsupported_decorators = set(decorators) & nonclass
  if unsupported_decorators:
    raise ParseError("Unsupported class decorators: %s" % ", ".join(
        unsupported_decorators))

  # Convert decorators to named types. These are wrapped as aliases because we
  # otherwise do not allow referencing functions as types.
  return [pytd.Alias(d, type_map.get(d) or pytd.NamedType(d))
          for d in decorators]


def check_for_duplicate_defs(methods, constants, aliases) -> None:
  """Check a class's list of definitions for duplicates."""
  all_names = (list(set(f.name for f in methods)) +
               [c.name for c in constants] +
               [a.name for a in aliases])
  duplicates = [name
                for name, count in collections.Counter(all_names).items()
                if count >= 2]
  if duplicates:
    raise ParseError(
        "Duplicate class-level identifier(s): " + ", ".join(duplicates))


#------------------------------------------------------
# pytd utils


def _is_parameterized_protocol(t) -> bool:
  return (isinstance(t, pytd.GenericType) and
          t.base_type.name == "typing.Protocol")
