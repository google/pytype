"""Test operators, using __any_object__."""

import unittest
from pytype.tests import test_inference


class OperatorsWithAnyTests(test_inference.InferenceTest):

  @unittest.skip("Needs __radd__ on all builtins")
  def testAdd1(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd1(x):
        return x + 2.0
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd1(x: int or float or complex or bool) -> float or complex
    """)

  @unittest.skip("Needs __radd__ on all builtins")
  def testAdd2(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd2(x):
        return 2.0 + x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd2(x: int or float or complex or bool) -> float or complex
    """)

  def testAdd3(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd3(x):
        return x + "abc"
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testAdd3(x) -> Any
    """)

  def testAdd4(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd4(x):
        return "abc" + x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testAdd4(x) -> Any
    """)

  @unittest.skip("Needs handling of immutable types for += on an unknown")
  def testAdd5(self):
    # TODO(rechen): Fix test_stringio when this is working.
    ty = self.Infer("""
      def t_testAdd5(x):
        x += "42"
        return x
    """, deep=True)
    # Currently missing str and unicode
    self.assertTypesMatchPytd(ty, """
      def t_testAdd5(x: str or unicode or bytearray or list[?]) -> str or unicode or bytearray or list[?]
    """)

  def testPow1(self):
    ty = self.Infer("""
      def t_testPow1(x, y):
        return x ** y
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testPow1(x, y) -> Any
    """)

  def testIsinstance1(self):
    ty = self.Infer("""
      def t_testIsinstance1(x):
        # TODO: if isinstance(x, int): return "abc" else: return None
        return isinstance(x, int)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def t_testIsinstance1(x) -> bool
    """)

  def testCallAny(self):
    ty = self.Infer("""
      t_testCallAny = __any_object__
      t_testCallAny()  # error because there's no "def f()..."
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      t_testCallAny = ...  # type: ?
    """)

  @unittest.skip("Needs NameError support")
  def testUndefinedModule(self):
    ty = self.Infer("""
      def t_testSys():
        return sys
      t_testSys()
      """, deep=False)
    self.assertEqual(ty.Lookup("t_testSys").signatures[0].exceptions,
                     self.nameerror)

  def testSubscr(self):
    self.assertNoErrors("""
      x = "foo" if __random__ else None
      d = {"foo": 42}
      d[x]  # BINARY_SUBSCR
      "foo" + x  # BINARY_ADD
      "%s" % x  # BINARY_MODULO
    """)


if __name__ == "__main__":
  test_inference.main()
