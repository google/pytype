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


"""A demo which uses types to find an error."""

import sys
from pytype.pytd import checker


class Emailer(object):
  """An dummy emailer class.
  """

  @classmethod
  def MakeAnnouncement(cls, emails):
    for addr in emails:
      cls.SendEmail(addr)

  @classmethod
  def SendEmail(cls, addr):
    print "sending email to " + addr

  def Hello(self):
    print "hello"

  def Bonjour(self):
    print "bonjour"


checker.CheckFromFile(sys.modules[__name__], __file__ + "td")
