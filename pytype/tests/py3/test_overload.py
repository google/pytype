"""Tests for typing.overload."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class OverloadTest(test_base.TargetPython3BasicTest):
  """Tests for typing.overload."""

  def test_simple(self):
    self.Check("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      def f(x):
        return x
    """)

  def test_bad_implementation(self):
    errors = self.CheckWithErrors("""\
      from typing import overload
      @overload
      def f(x: int) -> str:
        pass
      def f(x):
        return x
    """)
    self.assertErrorLogIs(errors, [(6, "bad-return-type", r"str.*int")])

  def test_bad_call(self):
    errors = self.CheckWithErrors("""\
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      def f(x):
        return x
      f("")
    """)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types", r"int.*str")])

  def test_sub_return(self):
    ty = self.Infer("""
      from typing import overload
      @overload
      def f(x: int) -> float:
        pass
      def f(x):
        return x
      v = f(0)
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> float: ...
      v: float
    """)

  def test_multiple_overload(self):
    self.Check("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f() -> None:
        pass
      def f(x=None):
        return x
      f(0)
      f()
    """)

  def test_multiple_overload_bad_implementation(self):
    errors = self.CheckWithErrors("""\
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f(x: str) -> int:
        pass
      def f(x):
        return x
    """)
    self.assertErrorLogIs(errors, [(9, "bad-return-type", "int.*str")])

  def test_multiple_overload_bad_call(self):
    errors = self.CheckWithErrors("""\
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f(x: int, y: str) -> str:
        pass
      def f(x, y=None):
        return x if y is None else y
      f("")
      f(0, 0)
    """)
    self.assertErrorLogIs(errors, [(10, "wrong-arg-types", r"int.*str"),
                                   (11, "wrong-arg-types", r"str.*int")])

  def test_pyi(self):
    src = """
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f(x: str) -> str:
        pass
      def f(x):
        return x
      def g():
        return f
    """
    ty = self.Infer(src, analyze_annotated=False)
    self.assertTrue(
        pytd_utils.ASTeq(ty, self.Infer(src, analyze_annotated=True)))
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      @overload
      def f(x: int) -> int: ...
      @overload
      def f(x: str) -> str: ...
      def g() -> Callable: ...
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      errors = self.CheckWithErrors("""\
        import foo
        foo.f(0)  # ok
        foo.f("")  # ok
        foo.f(0.0)  # error
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types", r"int.*float")])

  def test_method_bad_implementation(self):
    errors = self.CheckWithErrors("""\
      from typing import overload
      class Foo(object):
        @overload
        def f(self, x: int) -> int:
          pass
        @overload
        def f(self, x: str) -> int:
          pass
        def f(self, x):
          return x
    """)
    self.assertErrorLogIs(errors, [(10, "bad-return-type", r"int.*str")])

  def test_method_pyi(self):
    src = """
      from typing import overload
      class Foo(object):
        @overload
        def f(self, x: int) -> int:
          pass
        @overload
        def f(self, x: str) -> str:
          pass
        def f(self, x):
          return x
    """
    ty = self.Infer(src, analyze_annotated=False)
    self.assertTrue(
        pytd_utils.ASTeq(ty, self.Infer(src, analyze_annotated=True)))
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        @overload
        def f(self, x: int) -> int: ...
        @overload
        def f(self, x: str) -> str: ...
    """)

  def test_call_overload(self):
    errors = self.CheckWithErrors("""\
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      f(0)
    """)
    self.assertErrorLogIs(errors, [(5, "not-callable", r"overload")])


test_base.main(globals(), __name__ == "__main__")
