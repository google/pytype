"""Utilities for parsing pytd files for builtins."""

import os

from pytype.pyi import parser
from pytype.pytd import pytd_utils
from pytype.pytd import visitors


def _FindBuiltinFile(name):
  _, src = pytd_utils.GetPredefinedFile("builtins", name, ".pytd")
  return src


# TODO(rechen): It would be nice to get rid of GetBuiltinsAndTyping, but the
# cache currently prevents slowdowns in tests that create loaders willy-nilly.
# Maybe load_pytd.py can warn if there are more than n loaders in play, at any
# given time.
_cached_builtins_pytd = []


def InvalidateCache():
  if _cached_builtins_pytd:
    del _cached_builtins_pytd[0]


# Deprecated. Use load_pytd instead.
def GetBuiltinsAndTyping(gen_stub_imports):
  """Get builtins.pytd and typing.pytd."""
  if not _cached_builtins_pytd:
    t = parser.parse_string(_FindBuiltinFile("typing"), name="typing",
                            gen_stub_imports=gen_stub_imports)
    b = parser.parse_string(_FindBuiltinFile("builtins"), name="builtins",
                            gen_stub_imports=gen_stub_imports)
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
  return pytd_utils.Concat(*GetBuiltinsAndTyping(True))


# pyi for a catch-all module
DEFAULT_SRC = """
from typing import Any
def __getattr__(name: Any) -> Any: ...
"""


def GetDefaultAst(gen_stub_imports):
  return parser.parse_string(src=DEFAULT_SRC, gen_stub_imports=gen_stub_imports)


class BuiltinLoader:
  """Load builtins from the pytype source tree."""

  def __init__(self, python_version, gen_stub_imports):
    self.python_version = python_version
    self.gen_stub_imports = gen_stub_imports

  # pylint: disable=invalid-name
  def _parse_predefined(self, pytd_subdir, module, as_package=False):
    """Parse a pyi/pytd file in the pytype source tree."""
    try:
      filename, src = pytd_utils.GetPredefinedFile(
          pytd_subdir, module, as_package=as_package)
    except IOError:
      return None
    ast = parser.parse_string(
        src, filename=filename, name=module, python_version=self.python_version,
        gen_stub_imports=self.gen_stub_imports)
    assert ast.name == module
    return ast

  def get_builtin(self, builtin_dir, module_name):
    """Load a stub that ships with pytype."""
    mod = self._parse_predefined(builtin_dir, module_name)
    # For stubs in pytype's stubs/ directory, we use the module name prefixed
    # with "pytd:" for the filename. Package filenames need an "/__init__.pyi"
    # suffix for Module.is_package to recognize them.
    if mod:
      filename = module_name
    else:
      mod = self._parse_predefined(builtin_dir, module_name, as_package=True)
      filename = os.path.join(module_name, "__init__.pyi")
    return filename, mod
  # pylint: enable=invalid-name
