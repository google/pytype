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


# def IntToInt(i :int) -> int
def IntToInt(i):
  return 42


# def MultiArgs(a : int, b: int, c:str, d: str) -> None
def MultiArgs(a, b, c, d):
  return None


# def GoodRet() -> int
def GoodRet():
  return 42


# def BadRet() -> int
def BadRet():
  return "I want integer"


# def NoneRet() -> None
def NoneRet():
  return [1337]


class Apple(object):
  pass


class Banana(object):
  pass


class Orange(object):
  pass


# def AppleRet() -> Apple
def AppleRet():
  return Banana()  # Intentionally returning the wrong type


class FooException(Exception):
  pass


class WrongException(Exception):
  pass


class BadException(Exception):
  pass


# def FooFail() -> None raise FooException
def FooFail():
  raise FooException


# def WrongFail() -> None raise FooException, WrongException
def WrongFail():
  raise WrongException


# def BadFail() -> None raise FooException, WrongException
def BadFail():
  raise BadException


# def MultiFail(a: Apple) -> None raise FooException
def MultiFail(a):
  raise BadException


# def MultiArgsNoType(a: int, b, c, d: str, e) -> int
def MultiArgsNoType(a, b, c, d, e):
  return a

checker.CheckFromFile(sys.modules[__name__], __file__ + "td")
