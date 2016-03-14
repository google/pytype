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


"""Utilities for getting a predefined file."""

import os


def GetPredefinedFile(pytd_subdir, module, extension=".pytd"):
  """Get the contents of a predefined PyTD, typically with a file name *.pytd.

  Arguments:
    pytd_subdir: the directory, typically "builtins" or "stdlib"
    module: module name (e.g., "sys" or "__builtins__")
    extension: either ".pytd" or ".py"
  Returns:
    The contents of the file
  Raises:
    IOError: if file not found
  """
  path = os.path.join(os.path.dirname(__file__),
                      pytd_subdir, os.path.join(*module.split(".")) + extension)
  with open(path, "rb") as fi:
    return fi.read()
