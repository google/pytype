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


import os
import unittest
from pytype.pytd import data_files
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import parser_test_base


class TestDataFiles(parser_test_base.ParserTest):
  """Test data_filess.py."""

  def testGetPredefinedFileReturnsString(self):
    # smoke test, only checks that it doesn't throw and the result is a string
    self.assertIsInstance(
        data_files.GetPredefinedFile("builtins", "__builtin__"),
        str)

  def testGetPredefinedFileThrows(self):
    # smoke test, only checks that it does throw
    with self.assertRaisesRegexp(
        IOError,
        r"File not found|Resource not found|No such file or directory"):
      data_files.GetPredefinedFile("builtins", "-this-file-does-not-exist")

  def testPytdBuiltin(self):
    """Verify 'import sys'."""
    import_contents = data_files.GetPredefinedFile("builtins", "sys")
    with open(os.path.join(os.path.dirname(pytd.__file__),
                           "builtins", "sys.pytd"), "rb") as fi:
      file_contents = fi.read()
    self.assertMultiLineEqual(import_contents, file_contents)


if __name__ == "__main__":
  unittest.main()
