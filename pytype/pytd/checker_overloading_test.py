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
from pytype.pytd.tests import overloading
from pytype.pytd.tests import simple


class TestCheckerOverloading(unittest.TestCase):

  def testOverloadedArgsSimpleNoError(self):
    """Type checking a function that has two overloaded sigs."""
    # this should work normally
    self.assertEquals(42, overloading.Bar(1))
    self.assertEquals(42, overloading.Bar("a"))

  def testOverloadedArgsSimpleError(self):
    """Type checking a function that has two overloaded sigs.
    """
    expected = checker.OverloadingTypeErrorMsg("Bar")

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      overloading.Bar(1.0)

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testFibonnaciNoError(self):
    """Type checking of fib.
    """
    # should work no errors
    self.assertEquals(8, overloading.Fib(5))
    self.assertEquals(5, overloading.Fib(4.0))

  def testFibonnaciError(self):
    """Type checking of fib.
    """
    expected = checker.OverloadingTypeErrorMsg("Fib")

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      overloading.Fib("foo")

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testMultiOverloadingNoError(self):
    """Type checking of multiple argument sigs.
    """
    # this should work normally
    self.assertEquals(42, overloading.MultiOverload(42))
    self.assertEquals(42.0, overloading.MultiOverload(42.0))
    self.assertEquals("42", overloading.MultiOverload("42"))
    self.assertEquals([42], overloading.MultiOverload([42]))

  def testMultiOverloadingError(self):
    """Type checking of multiple argument sigs.
    """
    expected = checker.OverloadingTypeErrorMsg("MultiOverload")
    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      overloading.MultiOverload({})  # dict not supported

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testOverloadedExceptions(self):
    """Overloaded function with exceptions.
    """
    with self.assertRaises(simple.WrongException):
      overloading.ExceptionOverload()

if __name__ == "___main__":
  unittest.main()
