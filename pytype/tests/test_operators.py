"""Test operators (basic tests)."""

import textwrap
import unittest
from pytype.pytd import pytd
from pytype.pytd.parse import visitors
from pytype.tests import test_inference


class ConcreteTest(test_inference.InferenceTest):
  """Tests for operators on concrete values (no unknowns)."""

  def setUp(self):
    super(ConcreteTest, self).setUp()
    self._test_tests = True  # control double-check that the test is correct
    # TODO(pludemann):         control this by whether the testing version is
    #                          the same version as the test code (see comment in
    #                          check_native_call)

  def check_expr(self, expr, assignments, expected_return):
    # Note that testing "1+2" as opposed to "x=1; y=2; x+y" doesn't really test
    # anything because the peephole optimizer converts "1+2" to "3" and __add__
    # isn't called. So, need to defeat the optimizer by replacing the constants
    # by variables, which will result in calling __add__ et al.

    # Join the assignments with ";" to avoid figuring out the exact indentation:
    assignments = "; ".join(assignments)
    src = """
      def f():
        {assignments}
        return {expr}
      f()
    """.format(expr=expr, assignments=assignments)
    ty = self.Infer(src, deep=False, solve_unknowns=False,
                    extract_locals=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), expected_return)
    self.check_native_call(src, "f", expected_return)

  def check_native_call(self, src, function_name, expected_return):
    # Given the source code for a function, compile it, run it and check its
    # type ... this is a simple-minded check against typos in the tests -- the
    # top-level Python type must match what `expected_return` has; but it
    # doesn't verify that the contents of a container (e.g., list) is as
    # expected.

    # TODO(pludemann): check container contents?

    # TODO(pludemann): This test is problematic if the inferencer is running
    #                  under a different version of Python than what's being
    #                  tested. For now, use _test_tests as a way of turning
    #                  this off.
    if self._test_tests:
      src = textwrap.dedent(src)
      my_globs = {}
      # adds f to my_globs:
      eval(compile(src, "<string>", "exec"), my_globs)  # pylint: disable=eval-used
      f = my_globs["f"]  # was added to my_globs by eval above
      f_return_type_name = type(f()).__name__
      if isinstance(expected_return, pytd.UnionType):
        self.assertIn(f_return_type_name,
                      [t.Visit(visitors.PythonTypeNameVisitor())
                       for t in expected_return.type_list])
      else:
        self.assertEqual(f_return_type_name, expected_return.Visit(
            visitors.PythonTypeNameVisitor()))

  def test_add(self):
    self.check_expr("x + y", ["x=1", "y=2"], self.int)
    self.check_expr("x + y", ["x=1.0", "y=2"], self.float)
    self.check_expr("x + y", ["x=1", "y=2.0"], self.float)
    self.check_expr("x + y", ["x=1.1", "y=2.1"], self.float)

  def test_add2(self):
    # split out from test_add for better sharding
    self.check_expr("x + y", ["x=1", "y=2j"], self.complex)
    self.check_expr("x + y", ["x=1.0", "y=2j"], self.complex)
    self.check_expr("x + y", ["x=2j", "y=1"], self.complex)
    self.check_expr("x + y", ["x=3+2j", "y=1.0"], self.complex)
    self.check_expr("x + y", ["x=1j", "y=2j"], self.complex)

  def test_add3(self):
    # split out from test_add for better sharding
    # TODO(pludemann): add unicode, bytearray:
    self.check_expr("x + y", ["x='1'", "y='2'"], self.str)
    self.check_expr("x + y", ["x=[1]", "y=[2]"], self.int_list)
    self.check_expr("x + y", ["a=1", "x=[a,a,a]", "y=[a,a,a]"], self.int_list)
    self.check_expr("x + y", ["a=1", "x=[a,a,a]", "y=[]"], self.int_list)
    self.check_expr("x + y", ["a=1", "x=[]", "y=[a,a,a]"], self.int_list)

  def test_add4(self):
    # split out from test_add for better sharding
    self.check_expr("x + y", ["x=[]", "y=[]"], self.nothing_list)
    self.check_expr("x + y", ["x=[1]", "y=['abc']"], self.intorstr_list)
    self.check_expr("x + y", ["x=(1,)", "y=(2,)"], self.int_tuple)
    self.check_expr("x + y", ["x=(1,)", "y=(2.0,)"], self.intorfloat_tuple)

  def test_and(self):
    self.check_expr("x & y", ["x=3", "y=5"], self.int)
    self.check_expr("x & y", ["x={1}", "y={1, 2}"], self.int_set)
    self.check_expr("x & y", ["x={1}", "y={1.2}"], self.intorfloat_set)
    self.check_expr("x & y", ["x={1, 2}", "y=set([1])"], self.int_set)
    self.check_expr("x & y", ["x=1", "y=2"], self.int)

  def test_frozenset_ops(self):
    # TODO(pludemann): when these work, put them into the appropriate
    #                  test_<op> tests
    self.check_expr("x & y", ["x=frozenset()", "y=frozenset()"],
                    self.empty_frozenset)
    self.check_expr("x - y", ["x=frozenset()", "y=frozenset()"],
                    self.empty_frozenset)
    self.check_expr("x | y", ["x=frozenset([1.0])", "y=frozenset([2.2])"],
                    self.float_frozenset)

  def test_contains(self):
    self.check_expr("x in y", ["x=[1]", "y=[1, 2]"], self.bool)
    self.check_expr("x in y", ["x='ab'", "y='abcd'"], self.bool)
    self.check_expr("x in y", ["x='ab'", "y=['abcd']"], self.bool)

  def test_div(self):
    self.check_expr("x / y", ["x=1", "y=2"], self.int)
    self.check_expr("x / y", ["x=1.0", "y=2"], self.float)
    self.check_expr("x / y", ["x=1", "y=2.0"], self.float)
    self.check_expr("x / y", ["x=1.1", "y=2.1"], self.float)
    self.check_expr("x / y", ["x=1j", "y=2j"], self.complex)

  def test_div2(self):
    # split out from test_div for better sharding
    self.check_expr("x / y", ["x=1", "y=2j"], self.complex)
    self.check_expr("x / y", ["x=1.0", "y=2j"], self.complex)
    self.check_expr("x / y", ["x=2j", "y=1j"], self.complex)
    self.check_expr("x / y", ["x=2j", "y=1"], self.complex)
    self.check_expr("x / y", ["x=3+2j", "y=1.0"], self.complex)

  def test_floordiv(self):
    # TODO(pludemann): Python 3 is different:
    self.check_expr("x // y", ["x=1", "y=2"], self.int)
    self.check_expr("x // y", ["x=1.0", "y=2"], self.float)
    self.check_expr("x // y", ["x=1", "y=2.0"], self.float)
    self.check_expr("x // y", ["x=1.1", "y=2.1"], self.float)
    self.check_expr("x // y", ["x=1j", "y=2j"], self.complex)

  def test_floordiv2(self):
    # split out from test_floordiv for better sharding
    self.check_expr("x // y", ["x=1", "y=2j"], self.complex)
    self.check_expr("x // y", ["x=1.0", "y=2j"], self.complex)
    self.check_expr("x // y", ["x=2j", "y=1j"], self.complex)
    self.check_expr("x // y", ["x=2j", "y=1"], self.complex)
    self.check_expr("x // y", ["x=3+2j", "y=1.0"], self.complex)

  def test_invert(self):
    self.check_expr("~x", ["x=3"], self.int)
    self.check_expr("~x", ["x=False"], self.int)

  def test_lshift(self):
    self.check_expr("x << y", ["x=1", "y=2"], self.int)

  def test_rshift(self):
    self.check_expr("x >> y", ["x=1", "y=2"], self.int)

  def test_sub(self):
    self.check_expr("x - y", ["x=1", "y=2"], self.int)
    self.check_expr("x - y", ["x=1.0", "y=2"], self.float)
    self.check_expr("x - y", ["x=1", "y=2.0"], self.float)
    self.check_expr("x - y", ["x=1.1", "y=2.1"], self.float)

  def test_sub2(self):
    # split out from test_sub for better sharding
    self.check_expr("x - y", ["x=1j", "y=2j"], self.complex)
    self.check_expr("x - y", ["x={1}", "y={1, 2}"], self.int_set)
    self.check_expr("x - y", ["x={1}", "y={1.2}"], self.int_set)
    self.check_expr("x - y", ["x={1, 2}", "y=set([1])"], self.int_set)

  def test_sub_frozenset(self):
    self.check_expr("x - y", ["x={1, 2}", "y=frozenset([1.0])"],
                    self.int_set)

  def test_mod(self):
    self.check_expr("x % y", ["x=1", "y=2"], self.int)
    self.check_expr("x % y", ["x=1.5", "y=2.5"], self.float)
    self.check_expr("x % y", ["x='%r'", "y=set()"], self.str)

  def test_mul(self):
    self.check_expr("x * y", ["x=1", "y=2"], self.int)
    self.check_expr("x * y", ["x=1", "y=2.1"], self.float)
    self.check_expr("x * y", ["x=1+2j", "y=2.1+3.4j"], self.complex)
    self.check_expr("x * y", ["x='x'", "y=3"], self.str)
    self.check_expr("x * y", ["x=3", "y='x'"], self.str)

  def test_mul2(self):
    # split out from test_mul for better sharding
    self.check_expr("x * y", ["x=[1, 2]", "y=3"], self.int_list)
    self.check_expr("x * y", ["x=99", "y=[1.0, 2]"], self.intorfloat_list)
    self.check_expr("x * y", ["x=(1, 2)", "y=3"], self.int_tuple)
    self.check_expr("x * y", ["x=0", "y=(1, 2.0)"], self.intorfloat_tuple)

  def test_neg(self):
    self.check_expr("-x", ["x=1"], self.int)
    self.check_expr("-x", ["x=1.5"], self.float)
    self.check_expr("-x", ["x=1j"], self.complex)

  def test_or(self):
    self.check_expr("x | y", ["x=1", "y=2"], self.int)
    self.check_expr("x | y", ["x={1}", "y={2}"], self.int_set)

  def test_pos(self):
    self.check_expr("+x", ["x=1"], self.int)
    self.check_expr("+x", ["x=1.5"], self.float)
    self.check_expr("+x", ["x=2 + 3.1j"], self.complex)

  def test_pow(self):
    self.check_expr("x ** y", ["x=1", "y=2"], self.intorfloat)
    self.check_expr("x ** y", ["x=1", "y=-2"], self.intorfloat)
    self.check_expr("x ** y", ["x=1.0", "y=2"], self.float)
    self.check_expr("x ** y", ["x=1", "y=2.0"], self.float)
    self.check_expr("x ** y", ["x=1.1", "y=2.1"], self.float)
    self.check_expr("x ** y", ["x=1j", "y=2j"], self.complex)

  def test_xor(self):
    self.check_expr("x ^ y", ["x=1", "y=2"], self.int)
    self.check_expr("x ^ y", ["x={1}", "y={2}"], self.int_set)


class OverloadTest(test_inference.InferenceTest):
  """Tests for overloading operators."""

  def check_binary(self, function_name, op):
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self, unused_x):
          return 3j
      class Bar(object):
        pass
      def f():
        return Foo() {op} Bar()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False, solve_unknowns=False,
                    extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def check_unary(self, function_name, op, ret=None):
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self):
          return 3j
      def f():
        return {op} Foo()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False, solve_unknowns=False,
                    extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), ret or self.complex)

  def test_add(self):
    self.check_binary("__add__", "+")

  def test_and(self):
    self.check_binary("__and__", "&")

  def test_or(self):
    self.check_binary("__or__", "|")

  def test_sub(self):
    self.check_binary("__sub__", "-")

  def test_div(self):
    self.check_binary("__div__", "/")

  def test_floordiv(self):
    self.check_binary("__floordiv__", "//")

  def test_mod(self):
    self.check_binary("__mod__", "%")

  def test_mul(self):
    self.check_binary("__mul__", "*")

  def test_pow(self):
    self.check_binary("__pow__", "**")

  def test_lshift(self):
    self.check_binary("__lshift__", "<<")

  def test_rshift(self):
    self.check_binary("__rshift__", ">>")

  def test_invert(self):
    self.check_unary("__invert__", "~")

  def test_neg(self):
    self.check_unary("__neg__", "-")

  def test_pos(self):
    self.check_unary("__pos__", "+")

  def test_nonzero(self):
    # __nonzero__ is hard to test, because you can never call it directly -
    # "not x" will call __nonzero__ on x, but then convert the result to boolean
    # and invert it. Hence, we're only checking for bool here.
    self.check_unary("__nonzero__", "not", self.bool)


@unittest.skip("Reverse operator overloading isn't supported")
class ReverseTest(test_inference.InferenceTest):
  """Tests for reverse operators."""

  def check_reverse(self, function_name, op):
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      class Bar(Foo):
        def __r{function_name}__(self, x):
          return "foo"
      def f():
        return Foo() {op} 1  # use Foo.__{function_name}__
      def g():
        return 1 {op} Bar()  # use Bar.__r{function_name}__
      def h():
        return Foo() {op} Bar()  # use Bar.__r{function_name}__
      def i():
        return Foo() {op} Foo()  # use Foo.__{function_name}__
      f(); g(); h(); i()
    """.format(op=op, function_name=function_name),
                    deep=False, solve_unknowns=False,
                    extract_locals=False)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)
    self.assertHasReturnType(ty.Lookup("g"), self.str)
    self.assertHasReturnType(ty.Lookup("h"), self.str)
    self.assertHasReturnType(ty.Lookup("i"), self.complex)

  def test_add(self):
    self.check_reverse("add", "+")

  def test_and(self):
    self.check_reverse("and", "&")

  def test_div(self):
    self.check_reverse("div", "/")

  def test_floordiv(self):
    self.check_reverse("floordiv", "//")

  def test_lshift(self):
    self.check_reverse("lshift", "<<")

  def test_rshift(self):
    self.check_reverse("rshift", ">>")

  def test_mod(self):
    self.check_reverse("mod", "%")

  def test_mul(self):
    self.check_reverse("mul", "*")

  def test_or(self):
    self.check_reverse("or", "|")

  def test_pow(self):
    self.check_reverse("pow", "**")

  def test_sub(self):
    self.check_reverse("sub", "-")


class InplaceTest(test_inference.InferenceTest):
  """Tests for in-place operators."""

  def check_inplace(self, function_name, op):
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      def f():
        x = Foo()
        x {op} None
        return x
      f()
    """.format(op=op, function_name=function_name),
                    deep=False, solve_unknowns=False,
                    extract_locals=False)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)

  def test_add(self):
    self.check_inplace("iadd", "+=")

  def test_and(self):
    self.check_inplace("iand", "&=")

  def test_div(self):
    self.check_inplace("idiv", "/=")

  def test_floordiv(self):
    self.check_inplace("ifloordiv", "//=")

  def test_lshift(self):
    self.check_inplace("ilshift", "<<=")

  def test_rshift(self):
    self.check_inplace("irshift", ">>=")

  def test_mod(self):
    self.check_inplace("imod", "%=")

  def test_mul(self):
    self.check_inplace("imul", "*=")

  def test_or(self):
    self.check_inplace("ior", "|=")

  def test_pow(self):
    self.check_inplace("ipow", "**=")

  def test_sub(self):
    self.check_inplace("isub", "-=")


if __name__ == "__main__":
  test_inference.main()
