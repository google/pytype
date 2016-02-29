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

import os
import sys
import textwrap
from pytype.pytd import pytd
from pytype.pytd.parse import parser
from pytype.pytd.parse import visitors
import unittest


class ParserTest(unittest.TestCase):
  """Test utility class. Knows how to parse PYTD and compare source code."""

  def setUp(self):
    self.parser = parser.TypeDeclParser()

  def Parse(self, src, version=None):
    # TODO(kramm): Using self.parser here breaks tests. Why?
    tree = parser.TypeDeclParser(version=version).Parse(textwrap.dedent(src))
    tree.Visit(visitors.VerifyVisitor())
    return tree

  def ToAST(self, src_or_tree):
    # TODO(pludemann): The callers are not consistent in how they use this
    #                  and in most (all?) cases they know whether they're
    #                  passing in a source string or parse tree. It would
    #                  be better if all the calles were consistent.
    if isinstance(src_or_tree, basestring):
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
    # TODO(pludemann): Find out why some tests leave confuse NamedType and
    #                  ClassType and fix the tests so that this conversion isn't
    #                  needed.
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
        print >>sys.stderr, "Source files or ASTs differ:"
        print >>sys.stderr, "-" * 36, " Actual ", "-" * 36
        print >>sys.stderr, textwrap.dedent(src1).strip()
        print >>sys.stderr, "-" * 36, "Expected", "-" * 36
        print >>sys.stderr, textwrap.dedent(src2).strip()
        print >>sys.stderr, "-" * 80
      if not ast1.ASTeq(ast2):
        print >>sys.stderr, "Actual AST:", ast1
        print >>sys.stderr, "Expect AST:", ast2
      self.fail("source files differ")

  def ApplyVisitorToString(self, data, visitor):
    tree = self.Parse(data)
    new_tree = tree.Visit(visitor)
    return pytd.Print(new_tree)
