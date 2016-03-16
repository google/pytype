"""Tests for displaying errors."""

import StringIO

from pytype.tests import test_inference


class ErrorTest(test_inference.InferenceTest):
  """Tests for errors."""

  def testDeduplicate(self):
    _, errors = self.InferAndCheck("""
      def f(x):
        x.foobar
      f(3)
      f(4)
    """)
    s = StringIO.StringIO()
    errors.print_to_file(s)
    self.assertEquals(1, len([line for line in s.getvalue().splitlines()
                              if "foobar" in line]))

  def testUnknownGlobal(self):
    _, errors = self.InferAndCheck("""
      def f():
        return foobar()
    """)
    self.assertErrorLogContains(errors, r"line 3.*foobar")

  def testInvalidAttribute(self):
    ty, errors = self.InferAndCheck("""
      class A(object):
        pass
      def f():
        (3).parrot
        return "foo"
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        pass

      def f() -> str
    """)
    self.assertErrorLogContains(errors, r"line 5.*attribute.*parrot.*int")

  def testImportError(self):
    _, errors = self.InferAndCheck("""
      import rumplestiltskin
    """)
    self.assertErrorLogContains(errors, r"line 2.*module.*rumplestiltskin")

  def testNameError(self):
    _, errors = self.InferAndCheck("""
      foobar
    """)
    # "Line 2, in <module>: Name 'foobar' is not defined"
    self.assertErrorLogContains(errors, r"line 2.*name.*foobar.*not.defined")

  def testUnsupportedOperands(self):
    _, errors = self.InferAndCheck("""
      def f():
        x = "foo"
        y = "bar"
        return x ^ y
    """)
    # "Line 2, in f: Unsupported operands for __xor__: 'str' and 'str'
    self.assertErrorLogContains(errors,
                                r"line 5.*Unsupported.*__xor__.*str.*str")

  def testUnsupportedOperands2(self):
    _, errors = self.InferAndCheck("""
      def f():
        x = "foo"
        y = 3
        return x + y
    """)
    # "Line 2, in f: Unsupported operands for __add__: 'str' and 'int'
    self.assertErrorLogContains(errors,
                                r"line 5.*Unsupported.*__add__.*str.*int")

  def testWrongArgCount(self):
    _, errors = self.InferAndCheck("""
      hex(1, 2, 3, 4)
    """)
    self.assertErrorLogContains(
        errors, r"line 2.*hex was called with 4 args instead of expected 1")

  def testWrongArgTypes(self):
    _, errors = self.InferAndCheck("""
      hex(3j)
    """)
    self.assertErrorLogContains(
        errors, (r"line 2.*hex was called with the wrong arguments.*"
                 r"expected:.*int.*passed:.*complex"))

  def testIndexError(self):
    _, errors = self.InferAndCheck("""
      def f():
        return [][0]
    """)
    # "Line 3, in f: Can't retrieve item out of list. Empty?"
    self.assertErrorLogContains(errors, r"line 3.*item out of list")

  def testInvalidBaseClass(self):
    _, errors = self.InferAndCheck("""
      class Foo(3):
        pass
    """)
    # "Line 2, in <module>: Invalid base class: `~unknown0`"
    self.assertErrorLogContains(errors, r"Invalid base class")

  def testInvalidIteratorFromImport(self):
    _, errors = self.InferAndCheck("""
      import codecs
      def f():
        for row in codecs.Codec():
          pass
    """)
    # "Line 4, in f: No attribute '__iter__' on Codec"
    self.assertErrorLogContains(
        errors, r"line 4.*No attribute.*__iter__.*on Codec")
    self.assertErrorLogDoesNotContain(
        errors, "__class__")

  def testInvalidIteratorFromClass(self):
    _, errors = self.InferAndCheck("""
      class A(object):
        pass
      def f():
        for row in A():
          pass
    """)
    self.assertErrorLogContains(
        errors, r"line 5.*No attribute.*__iter__.*on A")
    self.assertErrorLogDoesNotContain(
        errors, "__class__")

  def testWriteIndexError(self):
    _, errors = self.InferAndCheck("""
      def f():
        {}[0].x = 3
    """)
    # "Line 3, in f: Can't retrieve item out of dict. Empty?"
    self.assertErrorLogContains(errors, r"line 3.*item out of dict")

if __name__ == "__main__":
  test_inference.main()
