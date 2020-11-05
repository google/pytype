"""Test operators, using __any_object__."""

from pytype.tests import test_base


class OperatorsWithAnyTests(test_base.TargetIndependentTest):
  """Operator tests."""

  @test_base.skip("Needs __radd__ on all builtins")
  def test_add1(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd1(x):
        return x + 2.0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testAdd1(x: Union[int, float, complex, bool]) -> Union[float, complex]: ...
    """)

  @test_base.skip("Needs __radd__ on all builtins")
  def test_add2(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd2(x):
        return 2.0 + x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testAdd2(x: Union[int, float, complex, bool]) -> Union[float, complex]: ...
    """)

  def test_add3(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd3(x):
        return x + "abc"
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testAdd3(x) -> Any: ...
    """)

  @test_base.skip("Needs handling of immutable types for += on an unknown")
  def test_add4(self):
    # TODO(rechen): Fix test_stringio when this is working.
    ty = self.Infer("""
      def t_testAdd5(x):
        x += "42"
        return x
    """)
    # Currently missing str and unicode
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union
      def t_testAdd5(x: Union[str, unicode, bytearray, list[Any]]) -> Union[str, unicode, bytearray, list[Any]]: ...
    """)

  def test_str_mul(self):
    """Test that __mul__, __rmul__ are working."""
    ty = self.Infer("""
      def t_testAdd4(x):
        return "abc" * x
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd4(x) -> str: ...
    """)

  def test_pow1(self):
    ty = self.Infer("""
      def t_testPow1(x, y):
        return x ** y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testPow1(x, y) -> Any: ...
    """)

  def test_isinstance1(self):
    ty = self.Infer("""
      def t_testIsinstance1(x):
        return isinstance(x, int)
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testIsinstance1(x) -> bool: ...
    """)

  def test_call_any(self):
    ty = self.Infer("""
      t_testCallAny = __any_object__
      t_testCallAny()  # error because there's no "def f()..."
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      t_testCallAny = ...  # type: Any
    """)

  @test_base.skip("Needs NameError support")
  def test_undefined_module(self):
    ty = self.Infer("""
      def t_testSys():
        return sys
      t_testSys()
      """, deep=False)
    self.assertEqual(ty.Lookup("t_testSys").signatures[0].exceptions,
                     self.nameerror)

  def test_subscr(self):
    self.Check("""
      x = "foo" if __random__ else None
      d = {"foo": 42}
      d[x]  # BINARY_SUBSCR
      "foo" + x  # BINARY_ADD
      "%s" % x  # BINARY_MODULO
    """)


test_base.main(globals(), __name__ == "__main__")
