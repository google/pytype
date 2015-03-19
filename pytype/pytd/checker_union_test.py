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
from pytype.pytd import pytd
from pytype.pytd.tests import simple
from pytype.pytd.tests import union


class TestCheckerUnion(unittest.TestCase):

  def testSimpleArgNoneAble(self):
    """Type checking of function with none-able argument."""
    # should work with no exceptions
    self.assertEquals(0, union.StrToInt(None))
    self.assertEquals(10, union.StrToInt("10"))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.StrToInt(10)  # can only pass str? so this should be an error

    expected = checker.ParamTypeErrorMsg("StrToInt",
                                         "s",
                                         int,
                                         pytd.UnionType([str, type(None)]))

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testNoneAbleAdd(self):
    """Type checking of function with None-able args, return and overloading.
    """

    self.assertEquals(None, union.Add(None, 4))
    self.assertEquals(None, union.Add(10.0, None))
    self.assertEquals(10, union.Add(5, 5))
    self.assertEquals(10.0, union.Add(5.0, 5.0))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.Add([1], None)  # list not in signature

    expected = checker.OverloadingTypeErrorMsg("Add")

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testUnionSimple(self):
    """Type checking of function with union args.
    """
    self.assertEquals(42.0, union.IntOrFloat(1, 2.0))
    self.assertEquals(42.0, union.IntOrFloat(1.0, 2))

  def testUnionError(self):
    """Type checking of function with union args (error).
    """

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.IntOrFloat("1", 2)

    expected = checker.ParamTypeErrorMsg("IntOrFloat",
                                         "a",
                                         str,
                                         pytd.UnionType([int, float]))

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testUnionNone(self):
    """Type checking of function with None union.
    """
    self.assertEquals(3, union.IntOrNone(3))
    self.assertEquals(None, union.IntOrNone(None))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.IntOrNone("error")

    expected_param = checker.ParamTypeErrorMsg("IntOrNone",
                                               "a",
                                               str,
                                               pytd.UnionType([int,
                                                               type(None)]))

    expected_ret = checker.ReturnTypeErrorMsg("IntOrNone",
                                              str,
                                              pytd.UnionType([int,
                                                              type(None)]))

    [actual_param, actual_ret] = context.exception.args[0]
    self.assertEquals(expected_param, actual_param)
    self.assertEquals(expected_ret, actual_ret)

  def testUnionWithClassTypes(self):
    """Type checking of function with union and class types.
    """

    self.assertEquals(None, union.AppleOrBananaOrOrange(simple.Apple()))
    self.assertEquals(None, union.AppleOrBananaOrOrange(simple.Banana()))
    self.assertEquals(None, union.AppleOrBananaOrOrange(simple.Orange()))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.AppleOrBananaOrOrange(42)

    expected = checker.ParamTypeErrorMsg("AppleOrBananaOrOrange",
                                         "f",
                                         int,
                                         pytd.UnionType([simple.Apple,
                                                         simple.Banana,
                                                         simple.Orange]))

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testUnionInReturnOK(self):
    """Typechecking fct with union in return type.
    """
    self.assertEquals([42], union.UnionReturn())

  def testUnionInReturnError(self):
    """Typechecking fct with union in return type (error).
    """
    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.UnionReturnError()

    expected = checker.ReturnTypeErrorMsg("UnionReturnError",
                                          tuple,
                                          pytd.UnionType([int, list]))

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testIntersectionSimple(self):
    """Typechecking fct with intersection types.
    """
    self.assertEquals("cool", union.DoSomeIOStuff(union.File()))

  def testIntersectionError(self):
    """Typechecking fct with intersection types (error).
    """
    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      union.DoSomeIOStuff(union.Readable())  # we want Readable & Writable

    expected = checker.ParamTypeErrorMsg("DoSomeIOStuff",
                                         "f",
                                         union.Readable,
                                         pytd.IntersectionType(
                                             [union.Readable,
                                              union.Writable]))

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  # TODO(raoulDoc): more tests! mixing overloading etc


if __name__ == "__main__":
  unittest.main()
