# Copyright 2016 Google Inc. All Rights Reserved.
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


from pytype.pytd.parse import preconditions

import unittest


class BaseClass(object):
  pass


class SubClass(BaseClass):
  pass


class PreconditionsTest(unittest.TestCase):

  def assertError(self, regex, condition, value):
    self.assertRaisesRegexp(
        preconditions.PreconditionError, regex, condition.check, value)

  def testClassNamePrecondition(self):
    c = preconditions._ClassNamePrecondition("str")
    self.assertEqual({"str"}, c.allowed_types())
    c.check("abc")
    self.assertError("actual=int.*expected=str", c, 1)

  def testTuplePrecondition(self):
    c = preconditions._TuplePrecondition(
        preconditions._ClassNamePrecondition("int"))
    self.assertEqual({"int"}, c.allowed_types())
    c.check(())
    c.check((1,))
    c.check((1, 2))
    self.assertError("actual=int.*expected=tuple", c, 1)

  def testOrPrecondition(self):
    c = preconditions._OrPrecondition([
        preconditions._ClassNamePrecondition("int"),
        preconditions._ClassNamePrecondition("str")])
    self.assertEqual({"int", "str"}, c.allowed_types())
    c.check(1)
    c.check("abc")
    self.assertError(
        "actual=float.*expected=int.*actual=float.*expected=str",
        c, 1.23)

  def testIsInstancePrecondition(self):
    c = preconditions._IsInstancePrecondition(BaseClass)
    self.assertEqual({BaseClass}, c.allowed_types())
    c.check(BaseClass())
    c.check(SubClass())
    self.assertError("actual=str.*expected_superclass=BaseClass", c, "foo")


class CallCheckerTest(unittest.TestCase):

  def setUp(self):
    self.checker = preconditions.CallChecker([
        ("x", preconditions._ClassNamePrecondition("int")),
        ("s", preconditions._ClassNamePrecondition("str"))])

  def testAllowedTypes(self):
    self.assertEqual({"int", "str"}, self.checker.allowed_types())

  def assertError(self, regex, *args, **kwargs):
    self.assertRaisesRegexp(
        preconditions.PreconditionError, regex, self.checker.check, *args,
        **kwargs)

  def testPositionalArgs(self):
    self.checker.check(1, "abc")
    self.assertError("argument=x.*actual=str.*expected=int", "a", "b")
    self.assertError("argument=s.*actual=int.*expected=str", 1, 2)

  def testKeywordArgs(self):
    self.checker.check(1, s="abc")
    self.checker.check(s="abc", x=1)
    self.assertError("argument=x.*actual=str.*expected=int", x="xyz", s="aaa")
    self.assertError("argument=s.*actual=int.*expected=str", s=1, x=2)


class ParserTest(unittest.TestCase):

  def assertClassName(self, class_name, condition):
    self.assertIsInstance(condition, preconditions._ClassNamePrecondition)
    self.assertEqual(class_name, condition._class_name)

  def assertOr(self, names, condition):
    def get_name(c):
      self.assertIsInstance(c, preconditions._ClassNamePrecondition)
      return c._class_name

    self.assertIsInstance(condition, preconditions._OrPrecondition)
    self.assertEqual(names, [get_name(c) for c in condition._choices])

  def testName(self):
    self.assertClassName("Foo", preconditions.parse("Foo"))

  def testIsInstance(self):
    saved = dict(preconditions._REGISTERED_CLASSES)
    try:
      # Can't parse class until it is registered.
      self.assertRaises(ValueError, preconditions.parse, "{BaseClass}")
      # Check parsed condition.
      preconditions.register(BaseClass)
      condition = preconditions.parse("{BaseClass}")
      self.assertIsInstance(condition, preconditions._IsInstancePrecondition)
      self.assertEqual(BaseClass, condition._cls)
      # Can't re-register a class.
      self.assertRaises(AssertionError, preconditions.register, BaseClass)
    finally:
      # Leave the world as we found it.
      preconditions._REGISTERED_CLASSES = saved

  def testNone(self):
    self.assertClassName("NoneType", preconditions.parse("None"))

  def testTuple(self):
    c = preconditions.parse("tuple[int]")
    self.assertIsInstance(c, preconditions._TuplePrecondition)
    self.assertClassName("int", c._element_condition)

  def testOr(self):
    self.assertOr(["int", "str", "float"],
                  preconditions.parse("int or str or float"))

  def testTupleAndOr(self):
    c = preconditions.parse("None or tuple[int or str]")
    self.assertIsInstance(c, preconditions._OrPrecondition)
    c1, c2 = c._choices
    self.assertClassName("NoneType", c1)
    self.assertIsInstance(c2, preconditions._TuplePrecondition)
    self.assertOr(["int", "str"], c2._element_condition)

  def testErrors(self):
    self.assertRaises(ValueError, preconditions.parse, "")
    self.assertRaises(ValueError, preconditions.parse, "or")
    self.assertRaises(ValueError, preconditions.parse, "a or")
    self.assertRaises(ValueError, preconditions.parse, "tuple")
    self.assertRaises(ValueError, preconditions.parse, "tuple[")
    self.assertRaises(ValueError, preconditions.parse, "tuple[]")
    self.assertRaises(ValueError, preconditions.parse, "?")

  def testParseArg(self):
    self.assertEqual(("x", None), preconditions.parse_arg("x"))
    name, cond = preconditions.parse_arg("foo: str")
    self.assertEqual("foo", name)
    self.assertClassName("str", cond)


if __name__ == "__main__":
  unittest.main()
