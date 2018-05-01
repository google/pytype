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

"""Utility classes for testing the PYTD parser."""
from __future__ import print_function

import os
import sys
import textwrap

from pytype import load_pytd
from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import visitors
import six
import unittest


class ParserTest(unittest.TestCase):
  """Test utility class. Knows how to parse PYTD and compare source code."""

  PYTHON_VERSION = (2, 7)

  @classmethod
  def setUpClass(cls):
    cls.loader = load_pytd.Loader(None, cls.PYTHON_VERSION)

  def Parse(self, src, name=None, version=None, platform=None):
    version = version or self.PYTHON_VERSION
    tree = parser.parse_string(
        textwrap.dedent(src), name=name, python_version=version,
        platform=platform)
    tree = tree.Visit(visitors.NamedTypeToClassType())
    tree = tree.Visit(visitors.AdjustTypeParameters())
    # Convert back to named types for easier testing
    tree = tree.Visit(visitors.ClassTypeToNamedType())
    tree.Visit(visitors.VerifyVisitor())
    return tree

  def ParseWithBuiltins(self, src):
    ast = parser.parse_string(textwrap.dedent(src),
                              python_version=self.PYTHON_VERSION)
    ast = ast.Visit(visitors.LookupExternalTypes(
        {"__builtin__": self.loader.builtins, "typing": self.loader.typing}))
    ast = ast.Visit(visitors.NamedTypeToClassType())
    ast = ast.Visit(visitors.AdjustTypeParameters())
    ast.Visit(visitors.FillInLocalPointers({
        "": ast, "__builtin__": self.loader.builtins}))
    ast.Visit(visitors.VerifyVisitor())
    return ast

  def ToAST(self, src_or_tree):
    if isinstance(src_or_tree, six.string_types):
      # Put into a canonical form (removes comments, standard indents):
      return self.Parse(src_or_tree + "\n")
    else:  # isinstance(src_or_tree, tuple):
      src_or_tree.Visit(visitors.VerifyVisitor())
      return src_or_tree

  def AssertSourceEquals(self, src_or_tree_1, src_or_tree_2):
    # Strip leading "\n"s for convenience
    ast1 = self.ToAST(src_or_tree_1)
    ast2 = self.ToAST(src_or_tree_2)
    src1 = pytd.Print(ast1).strip() + "\n"
    src2 = pytd.Print(ast2).strip() + "\n"
    # Verify printed versions are the same and ASTs are the same.
    ast1 = ast1.Visit(visitors.ClassTypeToNamedType())
    ast2 = ast2.Visit(visitors.ClassTypeToNamedType())
    if src1 != src2 or not ast1.ASTeq(ast2):
      # Due to differing opinions on the form of debug output, allow an
      # environment variable to control what output you want. Set
      # PY_UNITTEST_DIFF to get diff output.
      if os.getenv("PY_UNITTEST_DIFF"):
        self.maxDiff = None  # for better diff output (assertMultiLineEqual)
        self.assertMultiLineEqual(src1, src2)
      else:
        sys.stdout.flush()
        sys.stderr.flush()
        print("Source files or ASTs differ:", file=sys.stderr)
        print("-" * 36, " Actual ", "-" * 36, file=sys.stderr)
        print(textwrap.dedent(src1).strip(), file=sys.stderr)
        print("-" * 36, "Expected", "-" * 36, file=sys.stderr)
        print(textwrap.dedent(src2).strip(), file=sys.stderr)
        print("-" * 80, file=sys.stderr)
      if not ast1.ASTeq(ast2):
        print("Actual AST:", ast1, file=sys.stderr)
        print("Expect AST:", ast2, file=sys.stderr)
      self.fail("source files differ")

  def ApplyVisitorToString(self, data, visitor):
    tree = self.Parse(data)
    new_tree = tree.Visit(visitor)
    return pytd.Print(new_tree)
