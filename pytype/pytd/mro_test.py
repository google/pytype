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


import textwrap

from pytype import load_pytd
from pytype.pyi import parser
from pytype.pytd import mro
from pytype.pytd import visitors
from pytype.pytd.parse import parser_test_base
import unittest


class MroTest(parser_test_base.ParserTest):
  """Test pytype.pytd.mro."""

  def test_dedup(self):
    self.assertEqual([], mro.Dedup([]))
    self.assertEqual([1], mro.Dedup([1]))
    self.assertEqual([1, 2], mro.Dedup([1, 2]))
    self.assertEqual([1, 2], mro.Dedup([1, 2, 1]))
    self.assertEqual([1, 2], mro.Dedup([1, 1, 2, 2]))
    self.assertEqual([3, 2, 1], mro.Dedup([3, 2, 1, 3]))

  def test_mro_merge(self):
    self.assertEqual([], mro.MROMerge([[], []]))
    self.assertEqual([1], mro.MROMerge([[], [1]]))
    self.assertEqual([1], mro.MROMerge([[1], []]))
    self.assertEqual([1, 2], mro.MROMerge([[1], [2]]))
    self.assertEqual([1, 2], mro.MROMerge([[1, 2], [2]]))
    self.assertEqual([1, 2, 3, 4], mro.MROMerge([[1, 2, 3], [2, 4]]))
    self.assertEqual([1, 2, 3], mro.MROMerge([[1, 2], [1, 2, 3]]))
    self.assertEqual([1, 2], mro.MROMerge([[1, 1], [2, 2]]))
    self.assertEqual([1, 2, 3, 4, 5, 6],
                     mro.MROMerge([[1, 3, 5], [2, 3, 4], [4, 5, 6]]))
    self.assertEqual([1, 2, 3], mro.MROMerge([[1, 2, 1], [2, 3, 2]]))

  def test_get_bases_in_mro(self):
    ast = parser.parse_string(textwrap.dedent("""
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class Foo(Generic[T]): pass
      class Bar(Foo[int]): pass
    """), python_version=self.python_version)
    ast = ast.Visit(visitors.AdjustTypeParameters())
    loader = load_pytd.Loader(None, self.python_version)
    ast = loader.resolve_ast(ast)
    bases = mro.GetBasesInMRO(ast.Lookup("Bar"), lookup_ast=ast)
    self.assertListEqual(["Foo", "typing.Generic", "__builtin__.object"],
                         [t.name for t in bases])


if __name__ == "__main__":
  unittest.main()
