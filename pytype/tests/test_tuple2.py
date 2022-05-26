"""Tests of builtins.tuple."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class TupleTest(test_base.BaseTest):
  """Tests for builtins.tuple."""

  def test_unpack_inline_tuple(self):
    ty = self.Infer("""
      from typing import Tuple
      def f(x: Tuple[str, int]):
        return x
      v1, v2 = f(__any_object__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      def f(x: Tuple[str, int]) -> Tuple[str, int]: ...
      v1 = ...  # type: str
      v2 = ...  # type: int
    """)

  def test_unpack_tuple_or_tuple(self):
    self.Check("""
      def f():
        if __random__:
          return (False, 'foo')
        else:
          return (False, 'foo')
      def g() -> str:
        a, b = f()
        return b
    """)

  def test_unpack_tuple_or_list(self):
    self.Check("""
      def f():
        if __random__:
          return (False, 'foo')
        else:
          return ['foo', 'bar']
      def g() -> str:
        a, b = f()
        return b
    """)

  def test_unpack_ambiguous_tuple(self):
    self.Check("""
      def f() -> tuple:
        return __any_object__
      a, b = f()
    """)

  def test_tuple_printing(self):
    _, errors = self.InferWithErrors("""
      from typing import Tuple
      def f(x: Tuple[str, ...]):
        pass
      def g(y: Tuple[str]):
        pass
      f((42,))  # wrong-arg-types[e1]
      f(tuple([42]))  # wrong-arg-types[e2]
      f(("", ""))  # okay
      g((42,))  # wrong-arg-types[e3]
      g(("", ""))  # wrong-arg-types[e4]
      g(("",))  # okay
      g(tuple([""]))  # okay
    """)
    x = r"Tuple\[str, \.\.\.\]"
    y = r"Tuple\[str\]"
    tuple_int = r"Tuple\[int\]"
    tuple_ints = r"Tuple\[int, \.\.\.\]"
    tuple_str_str = r"Tuple\[str, str\]"
    self.assertErrorRegexes(errors, {
        "e1": r"%s.*%s" % (x, tuple_int),
        "e2": r"%s.*%s" % (x, tuple_ints),
        "e3": r"%s.*%s" % (y, tuple_int),
        "e4": r"%s.*%s" % (y, tuple_str_str)})

  def test_inline_tuple(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class A(Tuple[int, str]): ...
      """)
      self.Check("""
        from typing import Tuple, Type
        import foo
        def f(x: Type[Tuple[int, str]]):
          pass
        def g(x: Tuple[int, str]):
          pass
        f(type((1, "")))
        g((1, ""))
        g(foo.A())
      """, pythonpath=[d.path])

  def test_inline_tuple_error(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class A(Tuple[str, int]): ...
      """)
      _, errors = self.InferWithErrors("""
        from typing import Tuple, Type
        import foo
        def f(x: Type[Tuple[int, str]]):
          pass
        def g(x: Tuple[int, str]):
          pass
        f(type(("", 1)))  # wrong-arg-types[e1]
        g(("", 1))  # wrong-arg-types[e2]
        g(foo.A())  # wrong-arg-types[e3]
      """, pythonpath=[d.path])
      expected = r"Tuple\[int, str\]"
      actual = r"Tuple\[str, int\]"
      self.assertErrorRegexes(errors, {
          "e1": r"Type\[%s\].*Type\[%s\]" % (expected, actual),
          "e2": r"%s.*%s" % (expected, actual),
          "e3": r"%s.*foo\.A" % expected})

  def test_tuple_combination_explosion(self):
    self.Check("""
      from typing import Any, Dict, List, Tuple, Union
      AlphaNum = Union[str, int]
      def f(x: Dict[AlphaNum, Any]) -> List[Tuple]:
        return list(sorted((k, v) for k, v in x.items() if k in {}))
    """)

  def test_tuple_in_container(self):
    ty = self.Infer("""
      from typing import List, Tuple
      def f(l: List[Tuple[int, List[int]]]):
        line, foo = l[0]
        return foo
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple, TypeVar
      def f(l: List[Tuple[int, List[int]]]) -> List[int]: ...
    """)

  def test_mismatched_pyi_tuple(self):
    with file_utils.Tempdir() as d:
      d.create_file("bar.pyi", """
        class Bar(tuple): ...
      """)
      errors = self.CheckWithErrors("""
        from typing import Tuple
        import bar
        def foo() -> Tuple[bar.Bar, bar.Bar]:
          return bar.Bar(None, None)  # wrong-arg-count[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"1.*3"})

  def test_count(self):
    # TODO(b/63407497): Enabling --strict-parameter-checks leads to a
    # wrong-arg-types error on line 3.
    self.options.tweak(strict_parameter_checks=False)
    self.Check("""
      from typing import Optional
      def f(x: Optional[str] = None, y: Optional[str] = None):
        return (x, y).count(None)
      def g():
        return (0, None).count(None)
      def h(x):
        return (x, 0).count(None)
    """)

  def test_empty_pyi_tuple(self):
    foo = self.Infer("""
      from typing import Tuple
      def f(x: Tuple[()]):
        pass
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.CheckWithErrors("""
        from typing import Any
        import foo
        foo.f((Any, Any))  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_match_nothing(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        def integrate() -> Tuple[nothing, nothing]: ...
      """)
      self.CheckWithErrors("""
        import foo
        def f(x):
          return x[::0, 0]  # unsupported-operands
        def g():
          return f(foo.integrate())
      """, pythonpath=[d.path])

  def test_empty_tuple_class(self):
    self.Check("""
      x = ()
      print(x.__class__())
    """)


class TupleTestPython3Feature(test_base.BaseTest):
  """Tests for builtins.tuple."""

  def test_iteration(self):
    ty = self.Infer("""
      class Foo:
        mytuple = (1, "foo", 3j)
        def __getitem__(self, pos):
          return Foo.mytuple.__getitem__(pos)
      r = [x for x in Foo()]  # Py 3 does not leak 'x'
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple, Union
      class Foo:
        mytuple = ...  # type: Tuple[int, str, complex]
        def __getitem__(self, pos: int) -> Union[int, str, complex]: ...
      r = ...  # type: List[Union[int, str, complex]]
    """)

  def test_bad_unpacking_with_slurp(self):
    _, errors = self.InferWithErrors("""
      a, *b, c = (1,)  # bad-unpacking[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"1 value.*2 variables"})

  def test_strptime(self):
    ty = self.Infer("""
      import time
      (year, month, day, hour, minute) = (
          time.strptime('', '%m %d %Y')[0:5])
    """)
    self.assertTypesMatchPytd(ty, """
      import time
      from typing import Union
      year: int
      month: int
      day: int
      hour: int
      minute: int
    """)

  def test_parameterize_builtins_tuple(self):
    self.CheckWithErrors("""
      from __future__ import annotations
      def f(x: tuple[int, int]):
        pass
      f((0,))  # wrong-arg-types
      f((0, 0))  # ok
    """)


if __name__ == "__main__":
  test_base.main()
