"""Tests for super()."""

from pytype.tests import test_base


class TestSuperPython3Featue(test_base.TargetPython3FeatureTest):
  """Tests for super()."""

  def test_super_without_args(self):
    ty = self.Infer("""
      from typing import Callable
      class A(object):
        def m_a(self, x: int, y: int) -> int:
          return x + y
      class B(A):
        def m_b(self, x: int, y: int) -> int:
          return super().m_a(x, y)
      b = B()
      i = b.m_b(1, 2)
      class C(A):
        def m_c(self, x: int, y: int) -> Callable[["C"], int]:
          def f(this: "C") -> int:
            return super().m_a(x, y)
          return f
      def call_m_c(c: C, x: int, y: int) -> int:
        f = c.m_c(x, y)
        return f(c)
      i = call_m_c(C(), i, i + 1)
      def make_my_c() -> C:
        class MyC(C):
          def m_c(self, x: int, y: int) -> Callable[[C], int]:
            def f(this: C) -> int:
              super_f = super().m_c(x, y)
              return super_f(self)
            return f
        return MyC()
      def call_my_c(x: int, y: int) -> int:
        c = make_my_c()
        f = c.m_c(x, y)
        return f(c)
      i = call_my_c(i, i + 2)
      class Outer(object):
        class InnerA(A):
          def m_a(self, x: int, y: int) -> int:
            return 2 * super().m_a(x, y)
      def call_inner(a: Outer.InnerA) -> int:
        return a.m_a(1, 2)
      i = call_inner(Outer.InnerA())
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Callable
    class A(object):
      def m_a(self, x: int, y: int) -> int: ...
    class B(A):
      def m_b(self, x: int, y: int) -> int: ...
    class C(A):
      def m_c(self, x: int, y: int) -> Callable[[C], int]: ...
    def call_m_c(c: C, x: int, y: int) -> int: ...
    def make_my_c() -> C: ...
    def call_my_c(x: int, y: int) -> int: ...
    class Outer(object):
      InnerA = ...  # type: type
    def call_inner(a) -> int
    b = ...  # type: B
    i = ...  # type: int
    """)

  def test_super_without_args_error(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        def m(self):
          pass
      class B(A):
        def m(self):
          def f():
            super().m()  # invalid-super-call[e1]
          f()
      def func(x: int):
        super().m()  # invalid-super-call[e2]
      """)
    self.assertErrorRegexes(errors, {"e1": r".*Missing 'self' argument.*",
                                     "e2": r".*Missing __class__ closure.*"})


test_base.main(globals(), __name__ == "__main__")
