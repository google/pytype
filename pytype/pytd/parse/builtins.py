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


# Keyed by the parameter(s) passed to GetBuiltinsPyTD:
_cached_builtins_pytd = None  # ... => pytype.pytd.pytd.TypeDeclUnit


_BUILTIN_NAME = "__builtin__"


def GetBuiltinsPyTD():
  """Get the "default" AST used to lookup built in types.

  Get an AST for all Python builtins as well as the most commonly used standard
  libraries.

  Returns:
    A pytd.TypeDeclUnit instance. It'll directly contain the builtin classes
    and functions, and submodules for each of the standard library modules.
  """
  global _cached_builtins_pytd
  if not _cached_builtins_pytd:
    builtins_pytd = parser.TypeDeclParser().Parse(
        _FindBuiltinFile(_BUILTIN_NAME),
        name=_BUILTIN_NAME)
    _cached_builtins_pytd = visitors.LookupClasses(builtins_pytd)
  return _cached_builtins_pytd


# TODO(kramm): Use python_version, once we have builtins for both Python 2 and
# Python 3.
def GetBuiltinsCode(unused_python_version):
  """Similar to GetBuiltinsPyTD, but for code in the .py file."""
  return _FindBuiltinFile(_BUILTIN_NAME, extension=".py")
