"""Utilities for parsing pytd files for builtins."""

import os

from pytype.pyi import parser
from pytype.pytd import pytd_utils
from pytype.pytd import visitors


# TODO(rechen): It would be nice to get rid of GetBuiltinsAndTyping, and let the
# loader call BuiltinsAndTyping.load directly, but the cache currently prevents
# slowdowns in tests that create loaders willy-nilly.  Maybe load_pytd.py can
# warn if there are more than n loaders in play, at any given time.
_cached_builtins_pytd = []

# pylint: disable=invalid-name
# We use a mix of camel case and snake case method names in this file.


def InvalidateCache():
  if _cached_builtins_pytd:
    del _cached_builtins_pytd[0]


# Do not call this - get the "builtins" and "typing" modules via the loader.
def GetBuiltinsAndTyping(gen_stub_imports):
  if not _cached_builtins_pytd:
    _cached_builtins_pytd.append(BuiltinsAndTyping().load(gen_stub_imports))
  return _cached_builtins_pytd[0]


# Do not call this - use Loader.concat_all()
def GetBuiltinsPyTD():
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


# If you have a Loader available, use loader.get_default_ast() instead.
def GetDefaultAst(gen_stub_imports):
  return parser.parse_string(src=DEFAULT_SRC, gen_stub_imports=gen_stub_imports)


class BuiltinsAndTyping:
  """The builtins and typing modules, which need to be treated specially."""

  def _parse_predefined(self, name, gen_stub_imports):
    _, src = pytd_utils.GetPredefinedFile("builtins", name, ".pytd")
    mod = parser.parse_string(src, name=name, gen_stub_imports=gen_stub_imports)
    return mod

  def load(self, gen_stub_imports):
    """Read builtins.pytd and typing.pytd, and return the parsed modules."""
    t = self._parse_predefined("typing", gen_stub_imports)
    b = self._parse_predefined("builtins", gen_stub_imports)
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
    return b, t


class BuiltinLoader:
  """Load builtins from the pytype source tree."""

  def __init__(self, python_version, gen_stub_imports):
    self.python_version = python_version
    self.gen_stub_imports = gen_stub_imports

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
