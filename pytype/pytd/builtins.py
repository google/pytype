"""Utilities for parsing pytd files for builtins."""

from pytype.pyi import parser
from pytype.pytd import pytd_utils
from pytype.pytd import visitors


def _FindBuiltinFile(name):
  _, src = pytd_utils.GetPredefinedFile("builtins", name, ".pytd")
  return src


# TODO(rechen): It would be nice to get rid of this file, or at least
# GetBuiltinsAndTyping, but the cache currently prevents slowdowns in tests
# that create loaders willy-nilly. Maybe load_pytd.py can warn if there are
# more than n loaders in play, at any given time.
_cached_builtins_pytd = []


def InvalidateCache():
  if _cached_builtins_pytd:
    del _cached_builtins_pytd[0]


def GetBuiltinsAndTyping():  # Deprecated. Use load_pytd instead.
  """Get builtins.pytd and typing.pytd."""
  if not _cached_builtins_pytd:
    t = parser.parse_string(_FindBuiltinFile("typing"), name="typing")
    b = parser.parse_string(_FindBuiltinFile("builtins"), name="builtins")
    b = b.Visit(visitors.LookupExternalTypes({"typing": t},
                                             self_name="builtins"))
    t = t.Visit(visitors.LookupBuiltins(b))
    b = b.Visit(visitors.NamedTypeToClassType())
    t = t.Visit(visitors.NamedTypeToClassType())
    b = b.Visit(visitors.AdjustTypeParameters())
    t = t.Visit(visitors.AdjustTypeParameters())
    b = b.Visit(visitors.CanonicalOrderingVisitor())
    t = t.Visit(visitors.CanonicalOrderingVisitor())
    b.Visit(visitors.FillInLocalPointers({"": b, "typing": t,
                                          "builtins": b}))
    t.Visit(visitors.FillInLocalPointers({"": t, "typing": t,
                                          "builtins": b}))
    b.Visit(visitors.VerifyLookup())
    t.Visit(visitors.VerifyLookup())
    b.Visit(visitors.VerifyContainers())
    t.Visit(visitors.VerifyContainers())
    _cached_builtins_pytd.append((b, t))
  return _cached_builtins_pytd[0]


def GetBuiltinsPyTD():  # Deprecated. Use Loader.concat_all.
  """Get the "default" AST used to lookup built in types.

  Get an AST for all Python builtins as well as the most commonly used standard
  libraries.

  Returns:
    A pytd.TypeDeclUnit instance. It'll directly contain the builtin classes
    and functions, and submodules for each of the standard library modules.
  """
  return pytd_utils.Concat(*GetBuiltinsAndTyping())


# pyi for a catch-all module
DEFAULT_SRC = """
from typing import Any
def __getattr__(name: Any) -> Any: ...
"""


def GetDefaultAst():
  return parser.parse_string(src=DEFAULT_SRC)
