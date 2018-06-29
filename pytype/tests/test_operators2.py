"""Test operators, using __any_object__."""

from pytype.tests import test_base


class OperatorsWithAnyTests(test_base.TargetIndependentTest):

  @test_base.skip("Needs __radd__ on all builtins")
  def testAdd1(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd1(x):
        return x + 2.0
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd1(x: int or float or complex or bool) -> float or complex
    """)

  @test_base.skip("Needs __radd__ on all builtins")
  def testAdd2(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd2(x):
        return 2.0 + x
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd2(x: int or float or complex or bool) -> float or complex
    """)

  def testAdd3(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd3(x):
        return x + "abc"
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testAdd3(x) -> Any
    """)

  @test_base.skip("Needs handling of immutable types for += on an unknown")
  def testAdd4(self):
    # TODO(rechen): Fix test_stringio when this is working.
    ty = self.Infer("""
      def t_testAdd5(x):
        x += "42"
        return x
    """)
    # Currently missing str and unicode
    self.assertTypesMatchPytd(ty, """
      def t_testAdd5(x: str or unicode or bytearray or list[?]) -> str or unicode or bytearray or list[?]
    """)

  def testStrMul(self):
    """Test that __mul__, __rmul__ are working."""
    ty = self.Infer("""
      def t_testAdd4(x):
        return "abc" * x
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd4(x) -> str
    """)

  def testPow1(self):
    ty = self.Infer("""
      def t_testPow1(x, y):
        return x ** y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testPow1(x, y) -> Any
    """)

  def testIsinstance1(self):
    ty = self.Infer("""
      def t_testIsinstance1(x):
        # TODO: if isinstance(x, int): return "abc" else: return None
        return isinstance(x, int)
    """)
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

  @test_base.skip("Needs NameError support")
  def testUndefinedModule(self):
    ty = self.Infer("""
      def t_testSys():
        return sys
      t_testSys()
      """, deep=False)
    self.assertEqual(ty.Lookup("t_testSys").signatures[0].exceptions,
                     self.nameerror)

  def testSubscr(self):
    self.Check("""
      x = "foo" if __random__ else None
      d = {"foo": 42}
      d[x]  # BINARY_SUBSCR
      "foo" + x  # BINARY_ADD
      "%s" % x  # BINARY_MODULO
    """)


test_base.main(globals(), __name__ == "__main__")
