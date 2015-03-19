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

import sys
from pytype.pytd import checker
from pytype.pytd.tests import simple


# def Bar(i :int) -> int
# def Bar(i :str) -> int
def Bar(i):
  return 42


# def Fib(n: int) -> int
# def Fib(n: float) -> int
def Fib(n):
  if n == 1:
    return 1
  elif n == 2:
    return 2
  else:
    return Fib(n - 1) + Fib(n - 2)


# def MultiOverload(a: int) -> int
# def MultiOverload(a: float) -> float
# def MultiOverload(a: str) -> str
# def MultiOverload(a : list) -> list
def MultiOverload(a):
  return a


# def ExceptionOverload() -> None raise foo.WrongException
# def ExceptionOverload() -> None raise foo.BadException
def ExceptionOverload():
  raise simple.WrongException

checker.CheckFromFile(sys.modules[__name__], __file__ + "td")
