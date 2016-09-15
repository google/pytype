# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-

# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Utilities for parsing pytd files for builtins."""

import os


from pytype.pytd import data_files
from pytype.pytd import utils
from pytype.pytd.parse import parser
from pytype.pytd.parse import visitors


def _FindBuiltinFile(name, extension=".pytd"):
  return data_files.GetPredefinedFile("builtins", name, extension)


def _FindStdlibFile(name, extension=".pytd"):
  return data_files.GetPredefinedFile("stdlib", name, extension)


# Keyed by the parameter(s) passed to GetBuiltinsPyTD:
_cached_builtins_pytd = None  # ... => pytype.pytd.pytd.TypeDeclUnit


def GetBuiltinsAndTyping():
  """Get __builtin__.pytd and typing.pytd."""
  global _cached_builtins_pytd
  if not _cached_builtins_pytd:
    t = parser.TypeDeclParser().Parse(_FindBuiltinFile("typing"), name="typing")
    t = t.Visit(visitors.AddNamePrefix())
    b = parser.TypeDeclParser().Parse(_FindBuiltinFile("__builtin__"),
                                      name="__builtin__")
    b = b.Visit(visitors.AddNamePrefix())
    b = b.Visit(visitors.NamedTypeToClassType())
    b = b.Visit(visitors.LookupExternalTypes({"typing": t}, full_names=True,
                                             self_name="__builtin__"))
    t = t.Visit(visitors.LookupBuiltins(b))
    t = t.Visit(visitors.NamedTypeToClassType())
    b = visitors.AdjustTypeParameters(b)
    t = visitors.AdjustTypeParameters(t)
    b.Visit(visitors.FillInModuleClasses({"": b, "typing": t,
                                          "__builtin__": b}))
    t.Visit(visitors.FillInModuleClasses({"": t, "typing": t,
                                          "__builtin__": b}))
    b.Visit(visitors.VerifyLookup())
    t.Visit(visitors.VerifyLookup())
    b.Visit(visitors.VerifyContainers())
    t.Visit(visitors.VerifyContainers())
    _cached_builtins_pytd = b, t
  return _cached_builtins_pytd


def GetBuiltinsPyTD():
  """Get the "default" AST used to lookup built in types.

  Get an AST for all Python builtins as well as the most commonly used standard
  libraries.

  Returns:
    A pytd.TypeDeclUnit instance. It'll directly contain the builtin classes
    and functions, and submodules for each of the standard library modules.
  """
  return utils.Concat(*GetBuiltinsAndTyping())


# TODO(kramm): Use python_version, once we have builtins for both Python 2 and
# Python 3.
def GetBuiltinsCode(unused_python_version):
  """Similar to GetBuiltinsPyTD, but for code in the .py file."""
  return _FindBuiltinFile("__builtin__", extension=".py")


def ParsePyTD(src=None, filename=None, python_version=None, module=None,
              lookup_classes=False):
  """Parse pytd sourcecode and do name lookup for builtins.

  This loads a pytd and also makes sure that all names are resolved (i.e.,
  that all primitive types in the AST are ClassType, and not NameType).

  Args:
    src: PyTD source code.
    filename: The filename the source code is from.
    python_version: The Python version to parse the pytd for.
    module: The name of the module we're parsing.
    lookup_classes: If we should also lookup the class of every ClassType.

  Returns:
    A pytd.TypeDeclUnit.
  """
  assert python_version
  if src is None:
    with open(filename, "rb") as fi:
      src = fi.read()
  ast = parser.parse_string(src, filename=filename, name=module,
                            python_version=python_version)
  if module is not None:  # Allow "" as module name
    ast = ast.Visit(visitors.AddNamePrefix())
  if lookup_classes:
    ast = visitors.LookupClasses(ast, GetBuiltinsPyTD())
  return ast


def ParsePredefinedPyTD(pytd_subdir, module, python_version):
  """Load and parse a *.pytd from "pytd/{pytd_subdir}/{module}.pytd".

  Args:
    pytd_subdir: the directory where the module should be found
    module: the module name (without any file extension)
    python_version: sys.version_info[:2]

  Returns:
    The AST of the module; None if the module doesn't exist in pytd_subdir.
  """
  try:
    src = data_files.GetPredefinedFile(pytd_subdir, module)
  except IOError:
    return None
  return ParsePyTD(src, filename=os.path.join(pytd_subdir, module + ".pytd"),
                   module=module,
                   python_version=python_version).Replace(name=module)


# pyi for a catch-all module
DEFAULT_SRC = """
from typing import Any
def __getattr__(name) -> Any
"""


def GetDefaultAst(python_version):
  return ParsePyTD(src=DEFAULT_SRC,
                   python_version=python_version, lookup_classes=True)
