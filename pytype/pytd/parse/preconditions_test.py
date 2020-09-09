from pytype.pytd.parse import preconditions
import six

import unittest


class BaseClass:
  pass


class SubClass(BaseClass):
  pass


class PreconditionsTest(unittest.TestCase):

  def assertError(self, regex, condition, value):
    six.assertRaisesRegex(
        self, preconditions.PreconditionError, regex, condition.check, value)

  def test_class_name_precondition(self):
    c = preconditions._ClassNamePrecondition("str")
    self.assertEqual({"str"}, c.allowed_types())
    c.check("abc")
    self.assertError("actual=int.*expected=str", c, 1)

  def test_tuple_precondition(self):
    c = preconditions._TuplePrecondition(
        preconditions._ClassNamePrecondition("int"))
    self.assertEqual({"int"}, c.allowed_types())
    c.check(())
    c.check((1,))
    c.check((1, 2))
    self.assertError("actual=int.*expected=tuple", c, 1)

  def test_or_precondition(self):
    c = preconditions._OrPrecondition([
        preconditions._ClassNamePrecondition("int"),
        preconditions._ClassNamePrecondition("str")])
    self.assertEqual({"int", "str"}, c.allowed_types())
    c.check(1)
    c.check("abc")
    self.assertError(
        "actual=float.*expected=int.*actual=float.*expected=str",
        c, 1.23)

  def test_is_instance_precondition(self):
    c = preconditions._IsInstancePrecondition(BaseClass)
    self.assertEqual({BaseClass}, c.allowed_types())
    c.check(BaseClass())
    c.check(SubClass())
    self.assertError("actual=str.*expected_superclass=BaseClass", c, "foo")


class CallCheckerTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.checker = preconditions.CallChecker([
        ("x", preconditions._ClassNamePrecondition("int")),
        ("s", preconditions._ClassNamePrecondition("str"))])

  def test_allowed_types(self):
    self.assertEqual({"int", "str"}, self.checker.allowed_types())

  def assertError(self, regex, *args, **kwargs):
    six.assertRaisesRegex(
        self, preconditions.PreconditionError, regex, self.checker.check, *args,
        **kwargs)

  def test_positional_args(self):
    self.checker.check(1, "abc")
    self.assertError("argument=x.*actual=str.*expected=int", "a", "b")
    self.assertError("argument=s.*actual=int.*expected=str", 1, 2)

  def test_keyword_args(self):
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

  def test_name(self):
    self.assertClassName("Foo", preconditions.parse("Foo"))

  def test_is_instance(self):
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

  def test_none(self):
    self.assertClassName("NoneType", preconditions.parse("None"))

  def test_tuple(self):
    c = preconditions.parse("tuple[int]")
    self.assertIsInstance(c, preconditions._TuplePrecondition)
    self.assertClassName("int", c._element_condition)

  def test_or(self):
    self.assertOr(["int", "str", "float"],
                  preconditions.parse("int or str or float"))

  def test_tuple_and_or(self):
    c = preconditions.parse("None or tuple[int or str]")
    self.assertIsInstance(c, preconditions._OrPrecondition)
    c1, c2 = c._choices
    self.assertClassName("NoneType", c1)
    self.assertIsInstance(c2, preconditions._TuplePrecondition)
    self.assertOr(["int", "str"], c2._element_condition)

  def test_errors(self):
    self.assertRaises(ValueError, preconditions.parse, "")
    self.assertRaises(ValueError, preconditions.parse, "or")
    self.assertRaises(ValueError, preconditions.parse, "a or")
    self.assertRaises(ValueError, preconditions.parse, "tuple")
    self.assertRaises(ValueError, preconditions.parse, "tuple[")
    self.assertRaises(ValueError, preconditions.parse, "tuple[]")
    self.assertRaises(ValueError, preconditions.parse, "?")

  def test_parse_arg(self):
    self.assertEqual(("x", None), preconditions.parse_arg("x"))
    name, cond = preconditions.parse_arg("foo: str")
    self.assertEqual("foo", name)
    self.assertClassName("str", cond)


if __name__ == "__main__":
  unittest.main()
