"""Tests for displaying errors."""

import re

from pytype import file_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class ErrorTest(test_base.TargetPython3BasicTest):
  """Tests for errors."""

  def test_union(self):
    _, errors = self.InferWithErrors("""
      def f(x: int):
        pass
      if __random__:
        i = 0
      else:
        i = 1
      x = (3.14, "")
      f(x[i])  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Actually passed:.*Union\[float, str\]"})

  def test_invalid_annotations(self):
    _, errors = self.InferWithErrors("""
      from typing import Dict, List, Union
      def f1(x: Dict):  # okay
        pass
      def f2(x: Dict[str]):  # invalid-annotation[e1]
        pass
      def f3(x: List[int, str]):  # invalid-annotation[e2]
        pass
      def f4(x: Union):  # invalid-annotation[e3]
        pass
    """)
    self.assertErrorRegexes(errors, {"e1": r"typing.Dict\[_K, _V].*2.*1",
                                     "e2": r"typing.List\[_T].*1.*2",
                                     "e3": r"Union.*x"})

  def test_print_unsolvable(self):
    _, errors = self.InferWithErrors("""
      from typing import List
      def f(x: List[nonsense], y: str, z: float):  # name-error
        pass
      f({nonsense}, "", "")  # name-error  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected:.*x: list.*Actual.*x: set"})

  def test_print_union_of_containers(self):
    _, errors = self.InferWithErrors("""
      def f(x: str):
        pass
      if __random__:
        x = dict
      else:
        x = [float]
      f(x)  # wrong-arg-types[e]
    """)
    error = r"Actual.*Union\[List\[Type\[float\]\], Type\[dict\]\]"
    self.assertErrorRegexes(errors, {"e": error})

  def test_wrong_brackets(self):
    _, errors = self.InferWithErrors("""
      from typing import List
      def f(x: List(str)):  # not-callable[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"List"})

  def test_interpreter_class_printing(self):
    _, errors = self.InferWithErrors("""
      class Foo: pass
      def f(x: str): pass
      f(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*Foo"})

  def test_print_dict_and_tuple(self):
    _, errors = self.InferWithErrors("""
      from typing import Tuple
      tup = None  # type: Tuple[int, ...]
      dct = None  # type: dict[str, int]
      def f1(x: (int, str)):  # invalid-annotation[e1]
        pass
      def f2(x: tup):  # invalid-annotation[e2]
        pass
      def g1(x: {"a": 1}):  # invalid-annotation[e3]
        pass
      def g2(x: dct):  # invalid-annotation[e4]
        pass
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"(int, str).*Not a type",
        "e2": r"instance of Tuple\[int, \.\.\.\].*Not a type",
        "e3": r"{'a': '1'}.*Not a type",
        "e4": r"instance of Dict\[str, int\].*Not a type"})

  def test_move_union_inward(self):
    _, errors = self.InferWithErrors("""
      def f() -> str:  # invalid-annotation[e]
        y = "hello" if __random__ else 42
        yield y
    """)
    self.assertErrorRegexes(errors, {"e": r"Generator, Iterable or Iterator"})

  def test_inner_class_error(self):
    _, errors = self.InferWithErrors("""
      def f(x: str): pass
      def g():
        class Foo: pass
        f(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x: str.*x: Foo"})

  def test_inner_class_error2(self):
    _, errors = self.InferWithErrors("""
      def f():
        class Foo: pass
        def g(x: Foo): pass
        g("")  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x: Foo.*x: str"})

  def test_clean_namedtuple_names(self):
    # Make sure the namedtuple renaming in _pytd_print correctly extracts type
    # names and doesn't erase other types accidentally.
    _, errors = self.InferWithErrors("""
      import collections
      X = collections.namedtuple("X", "a b c d")
      Y = collections.namedtuple("Z", "")
      W = collections.namedtuple("W", "abc def ghi abc", rename=True)
      def bar(x: str):
        return x
      bar(X(1,2,3,4))  # wrong-arg-types[e1]
      bar(Y())         # wrong-arg-types[e2]
      bar(W(1,2,3,4))  # wrong-arg-types[e3]
      bar({1: 2}.__iter__())  # wrong-arg-types[e4]
      if __random__:
        a = X(1,2,3,4)
      else:
        a = 1
      bar(a)  # wrong-arg-types[e5]
      """)
    self.assertErrorRegexes(errors, {
        "e1": r"x: X", "e2": r"x: Z", "e3": r"x: W",
        "e4": r"Iterator", "e5": r"Union\[int, X\]"})

  def test_argument_order(self):
    _, errors = self.InferWithErrors("""
      def g(f: str, a, b, c, d, e,):
        pass
      g(a=1, b=2, c=3, d=4, e=5, f=6)  # wrong-arg-types[e]
      """)
    self.assertErrorRegexes(errors, {
        "e": r"Expected.*f: str, \.\.\..*Actual.*f: int, \.\.\."})

  def test_conversion_of_generic(self):
    self.InferWithErrors("""
      import os
      def f() -> None:
        return os.walk("/tmp")  # bad-return-type
    """)

  def test_inner_class(self):
    _, errors = self.InferWithErrors("""
      def f() -> int:
        class Foo:
          pass
        return Foo()  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*Foo"})

  def test_nested_proto_class(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo_bar.pyi", """
        from typing import Type
        class _Foo_DOT_Bar: ...
        class Foo:
          Bar = ...  # type: Type[_Foo_DOT_Bar]
      """)
      errors = self.CheckWithErrors("""
        import foo_bar
        def f(x: foo_bar.Foo.Bar): ...
        f(42)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo_bar\.Foo\.Bar"})

  def test_staticmethod_in_error(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A:
          @staticmethod
          def t(a: str) -> None: ...
        """)
      errors = self.CheckWithErrors("""
        from typing import Callable
        import foo
        def f(x: Callable[[int], None], y: int) -> None:
          return x(y)
        f(foo.A.t, 1)  # wrong-arg-types[e]
        """, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e": r"Actually passed: \(x: Callable\[\[str\], None\]"})

  def test_generator_send(self):
    errors = self.CheckWithErrors("""
      from typing import Generator, Any
      def f(x) -> Generator[Any, int, Any]:
        if x == 1:
          yield 1
        else:
          yield "1"

      x = f(2)
      x.send("123")  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\(self, value: int\)"})

  def test_generator_iterator_ret_type(self):
    errors = self.CheckWithErrors("""
      from typing import Iterator
      def f() -> Iterator[str]:
        yield 1  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_generator_iterable_ret_type(self):
    errors = self.CheckWithErrors("""
      from typing import Iterable
      def f() -> Iterable[str]:
        yield 1  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_silence_variable_mismatch(self):
    self.Check("""
      x = [
          0,
      ]  # type: None  # pytype: disable=annotation-type-mismatch
    """)

  def test_assert_type(self):
    _, errors = self.InferWithErrors("""
      from typing import Union
      class A: pass
      def f(x: int, y: str, z):
        assert_type(x, int)
        assert_type(y, int)  # assert-type[e1]
        assert_type(z)  # assert-type[e2]
        if __random__:
          x = A()
        assert_type(x, Union[A, int])
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Expected.*int.*Actual.*str",
        "e2": r"type was Any"
    })

  def test_assert_type_str(self):
    _, errors = self.InferWithErrors("""
      class A: pass
      def f(x: int, y: str, z):
        assert_type(x, 'int')
        assert_type(y, 'int')  # assert-type[e1]
        assert_type(z)  # assert-type[e2]
        if __random__:
          x = A()
        assert_type(x, 'Union[A, int]')
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Expected.*int.*Actual.*str",
        "e2": r"type was Any"
    })

  def test_assert_type_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("pytype_extensions.pyi", """
        def assert_type(*args): ...
      """)
      _, errors = self.InferWithErrors("""
        from typing import Union
        from pytype_extensions import assert_type
        class A: pass
        def f(x: int, y: str, z):
          assert_type(x, int)
          assert_type(y, int)  # assert-type[e1]
          assert_type(z)  # assert-type[e2]
          if __random__:
            x = A()
          assert_type(x, Union[A, int])
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"Expected.*int.*Actual.*str",
          "e2": r"type was Any"
      })


class InPlaceOperationsTest(test_base.TargetPython3BasicTest):
  """Test in-place operations."""

  def _testOp(self, op, symbol):
    errors = self.CheckWithErrors("""
      class A:
        def __%s__(self, x: "A"):
          return None
      def f():
        v = A()
        v %s 3  # unsupported-operands[e]
    """ % (op, symbol))
    self.assertErrorRegexes(errors, {
        "e": r"%s.*A.*int.*__%s__ on A.*A" % (re.escape(symbol), op)})

  def test_isub(self):
    self._testOp("isub", "-=")

  def test_imul(self):
    self._testOp("imul", "*=")

  def test_idiv(self):
    errors = self.CheckWithErrors("""
      class A:
        def __idiv__(self, x: "A"):
          return None
        def __itruediv__(self, x: "A"):
          return None
      def f():
        v = A()
        v /= 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\/\=.*A.*int.*__i(true)?div__ on A.*A"})

  def test_imod(self):
    self._testOp("imod", "%=")

  def test_ipow(self):
    self._testOp("ipow", "**=")

  def test_ilshift(self):
    self._testOp("ilshift", "<<=")

  def test_irshift(self):
    self._testOp("irshift", ">>=")

  def test_iand(self):
    self._testOp("iand", "&=")

  def test_ixor(self):
    self._testOp("ixor", "^=")

  def test_ior(self):
    self._testOp("ior", "|=")

  def test_ifloordiv(self):
    self._testOp("ifloordiv", "//=")


class ErrorTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for errors."""

  def test_nis_wrong_arg_types(self):
    errors = self.CheckWithErrors("""
      from typing import Iterable
      def f(x: Iterable[str]): ...
      f("abc")  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors,
                            {"e": r"str does not match iterables by default"})

  def test_nis_bad_return(self):
    errors = self.CheckWithErrors("""
      from typing import Iterable
      def f() -> Iterable[str]:
        return "abc" # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors,
                            {"e": r"str does not match iterables by default"})

  def test_protocol_mismatch(self):
    _, errors = self.InferWithErrors("""
      class Foo: pass
      next(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__, __next__"})

  def test_protocol_mismatch_partial(self):
    _, errors = self.InferWithErrors("""
      class Foo:
        def __iter__(self):
          return self
      next(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"not implemented on Foo: __next__"})

  def test_generator_send_ret_type(self):
    _, errors = self.InferWithErrors("""
      from typing import Generator
      def f() -> Generator[int, str, int]:
        x = yield 1
        return x  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_silence_parameter_mismatch(self):
    self.Check("""
      def f(
        x: int = 0.0,
        y: str = '',
        **kwargs,
      ):  # pytype: disable=annotation-type-mismatch
        pass
    """)

  @test_utils.skipFromPy((3, 8), "MAKE_FUNCTION opcode lineno changes in 3.8")
  def test_do_not_silence_parameter_mismatch_pre38(self):
    self.CheckWithErrors("""
      def f(
        x: int = 0.0,
        y: str = '',  # annotation-type-mismatch
        **kwargs,
      ):
        pass  # pytype: disable=annotation-type-mismatch
    """)

  @test_utils.skipBeforePy((3, 8), "MAKE_FUNCTION opcode lineno changes in 3.8")
  def test_do_not_silence_parameter_mismatch(self):
    self.CheckWithErrors("""
      def f(  # annotation-type-mismatch
        x: int = 0.0,
        y: str = '',
        **kwargs,
      ):
        pass  # pytype: disable=annotation-type-mismatch
    """)


class MatrixOperationsTest(test_base.TargetPython3FeatureTest):
  """Test matrix operations."""

  def test_matmul(self):
    errors = self.CheckWithErrors("""
      def f():
        return 'foo' @ 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\@.*str.*int.*'__matmul__' on str.*'__rmatmul__' on int"})

  def test_imatmul(self):
    errors = self.CheckWithErrors("""
      class A:
        def __imatmul__(self, x: "A"):
          pass
      def f():
        v = A()
        v @= 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\@.*A.*int.*__imatmul__ on A.*A"})


class UnboundLocalErrorTest(test_base.TargetPython3FeatureTest):
  """Tests for UnboundLocalError.

  It is often confusing to users when a name error is logged due to a local
  variable shadowing one from an outer scope and being referenced before its
  local definition, e.g.:

  def f():
    x = 0
    def g():
      print(x)  # name error!
      x = 1

  In this case, we add some more details to the error message.
  """

  def test_function_in_function(self):
    errors = self.CheckWithErrors("""
      def f(x):
        def g():
          print(x)  # name-error[e]
          x = 0
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Add `nonlocal x` in function 'f\.g' to reference 'x' from "
              r"function 'f'")})

  def test_global(self):
    errors = self.CheckWithErrors("""
      x = 0
      def f():
        print(x)  # name-error[e]
        x = 1
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Add `global x` in function 'f' to reference 'x' from global "
              r"scope")})

  def test_class_in_function(self):
    errors = self.CheckWithErrors("""
      def f():
        x = 0
        class C:
          print(x)  # name-error[e]
          x = 1
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Add `nonlocal x` in class 'f\.C' to reference 'x' from "
              r"function 'f'")})

  def test_deep_nesting(self):
    errors = self.CheckWithErrors("""
      def f():
        def g():
          x = 0
          class C:
            class D:
              print(x)  # name-error[e]
              x = 1
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Add `nonlocal x` in class 'f\.g\.C\.D' to reference 'x' from "
              r"function 'f\.g'")})

  def test_duplicate_names(self):
    # This is a plain old name error; make sure the UnboundLocalError details
    # are *not* printed.
    errors = self.CheckWithErrors("""
      def f1():
        def f2():
          def f3():
            x = 0
        def f3():
          def f4():
            print(x)  # name-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Name 'x' is not defined$"})

  def test_precedence(self):
    errors = self.CheckWithErrors("""
      def f():
        x = 0
        def g():
          x = 1
          def h():
            print(x)  # name-error[e]
            x = 2
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Add `nonlocal x` in function 'f\.g\.h' to reference 'x' from "
              r"function 'f\.g'")})


class ClassAttributeNameErrorTest(test_base.TargetPython3FeatureTest):
  """Tests for name errors on class attributes.

  For code like:
    class C:
      x = 0
      def f(self):
        print(x)  # name error!
  it's non-obvious that 'C.x' needs to be used to reference attribute 'x' from
  class 'C', so we add a hint to the error message.
  """

  def test_nested_classes(self):
    errors = self.CheckWithErrors("""
      class C:
        x = 0
        class D:
          y = 1
          def f(self):
            print(x)  # name-error[e1]
            print(y)  # name-error[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Use 'C\.x' to reference 'x' from class 'C'",
        "e2": r"Use 'C\.D\.y' to reference 'y' from class 'C\.D'"})

  def test_outer_function(self):
    errors = self.CheckWithErrors("""
      def f():
        class C:
          x = 0
          def f(self):
            print(x)  # name-error[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"Use 'C\.x' to reference 'x' from class 'f\.C'"})


class PartiallyDefinedClassNameErrorTest(test_base.TargetPython3FeatureTest):
  """Test for name errors on the attributes of partially defined classes.

  For code like:
    class C:
      x = 0
      class D:
        print(x)  # name error!
  unlike the similar examples in ClassAttributeNameErrorTest, using 'C.x' does
  not work because 'C' has not yet been fully defined. We add this explanation
  to the error message.
  """

  def test_nested_classes(self):
    errors = self.CheckWithErrors("""
      class C:
        x = 0
        class D:
          y = 1
          class E:
            print(x)  # name-error[e1]
            print(y)  # name-error[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": (r"Cannot reference 'x' from class 'C' before the class is fully "
               r"defined"),
        "e2": (r"Cannot reference 'y' from class 'C\.D' before the class is "
               r"fully defined")})

  def test_nested_classes_in_function(self):
    errors = self.CheckWithErrors("""
      def f():
        class C:
          x = 0
          class D:
            print(x)  # name-error[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Cannot reference 'x' from class 'f\.C' before the class is "
              r"fully defined")})

  def test_unbound_local_precedence(self):
    # We should report the UnboundLocalError in preference to one about C not
    # being fully defined, since print(x) would resolve to f.x, not f.C.x, if
    # the redefinition in D were removed.
    errors = self.CheckWithErrors("""
      def f():
        x = 0
        class C:
          x = 1
          class D:
            print(x)  # name-error[e]
            x = 2
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Add `nonlocal x` in class 'f\.C\.D' to reference 'x' from "
              r"function 'f'")})


test_base.main(globals(), __name__ == "__main__")
