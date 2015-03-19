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

from pytype.pyc import pyc
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
_cached_builtins_pytd = {}  # ... => pytype.pytd.pytd.TypeDeclUnit


_BUILTIN_NAME = "__builtin__"


def GetBuiltinsPyTD(stdlib=True):
  """Get the "default" AST used to lookup built in types.

  Get an AST for all Python builtins as well as the most commonly used standard
  libraries.

  Args:
    stdlib: Whether to load the standard library, too. If this is False,
      TypeDeclUnit.modules will be empty. If it's True, it'll contain modules
      like itertools and signal.

  Returns:
    A pytd.TypeDeclUnit instance. It'll directly contain the builtin classes
    and functions, and submodules for each of the standard library modules.
  """
  cache_key = stdlib
  if cache_key in _cached_builtins_pytd:
    return _cached_builtins_pytd[cache_key]
  # TODO(pludemann): This can be fairly slow; suggest pickling the result and
  #                  reusing if possible (see lib2to3.pgen2.grammar)

  # We use the same parser instance to parse all builtin files. This changes
  # the run time from 1.0423s to 0.5938s (for 21 builtins).
  p = parser.TypeDeclParser()
  builtins_pytd = p.Parse(
      _FindBuiltinFile(_BUILTIN_NAME + ".pytd"), name=_BUILTIN_NAME)
  if stdlib:
    builtins_pytd = builtins_pytd.Replace(
        modules=tuple(p.Parse(_FindBuiltinFile(mod + ".pytd"),
                              filename=mod + ".pytd", name=mod)
                      for mod in _MODULES))
  _cached_builtins_pytd[cache_key] = builtins_pytd
  return builtins_pytd


# Keyed by the parameter(s) passed to GetBuiltinsPyTD:
_cached_builtins_code = {}  # ... => list<pytype.pyc.loadmarshal.CodeType>

PYTHON_VERSION = (2, 7)  # TODO(pludemann): parameter or FLAG


def GetBuiltinsCode(stdlib=True):
  """Similar to GetBuiltinsPyTD, but for code in the .py file."""

  cache_key = stdlib
  if cache_key in _cached_builtins_code:
    return _cached_builtins_code[cache_key]
  # TODO(pludemann): This can be fairly slow; suggest pickling the result and
  #                  reusing if possible (see lib2to3.pgen2.grammar)

  filename = _BUILTIN_NAME + ".py"
  builtins_code = [pyc.compile_and_load(_FindBuiltinFile(filename),
                                        python_version=PYTHON_VERSION,
                                        filename=filename)]
  # TODO(pludemann): add support for .py files in _MODULES:
  #   ... see similar code in GetBuiltinsPyTD, but we need to check
  #       for the existence of each .py file
  _cached_builtins_code[cache_key] = builtins_code
  return builtins_code
