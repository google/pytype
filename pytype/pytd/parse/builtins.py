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


from pytype.pytd import data_files
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
    t = parser.TypeDeclParser().Parse(_FindStdlibFile("typing"), name="typing")
    t = t.Visit(visitors.AddNamePrefix("typing."))
    t = t.Visit(visitors.NamedTypeToClassType())
    b = parser.TypeDeclParser().Parse(_FindBuiltinFile("__builtin__"),
                                      name="__builtin__")
    b = b.Visit(visitors.NamedTypeToClassType())
    b = b.Visit(visitors.LookupExternalTypes({"typing": t}, full_names=True))
    b.Visit(visitors.FillInModuleClasses({"": b, "typing": t}))
    t.Visit(visitors.FillInModuleClasses({"": t, "typing": t,
                                          "__builtin__": b}))
    b.Visit(visitors.VerifyNoExternalTypes())
    t.Visit(visitors.VerifyNoExternalTypes())
    b.Visit(visitors.VerifyLookup())
    t.Visit(visitors.VerifyLookup())
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
  # TODO(kramm): Fix circular import.
  from pytype.pytd import utils  # pylint: disable=g-import-not-at-top
  return utils.Concat(*GetBuiltinsAndTyping())


# TODO(kramm): Use python_version, once we have builtins for both Python 2 and
# Python 3.
def GetBuiltinsCode(unused_python_version):
  """Similar to GetBuiltinsPyTD, but for code in the .py file."""
  return _FindBuiltinFile("__builtin__", extension=".py")
