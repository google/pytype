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


# def Length(l : list<int>) -> int
def Length(l):
  return len(l)


class Box(object):

  def __init__(self, data):
    self.data = data

  def Get(self):
    return self.data

  def __iter__(self):
    return iter([self.data])


# def UnwrapBox(b: Box<int>) -> int
def UnwrapBox(b):
  return b.Get()


# def FindInCache(cache: dict<str, int>, k: str) -> int
def FindInCache(cache, k):
  return cache[k]


# def _BadGen() -> generator
def _BadGen():
  """This is *supposed* to yield integers..."""
  for num in [1, 2, 3.1414926, 4]:
    yield num


# def ConvertGenToList(g: generator<int>) -> list<int>
def ConvertGenToList(g):
  return list(g)


def ConsumeDoubleGenerator(g1, g2):

  l1 = [e for e in g1]
  l2 = [e for e in g2]
  return l2

checker.CheckFromFile(sys.modules[__name__], __file__ + "td")
