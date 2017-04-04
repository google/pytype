"""Test operators, using __any_object__."""

import unittest
from pytype import utils
from pytype.tests import test_inference


class OperatorsWithAnyTests(test_inference.InferenceTest):

  @unittest.skip("Needs __radd__ on all builtins")
  def testAdd1(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd1(x):
        return x + 2.0
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd1(x: int or float or complex or bool) -> float or complex
    """)

  @unittest.skip("Needs __radd__ on all builtins")
  def testAdd2(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd2(x):
        return 2.0 + x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd2(x: int or float or complex or bool) -> float or complex
    """)

  def testAdd3(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd3(x):
        return x + "abc"
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import MutableSequence
      def t_testAdd3(x: buffer or bytearray or str or unicode or MutableSequence) -> bytearray or str or unicode or MutableSequence
    """)

  def testAdd4(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd4(x):
        return "abc" + x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testAdd4(x: Union[basestring, bytearray]) -> Union[str, unicode, bytearray]: ...
    """)

  @unittest.skip("Needs handling of immutable types for += on an unknown")
  def testAdd5(self):
    # TODO(rechen): Fix test_stringio when this is working.
    ty = self.Infer("""
      def t_testAdd5(x):
        x += "42"
        return x
    """, deep=True, solve_unknowns=True)
    # Currently missing str and unicode
    self.assertTypesMatchPytd(ty, """
      def t_testAdd5(x: str or unicode or bytearray or list[?]) -> str or unicode or bytearray or list[?]
    """)

  def testPow1(self):
    ty = self.Infer("""
      def t_testPow1(x, y):
        return x ** y
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def t_testPow1(x: complex or float or int, y: complex or float or int) -> complex or float or int
    """)

  def testIsinstance1(self):
    ty = self.Infer("""
      def t_testIsinstance1(x):
        # TODO: if isinstance(x, int): return "abc" else: return None
        return isinstance(x, int)
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      def t_testIsinstance1(x) -> bool
    """)


class CallErrorTests(test_inference.InferenceTest):

  def testCallAny(self):
    ty = self.Infer("""
      t_testCallAny = __any_object__
      t_testCallAny()  # error because there's no "def f()..."
    """, deep=False, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      t_testCallAny = ...  # type: ?
    """)

  @unittest.skip("Needs NameError support")
  def testUndefinedModule(self):
    ty = self.Infer("""
      def t_testSys():
        return sys
      t_testSys()
      """, deep=False, solve_unknowns=False)
    self.assertEquals(ty.Lookup("t_testSys").signatures[0].exceptions,
                      self.nameerror)

  def testCustomReverseOperator(self):
    with utils.Tempdir() as d:
      d.create_file("test.pyi", """
        from typing import Tuple
        class Test():
          def __or__(self, other: Tuple[int, ...]) -> bool
          def __ror__(self, other: Tuple[int, ...]) -> bool
      """)
      ty = self.Infer("""
        import test
        x = test.Test() | (1, 2)
        y = (1, 2) | test.Test()
        def f(t):
          return t | (1, 2)
        def g(t):
          return (1, 2) | t
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Set
        test = ...  # type: module
        x = ...  # type: bool
        y = ...  # type: bool
        def f(t: dict_keys[int] or Set[int] or test.Test) -> Set[int] or bool
        def g(t: test.Test) -> bool
      """)

if __name__ == "__main__":
  test_inference.main()
