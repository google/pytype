"""Utilities for parsing pytd files for builtins."""

from pytype import file_utils
from pytype.pyi import parser
from pytype.pytd import pytd_utils
from pytype.pytd import visitors


def _FindBuiltinFile(name, python_version, extension=".pytd"):
  subdir = file_utils.get_versioned_path("builtins", python_version)
  _, src = pytd_utils.GetPredefinedFile(subdir, name, extension)
  return src


# Tests might run with different python versions in the same pytype invocation.
# TODO(rechen): It would be nice to get rid of this file, or at least
# GetBuiltinsAndTyping, but the cache currently prevents slowdowns in tests
# that create loaders willy-nilly. Maybe load_pytd.py can warn if there are
# more than n loaders in play, at any given time.
_cached_builtins_pytd = {}


def InvalidateCache(python_version):
  del _cached_builtins_pytd[python_version]


def GetBuiltinsAndTyping(python_version):  # Deprecated. Use load_pytd instead.
  """Get __builtin__.pytd and typing.pytd."""
  assert python_version
  if python_version not in _cached_builtins_pytd:
    t = parser.parse_string(_FindBuiltinFile("typing", python_version),
                            name="typing",
                            python_version=python_version)
    b = parser.parse_string(_FindBuiltinFile("__builtin__", python_version),
                            name="__builtin__",
                            python_version=python_version)
    b = b.Visit(visitors.LookupExternalTypes({"typing": t},
                                             self_name="__builtin__"))
    t = t.Visit(visitors.LookupBuiltins(b))
    b = b.Visit(visitors.NamedTypeToClassType())
    t = t.Visit(visitors.NamedTypeToClassType())
    b = b.Visit(visitors.AdjustTypeParameters())
    t = t.Visit(visitors.AdjustTypeParameters())
    b = b.Visit(visitors.CanonicalOrderingVisitor())
    t = t.Visit(visitors.CanonicalOrderingVisitor())
    b.Visit(visitors.FillInLocalPointers({"": b, "typing": t,
                                          "__builtin__": b}))
    t.Visit(visitors.FillInLocalPointers({"": t, "typing": t,
                                          "__builtin__": b}))
    b.Visit(visitors.VerifyLookup())
    t.Visit(visitors.VerifyLookup())
    b.Visit(visitors.VerifyContainers())
    t.Visit(visitors.VerifyContainers())
    _cached_builtins_pytd[python_version] = (b, t)
  return _cached_builtins_pytd[python_version]


def GetBuiltinsPyTD(python_version):  # Deprecated. Use Loader.concat_all.
  """Get the "default" AST used to lookup built in types.

  Get an AST for all Python builtins as well as the most commonly used standard
  libraries.

  Args:
    python_version: The python version tuple.
  Returns:
    A pytd.TypeDeclUnit instance. It'll directly contain the builtin classes
    and functions, and submodules for each of the standard library modules.
  """
  assert python_version
  return pytd_utils.Concat(*GetBuiltinsAndTyping(python_version))


# pyi for a catch-all module
DEFAULT_SRC = """
from typing import Any
def __getattr__(name: Any) -> Any: ...
"""


def GetDefaultAst(python_version):
  return parser.parse_string(src=DEFAULT_SRC, python_version=python_version)
