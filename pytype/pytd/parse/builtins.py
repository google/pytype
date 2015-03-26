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

import os.path

from pytype.pytd import utils
from pytype.pytd.parse import parser


# We list modules explicitly, because we might have to extract them out of
# a PAR file, which doesn't have good support for listing directories.
_MODULES = ["array", "codecs", "errno", "fcntl", "gc", "itertools", "marshal",
            "os", "posix", "pwd", "select", "signal", "_sre", "StringIO",
            "strop", "_struct", "sys", "_warnings", "warnings", "_weakref"]


def _FindBuiltinFile(name):
  return utils.GetDataFile(os.path.join("builtins", name))


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
  if _cached_builtins_pytd:
    return _cached_builtins_pytd
  _cached_builtins_pytd = builtins_pytd = parser.TypeDeclParser().Parse(
      _FindBuiltinFile(_BUILTIN_NAME + ".pytd"), name=_BUILTIN_NAME)
  return builtins_pytd


# TODO(kramm): Use python_version, once we have builtins for both Python 2 and
# Python 3.
def GetBuiltinsCode(unused_python_version):
  """Similar to GetBuiltinsPyTD, but for code in the .py file."""
  return _FindBuiltinFile(_BUILTIN_NAME + ".py")
