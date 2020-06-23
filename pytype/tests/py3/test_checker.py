"""Tests for --check."""

from pytype.tests import test_base


class CheckerTest(test_base.TargetPython3BasicTest):
  """Tests for --check."""

  def test_set(self):
    self.Check("""
      from typing import List, Set
      def f(data: List[str]):
        data = set(x for x in data)  # type: Set[str]
        g(data)
      def g(data: Set[str]):
        pass
    """)

  def test_recursive_forward_reference(self):
    errorlog = self.CheckWithErrors("""
      class X(object):
        def __init__(self, val: "X"):
          pass
      def f():
        X(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"X.*int"})

  def test_bad_return_type_inline(self):
    errorlog = self.CheckWithErrors("""
      from typing import List
      def f() -> List[int]:
        return [object()]  # bad-return-type[e]
      f()[0] += 1
    """)
    self.assertErrorRegexes(errorlog, {"e": r"List\[int\].*List\[object\]"})

  def test_use_varargs_and_kwargs(self):
    self.Check("""
      class A(object):
        pass
      def f(*args: A, **kwargs: A):
        for arg in args:
          pass
        for kwarg in kwargs:
          pass
    """)

  def test_nested_none_type(self):
    self.Check("""
      from typing import List, Union
      def f1() -> Union[None]:
        pass
      def f2() -> List[None]:
        return [None]
      def g1(x: Union[None]):
        pass
      def g2(x: List[None]):
        pass
    """)

  def test_inner_class_init(self):
    self.Check("""
      from typing import List
      class A:
        def __init__(self):
          self.x = 42
      def f(v: List[A]):
        return v[0].x
      def g() -> List[A]:
        return [A()]
      def h():
        return g()[0].x
    """)

  def test_recursion(self):
    self.Check("""
      class A:
        def __init__(self, x: "B"):
          pass
      class B:
        def __init__(self):
          self.x = 42
          self.y = A(self)
    """)

  def test_bad_dict_value(self):
    errorlog = self.CheckWithErrors("""
      from typing import Dict
      def f() -> Dict[str, int]:
        return {"x": 42.0}  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"int.*float"})

  def test_instance_as_annotation(self):
    errorlog = self.CheckWithErrors("""
      def f():
        pass
      def g(x: f):  # invalid-annotation[e1]
        pass
      def h(x: 3):  # invalid-annotation[e2]
        pass
    """)
    self.assertErrorRegexes(
        errorlog, {"e1": r"instance of Callable.*x", "e2": r"3.*x"})

  def test_bad_generator(self):
    errorlog = self.CheckWithErrors("""
      from typing import Generator
      def f() -> Generator[str, None, None]:
        for i in range(3):
          yield i  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"str.*int"})

  def test_multiple_parameter_bindings(self):
    errorlog = self.CheckWithErrors("""
      from typing import List
      def f(x) -> List[int]:
        return ["", x]  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"List\[int\].*List\[str\]"})

  def test_no_param_binding(self):
    errorlog = self.CheckWithErrors("""
      def f() -> None:
        x = []
        return x  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"None.*List\[nothing\]"})

  def test_attribute_in_incomplete_instance(self):
    errorlog = self.CheckWithErrors("""
      from typing import List
      class Foo(object):
        def __init__(self, other: "List[Foo]"):
          self.x = other[0].x  # okay
          # No "y" on List[Foo]
          self.y = other.y  # attribute-error[e1]
          # No "z" on Type[Foo]
          self.z = Foo.z  # attribute-error[e2]
    """)
    self.assertErrorRegexes(errorlog, {"e1": r"y.*List\[Foo\]",
                                       "e2": r"z.*Type\[Foo\]"})

  def test_bad_getitem(self):
    errorlog = self.CheckWithErrors("""
      def f(x: int):
        return x[0]  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"int.*int"})

  def test_bad_annotation_container(self):
    errorlog = self.CheckWithErrors("""
      class A(object):
        pass
      def f(x: int[str]):  # not-indexable[e1]
        pass
      def g(x: A[str]):  # not-indexable[e2]
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e1": r"Generic", "e2": r"Generic"})


test_base.main(globals(), __name__ == "__main__")
