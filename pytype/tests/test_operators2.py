"""Test operators, using __any_object__."""

import unittest
from pytype import utils
from pytype.tests import test_inference


# TODO(pludemann): duplicate the tests in test_operators.py, but
#                  with __any_object__() ... that is: copy check_expr
#                  to here and then simplify test_operators.check_expr


class OperatorsWithAnyTests(test_inference.InferenceTest):

  @unittest.skip("Needs __radd__ on all builtins")
  def testAdd1(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd1(x):
        return x + 2.0
    """, deep=True, solve_unknowns=True, extract_locals=True)
    # TODO(pludemann): Currently this matches:
    #         def t_testAdd1(x: float) -> float
    self.assertTypesMatchPytd(ty, """
      def t_testAdd1(x: int or float or complex or long or bool) -> float or complex
    """)

  @unittest.skip("Needs __radd__ on all builtins")
  def testAdd2(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd2(x):
        return 2.0 + x
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd2(x: int or float or complex or long or bool) -> float or complex
    """)

  def testAdd3(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd3(x):
        return x + "abc"
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def t_testAdd3(x: buffer or bytearray or str or unicode) -> bytearray or str or unicode
    """)

  @unittest.skip("Broken: Needs full __radd__ in all builtins")
  def testAdd4(self):
    """Test that __add__, __radd__ are working."""
    ty = self.Infer("""
      def t_testAdd4(x):
        return "abc" + x
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      # TODO(pludemann): generates this, which is wrong:
      def t_testAdd4(x: nothing) -> object
      # Should generate:
      def t_testAdd4(x: str) -> str
    """)

  @unittest.skip("Needs handling of immutable types for += on an unknown")
  def testAdd5(self):
    # TODO(rechen): Fix test_stringio when this is working.
    ty = self.Infer("""
      def t_testAdd5(x):
        x += "42"
        return x
    """, deep=True, solve_unknowns=True, extract_locals=True)
    # Currently missing str and unicode
    self.assertTypesMatchPytd(ty, """
      def t_testAdd5(x: str or unicode or bytearray or list[?]) -> str or unicode or bytearray or list[?]
    """)

  def testPow1(self):
    # TODO(pludemann): add tests for 3-arg pow, etc.
    ty = self.Infer("""
      def t_testPow1(x, y):
        return x ** y
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      # TODO(pludemann): bool should be removed (by either solver (if __builtin__ changes or optimizer)
      def t_testPow1(x: complex or float or int or long, y: complex or float or int or long) -> complex or float or int or long
    """)

  def testIsinstance1(self):
    ty = self.Infer("""
      def t_testIsinstance1(x):
        # TODO: if isinstance(x, int): return "abc" else: return None
        return isinstance(x, int)
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def t_testIsinstance1(x) -> bool
    """)


class CallErrorTests(test_inference.InferenceTest):

  def testCallAny(self):
    # TODO(pludemann): verify that this generates
    # class `~unknown1`(nothing):
    #   def __call__(self) -> `~unknown2`
    # class `~unknown2`(nothing):
    #   pass
    # ... ~unknown1 = function
    # ... ~unknown2 = ?
    ty = self.Infer("""
      t_testCallAny = __any_object__
      t_testCallAny()  # error because there's no "def f()..."
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      t_testCallAny = ...  # type: ?
    """)

  @unittest.skip("Need to handle undefined function call")
  def testUndefinedCall(self):
    # Raises VirtualMachineError("Frame has no return") because
    # LOAD_NAME '_testBar' raises ByteCodeException:
    # <type # 'exceptions.NameError'> "name '_testBar' is not defined"
    ty = self.Infer("""
      def t_testUndefinedCallDoesntExist():
        return 1
      t_testUndefinedCall()  # Doesn't exist -- should give an error
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      # TODO(pludemann): verify that it generates an error
    """)

  @unittest.skip("Needs NameError support")
  def testUndefinedModule(self):
    ty = self.Infer("""
      def t_testSys():
        return sys
      t_testSys()
      """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertEquals(ty.Lookup("t_testSys").signatures[0].exceptions,
                      self.nameerror)

  def testCustomReverseOperator(self):
    with utils.Tempdir() as d:
      d.create_file("test.pyi", """
        class Test():
          def __or__(self, other: Tuple[int]) -> bool
          def __ror__(self, other: Tuple[int]) -> bool
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
        test = ...  # type: module
        x = ...  # type: bool
        y = ...  # type: bool
        def f(t: dict_keys[int] or Set[int] or test.Test) -> Set[int] or bool
        def g(t: test.Test) -> bool
      """)

if __name__ == "__main__":
  test_inference.main()
