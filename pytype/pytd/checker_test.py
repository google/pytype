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


import types
import unittest
from pytype.pytd import checker
from pytype.pytd.tests import simple


class TestChecker(unittest.TestCase):

  def testSimpleArgTypeNoError(self):
    """Type checking of function with single argument."""
    # there should be no exceptions thrown
    result = simple.IntToInt(2)
    self.assertEquals(42, result)

  def testSimpleArgTypeError(self):
    """Type checking of function with single argument.
    """
    # there should be a type error exception

    expected = checker.ParamTypeErrorMsg("IntToInt", "i", str, int)

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.IntToInt("test")

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testMultiArgTypeError(self):
    """Type checking of function with multiple argument.
    """
    # there should be a type error exception

    expected_a = checker.ParamTypeErrorMsg("MultiArgs", "a", str, int)
    expected_c = checker.ParamTypeErrorMsg("MultiArgs", "c", int, dict)
    expected_d = checker.ParamTypeErrorMsg("MultiArgs", "d", dict, str)

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.MultiArgs("test", 1, 2, {})

    a, c, d = context.exception.args[0]
    self.assertEquals(expected_a, a)
    self.assertEquals(expected_c, c)
    self.assertEquals(expected_d, d)

  def testReturnTypeNoError(self):
    """Type checking of return type of function.
    """
    res = simple.GoodRet()
    self.assertEquals(type(res), int)

  def testReturnTypeError(self):
    """Type checking of return type of function.
    """

    expected = checker.ReturnTypeErrorMsg("BadRet", str, int)

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.BadRet()

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testReturnNone(self):
    """Type checking of return type of function with None.
    """

    expected = checker.ReturnTypeErrorMsg("NoneRet", list, types.NoneType)

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.NoneRet()

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testReturnAClassType(self):
    """Type checking of return type of a function returning a class type.
    """

    expected = checker.ReturnTypeErrorMsg("AppleRet",
                                          simple.Banana,
                                          simple.Apple)

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.AppleRet()

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testExceptionCorrect(self):
    """Type checking of exception: the correct exception is thrown.
    """
    with self.assertRaises(simple.FooException):
      simple.FooFail()

  def testExceptionListCorrect(self):
    """Type checking of exception: one correct exception from a list.
    """
    with self.assertRaises(simple.WrongException):
      simple.WrongFail()

  def testExceptionIncorrect(self):
    """Type checking of exception: incorrect exception thrown.
    """

    expected = checker.ExceptionTypeErrorMsg(
        "BadFail",
        simple.BadException,
        (simple.FooException, simple.WrongException))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.BadFail()

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testMultiTypeErrors(self):
    """Type checking of params and exceptions.
    """

    expected_a = checker.ParamTypeErrorMsg("MultiFail",
                                           "a",
                                           simple.Banana,
                                           simple.Apple)
    expected_e = checker.ExceptionTypeErrorMsg(
        "MultiFail",
        simple.BadException,
        (simple.FooException,))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.MultiFail(simple.Banana())

    a, e = context.exception.args[0]
    self.assertEquals(expected_a, a)
    self.assertEquals(expected_e, e)

  def testOptionalTypeParam(self):
    """Type checking with params without type.
    """
    self.assertEquals(1, simple.MultiArgsNoType(1, 2, 3, "4", []))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      simple.MultiArgsNoType(1, 2, 3, 4, 5)

    expected_p = checker.ParamTypeErrorMsg("MultiArgsNoType",
                                           "d",
                                           int,
                                           str)

    [actual] = context.exception.args[0]
    self.assertEquals(expected_p, actual)


if __name__ == "__main__":
  unittest.main()
