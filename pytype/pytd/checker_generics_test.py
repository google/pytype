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


import unittest
from pytype.pytd import checker
from pytype.pytd.tests import generics


class TestCheckerGenerics(unittest.TestCase):

  def testSimpleList(self):
    """Type checking of a list of int."""

    # should work with no exceptions
    self.assertEquals(3, generics.Length([1, 2, 3]))

    with self.assertRaises(checker.CheckTypeAnnotationError):
      generics.Length(["42", 1])

    with self.assertRaises(checker.CheckTypeAnnotationError):
      generics.Length(["abc", 1, 3])

  def testUserContainerClass(self):
    """Type checking of a container class."""

    self.assertEquals(1, generics.UnwrapBox(generics.Box(1)))

    with self.assertRaises(checker.CheckTypeAnnotationError):
      generics.UnwrapBox(generics.Box("hello"))

  def testDict(self):
    """Type checking of built-in dict."""
    cache = {"Albert": 1, "Greg": 2, "Peter": 3}

    self.assertEquals(1, generics.FindInCache(cache, "Albert"))

    with self.assertRaises(checker.CheckTypeAnnotationError):
      generics.FindInCache(cache, 9999)

  def testGenSimple(self):
    """Type checking of typed generator."""

    self.assertEquals([1, 2], generics.ConvertGenToList(
        e for e in [1, 2]))

    gen = generics._BadGen()
    with self.assertRaises(checker.CheckTypeAnnotationError):
      generics.ConvertGenToList(gen)

  def testSameGenAsTwoArgs(self):
    """Passing same generator twice."""

    gen = (e for e in [1, 2, 3, 4, 5, 6])
    self.assertEquals([], generics.ConsumeDoubleGenerator(gen, gen))

    gen_broken = (e for e in [1, 2, 3, 4, 5, "6"])
    with self.assertRaises(checker.CheckTypeAnnotationError):
      generics.ConsumeDoubleGenerator(gen_broken, gen_broken)


if __name__ == "__main__":
  unittest.main()
