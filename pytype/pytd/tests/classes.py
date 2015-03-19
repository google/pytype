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


"""Used for tests."""

# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=g-line-too-long
# pylint: disable=unused-variable

import sys
from pytype.pytd import checker


class Emailer(object):

  def MakeAnnouncement(self, emails):
    for addr in emails:
      self.SendEmail(addr)

  def SendEmail(self, addr):
    return "sending email to " + addr

  @classmethod
  def GetServerInfo(cls, port):
    return "smtp.server.com:" + str(port)


class Utils(object):
  # Overloaded signatures
  # def Repeat(self, s: str, number: int) -> str
  # def Repeat(self, s: str, number: float) -> str

  def Repeat(self, s, number):
    return s * int(number)


class Comparators(object):

  # def isGreater(a: int, b: int) -> bool

  @classmethod
  def IsGreater(cls, a, b):
    return a > b


checker.CheckFromFile(sys.modules[__name__], __file__ + "td")
