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
import checker_classes_test
import checker_generics_test
import checker_overloading_test
import checker_test
import checker_union_test
from parse import ast_test


def suite():

  # ast tests
  # TODO(pludemann): can this be simplified using test discovery?

  ast_generation = unittest.TestLoader().loadTestsFromTestCase(
      ast_test.TestASTGeneration)
  tuple_eq = unittest.TestLoader().loadTestsFromTestCase(ast_test.TestTupleEq)

  # checker tests
  classes = unittest.TestLoader().loadTestsFromTestCase(
      checker_classes_test.TestCheckerClasses)
  generics = unittest.TestLoader().loadTestsFromTestCase(
      checker_generics_test.TestCheckerGenerics)
  overloading = unittest.TestLoader().loadTestsFromTestCase(
      checker_overloading_test.TestCheckerOverloading)
  simple = unittest.TestLoader().loadTestsFromTestCase(checker_test.TestChecker)
  union = unittest.TestLoader().loadTestsFromTestCase(
      checker_union_test.TestCheckerUnion)

  all_tests = [ast_generation, tuple_eq, classes, generics, overloading,
               simple, union]

  return unittest.TestSuite(all_tests)


if __name__ == "__main__":
  unittest.TextTestRunner().run(suite())
