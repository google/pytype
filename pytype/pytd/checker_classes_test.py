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
from pytype.pytd.tests import classes


class TestCheckerClasses(unittest.TestCase):

  def testEmailer(self):
    emailer = classes.Emailer()
    page_email = "nobody@example.com"
    expected_msg = "sending email to " + page_email
    self.assertEquals(expected_msg, emailer.SendEmail(page_email))

    # NOTE: We only check that we get the correct type of exception, but don't
    # verify the attributes of the exception (error message string etc.)
    # In theory, we might miss things (complaining about the wrong type, or
    # for the wrong reason), but tests are way too flaky if we depend on the
    # exact format of an exception message string.

    with self.assertRaises(checker.CheckTypeAnnotationError):
      emailer.MakeAnnouncement("nobody@example.com")

    with self.assertRaises(checker.CheckTypeAnnotationError):
      classes.Emailer.GetServerInfo("25")

  def testUtils(self):
    utils = classes.Utils()
    self.assertEquals("aaa", utils.Repeat("a", 3.0))

    with self.assertRaises(checker.CheckTypeAnnotationError) as context:
      utils.Repeat("a", "3")

    expected = checker.OverloadingTypeErrorMsg("Repeat")

    [actual] = context.exception.args[0]
    self.assertEquals(expected, actual)

  def testComparators(self):

    self.assertTrue(classes.Comparators.IsGreater(20, 10))

    # call using with class name
    with self.assertRaises(checker.CheckTypeAnnotationError):
      classes.Comparators.IsGreater("20", 10)

    # call using instance of comparators
    comparators = classes.Comparators()
    with self.assertRaises(checker.CheckTypeAnnotationError):
      comparators.IsGreater(20, "10")


if __name__ == "__main__":
  unittest.main()
