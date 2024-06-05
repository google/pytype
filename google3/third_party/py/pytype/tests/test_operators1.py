"""Test operators (basic tests)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ConcreteTest(test_base.BaseTest,
                   test_utils.OperatorsTestMixin):
  """Tests for operators on concrete values (no unknowns)."""

  def test_add(self):
    self.check_expr("x + y", ["x=1", "y=2"], "int")
    self.check_expr("x + y", ["x=1.0", "y=2"], "float")
    self.check_expr("x + y", ["x=1", "y=2.0"], "float")
    self.check_expr("x + y", ["x=1.1", "y=2.1"], "float")

  def test_add2(self):
    # split out from test_add for better sharding
    self.check_expr("x + y", ["x=1", "y=2j"], "complex")
    self.check_expr("x + y", ["x=1.0", "y=2j"], "complex")
    self.check_expr("x + y", ["x=2j", "y=1"], "complex")
    self.check_expr("x + y", ["x=3+2j", "y=1.0"], "complex")
    self.check_expr("x + y", ["x=1j", "y=2j"], "complex")

  def test_add3(self):
    # split out from test_add for better sharding
    self.check_expr("x + y", ["x='1'", "y='2'"], "str")
    self.check_expr("x + y", ["x=[1]", "y=[2]"], "list[int]")
    self.check_expr("x + y", ["a=1", "x=[a,a,a]", "y=[a,a,a]"], "list[int]")
    self.check_expr("x + y", ["a=1", "x=[a,a,a]", "y=[]"], "list[int]")
    self.check_expr("x + y", ["a=1", "x=[]", "y=[a,a,a]"], "list[int]")

  def test_add4(self):
    # split out from test_add for better sharding
    self.check_expr("x + y", ["x=[]", "y=[]"], "list[nothing]")
    self.check_expr("x + y", ["x=[1]", "y=['abc']"], "list[int | str]")
    self.check_expr("x + y", ["x=(1,)", "y=(2,)"], "tuple[int, int]")
    self.check_expr("x + y", ["x=(1,)", "y=(2.0,)"], "tuple[int, float]")

  def test_and(self):
    self.check_expr("x & y", ["x=3", "y=5"], "int")
    self.check_expr("x & y", ["x={1}", "y={1, 2}"], "set[int]")
    self.check_expr("x & y", ["x={1}", "y={1.2}"], "set[int]")
    self.check_expr("x & y", ["x={1, 2}", "y=set([1])"], "set[int]")
    self.check_expr("x & y", ["x=1", "y=2"], "int")

  def test_frozenset_ops(self):
    self.check_expr("x & y", ["x=frozenset()", "y=frozenset()"],
                    "frozenset[nothing]")
    self.check_expr("x - y", ["x=frozenset()", "y=frozenset()"],
                    "frozenset[nothing]")
    self.check_expr("x | y", ["x=frozenset([1.0])", "y=frozenset([2.2])"],
                    "frozenset[float]")

  def test_contains(self):
    self.check_expr("x in y", ["x=[1]", "y=[1, 2]"], "bool")
    self.check_expr("x in y", ["x='ab'", "y='abcd'"], "bool")
    self.check_expr("x in y", ["x='ab'", "y=['abcd']"], "bool")

  def test_div(self):
    self.check_expr("x / y", ["x=1.0", "y=2"], "float")
    self.check_expr("x / y", ["x=1", "y=2.0"], "float")
    self.check_expr("x / y", ["x=1.1", "y=2.1"], "float")
    self.check_expr("x / y", ["x=1j", "y=2j"], "complex")

  def test_div2(self):
    # split out from test_div for better sharding
    self.check_expr("x / y", ["x=1", "y=2j"], "complex")
    self.check_expr("x / y", ["x=1.0", "y=2j"], "complex")
    self.check_expr("x / y", ["x=2j", "y=1j"], "complex")
    self.check_expr("x / y", ["x=2j", "y=1"], "complex")
    self.check_expr("x / y", ["x=3+2j", "y=1.0"], "complex")

  def test_floordiv(self):
    self.check_expr("x // y", ["x=1", "y=2"], "int")
    self.check_expr("x // y", ["x=1.0", "y=2"], "float")
    self.check_expr("x // y", ["x=1", "y=2.0"], "float")
    self.check_expr("x // y", ["x=1.1", "y=2.1"], "float")
    self.check_expr("x // y", ["x=1j", "y=2j"], "complex")

  def test_floordiv2(self):
    # split out from test_floordiv for better sharding
    self.check_expr("x // y", ["x=1", "y=2j"], "complex")
    self.check_expr("x // y", ["x=1.0", "y=2j"], "complex")
    self.check_expr("x // y", ["x=2j", "y=1j"], "complex")
    self.check_expr("x // y", ["x=2j", "y=1"], "complex")
    self.check_expr("x // y", ["x=3+2j", "y=1.0"], "complex")

  def test_invert(self):
    self.check_expr("~x", ["x=3"], "int")
    self.check_expr("~x", ["x=False"], "int")

  def test_lshift(self):
    self.check_expr("x << y", ["x=1", "y=2"], "int")

  def test_rshift(self):
    self.check_expr("x >> y", ["x=1", "y=2"], "int")

  def test_sub(self):
    self.check_expr("x - y", ["x=1", "y=2"], "int")
    self.check_expr("x - y", ["x=1.0", "y=2"], "float")
    self.check_expr("x - y", ["x=1", "y=2.0"], "float")
    self.check_expr("x - y", ["x=1.1", "y=2.1"], "float")

  def test_sub2(self):
    # split out from test_sub for better sharding
    self.check_expr("x - y", ["x=1j", "y=2j"], "complex")
    self.check_expr("x - y", ["x={1}", "y={1, 2}"], "set[int]")
    self.check_expr("x - y", ["x={1}", "y={1.2}"], "set[int]")
    self.check_expr("x - y", ["x={1, 2}", "y=set([1])"], "set[int]")

  def test_sub_frozenset(self):
    self.check_expr("x - y", ["x={1, 2}", "y=frozenset([1.0])"], "set[int]")

  def test_mod(self):
    self.check_expr("x % y", ["x=1", "y=2"], "int")
    self.check_expr("x % y", ["x=1.5", "y=2.5"], "float")
    self.check_expr("x % y", ["x='%r'", "y=set()"], "str")

  def test_mul(self):
    self.check_expr("x * y", ["x=1", "y=2"], "int")
    self.check_expr("x * y", ["x=1", "y=2.1"], "float")
    self.check_expr("x * y", ["x=1+2j", "y=2.1+3.4j"], "complex")
    self.check_expr("x * y", ["x='x'", "y=3"], "str")
    self.check_expr("x * y", ["x=3", "y='x'"], "str")

  def test_mul2(self):
    # split out from test_mul for better sharding
    self.check_expr("x * y", ["x=[1, 2]", "y=3"], "list[int]")
    self.check_expr("x * y", ["x=99", "y=[1.0, 2]"], "list[int | float]")
    self.check_expr("x * y", ["x=(1, 2)", "y=3"], "tuple[int, ...]")
    self.check_expr("x * y", ["x=0", "y=(1, 2.0)"], "tuple[int | float, ...]")

  def test_neg(self):
    self.check_expr("-x", ["x=1"], "int")
    self.check_expr("-x", ["x=1.5"], "float")
    self.check_expr("-x", ["x=1j"], "complex")

  def test_or(self):
    self.check_expr("x | y", ["x=1", "y=2"], "int")
    self.check_expr("x | y", ["x={1}", "y={2}"], "set[int]")

  def test_pos(self):
    self.check_expr("+x", ["x=1"], "int")
    self.check_expr("+x", ["x=1.5"], "float")
    self.check_expr("+x", ["x=2 + 3.1j"], "complex")

  def test_pow(self):
    self.check_expr("x ** y", ["x=1", "y=2"], "int | float")
    self.check_expr("x ** y", ["x=1", "y=-2"], "int | float")
    self.check_expr("x ** y", ["x=1.0", "y=2"], "float")
    self.check_expr("x ** y", ["x=1", "y=2.0"], "float")
    self.check_expr("x ** y", ["x=1.1", "y=2.1"], "float")
    self.check_expr("x ** y", ["x=1j", "y=2j"], "complex")

  def test_xor(self):
    self.check_expr("x ^ y", ["x=1", "y=2"], "int")
    self.check_expr("x ^ y", ["x={1}", "y={2}"], "set[int]")

  def test_add_type_parameter_instance(self):
    self.Check("""
      from typing import Union
      v = None  # type: Union[str]
      d = {v: 42}
      for k, _ in sorted(d.items()):
        k + " as "
    """)


class OverloadTest(test_base.BaseTest,
                   test_utils.OperatorsTestMixin):
  """Tests for overloading operators."""

  def test_add(self):
    self.check_binary("__add__", "+")

  def test_and(self):
    self.check_binary("__and__", "&")

  def test_or(self):
    self.check_binary("__or__", "|")

  def test_sub(self):
    self.check_binary("__sub__", "-")

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
    self.check_unary("__nonzero__", "not", "bool")


class ReverseTest(test_base.BaseTest,
                  test_utils.OperatorsTestMixin):
  """Tests for reverse operators."""

  def test_add(self):
    self.check_reverse("add", "+")

  def test_and(self):
    self.check_reverse("and", "&")

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

  def test_custom(self):
    with test_utils.Tempdir() as d:
      d.create_file("test.pyi", """
        from typing import Tuple
        class Test():
          def __or__(self, other: Tuple[int, ...]) -> bool: ...
          def __ror__(self, other: Tuple[int, ...]) -> bool: ...
      """)
      ty = self.Infer("""
        import test
        x = test.Test() | (1, 2)
        y = (1, 2) | test.Test()
        def f(t):
          return t | (1, 2)
        def g(t):
          return (1, 2) | t
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import test
        from typing import Any
        x = ...  # type: bool
        y = ...  # type: bool
        def f(t) -> Any: ...
        def g(t) -> Any: ...
      """)

  def test_custom_reverse_unused(self):
    self.Check("""
      class Foo:
        def __sub__(self, other):
          return 42
        def __rsub__(self, other):
          return ""
      (Foo() - Foo()).real
    """)

  def test_inherited_custom_reverse_unused(self):
    self.Check("""
      class Foo:
        def __sub__(self, other):
          return 42
        def __rsub__(self, other):
          return ""
      class Bar(Foo):
        pass
      (Foo() - Bar()).real
    """)

  def test_custom_reverse_only(self):
    self.Check("""
      class Foo:
        def __sub__(self, other):
          return ""
      class Bar(Foo):
        def __rsub__(self, other):
          return 42
      (Foo() - Bar()).real
    """)

  def test_unknown_left(self):
    self.Check("""
      class Foo:
        def __rsub__(self, other):
          return ""
      (__any_object__ - Foo()).real
    """)

  def test_unknown_right(self):
    # Reverse operators are rare enough that it makes sense to assume that the
    # regular operator was called when the right side is ambiguous.
    _, errors = self.InferWithErrors("""
      class Foo:
        def __sub__(self, other):
          return ""
      (Foo() - __any_object__).real  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"real.*str"})


class InplaceTest(test_base.BaseTest,
                  test_utils.OperatorsTestMixin):
  """Tests for in-place operators."""

  def test_add(self):
    self.check_inplace("iadd", "+=")

  def test_and(self):
    self.check_inplace("iand", "&=")

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

  def test_list_add(self):
    _, errors = self.InferWithErrors("""
      class A: pass
      v = []
      v += A()  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*Iterable"})


class BindingsTest(test_base.BaseTest):
  """Tests that we correctly handle results without bindings."""

  def test_subscr(self):
    # Regression test (b/150240064)
    # Make sure we don't crash due to __path__[0] having no bindings. Previously
    # we were not setting __path__[0] to [unsolvable] if report_errors was False
    self.options.tweak(report_errors=False)
    self.InferWithErrors("""
      { 'path': __path__[0] }
    """)


if __name__ == "__main__":
  test_base.main()
