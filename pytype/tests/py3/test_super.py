"""Tests for super()."""

from pytype import file_utils
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
    def call_inner(a) -> int: ...
    b = ...  # type: B
    i = ...  # type: int
    """)

  def test_super_without_args_error(self):
    _, errors = self.InferWithErrors("""
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

  def test_mixin(self):
    self.Check("""
      class Mixin:
        def __init__(self, x, **kwargs):
          super().__init__(**kwargs)
          self.x = x

      class Foo:
        def __init__(self, y):
          self.y = y

      class Bar(Mixin, Foo):
        def __init__(self, x, y):
          return super().__init__(x=x, y=y)
    """)

  def test_classmethod(self):
    self.Check("""
      import abc

      class Foo(metaclass=abc.ABCMeta):
        pass

      class Bar(Foo):
        def __new__(cls):
          return super().__new__(cls)
    """)

  def test_metaclass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Meta(type): ...
        class Foo(metaclass=Meta):
          @classmethod
          def hook(cls): ...
      """)
      self.Check("""
        import foo
        class Bar(foo.Foo):
          @classmethod
          def hook(cls):
            return super().hook()
        class Baz(Bar):
          @classmethod
          def hook(cls):
            return super().hook()
      """, pythonpath=[d.path])

  def test_metaclass_calling_super(self):
    # Regression test distilled from a custom enum module that was already using
    # some pytype disables to squeak past type-checking.
    self.Check("""
      class Meta(type):
        def __init__(cls, name, bases, dct):
          super(Meta, cls).__init__(name, bases, dct)
          cls.hook()  # pytype: disable=attribute-error
      class Foo(metaclass=Meta):
        @classmethod
        def hook(cls):
          pass
      class Bar(Foo):
        @classmethod
        def hook(cls):
          super(Bar, cls).hook()  # pytype: disable=name-error
    """)

  def test_generic_class(self):
    self.Check("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        pass
      class Bar(Foo[T]):
        def __init__(self):
          super().__init__()
      class Baz(Bar[T]):
        pass
    """)

  def test_nested_class(self):
    self.Check("""
      class Parent1:
        def hook(self):
          pass
      class Parent2(Parent1):
        pass
      def _BuildChild(parent):
        class Child(parent):
          def hook(self):
            return super().hook()
        return Child
      Child1 = _BuildChild(Parent1)
      Child2 = _BuildChild(Parent2)
    """)

  def test_namedtuple(self):
    self.Check("""
      from typing import NamedTuple
      class Foo(NamedTuple('Foo', [('x', int)])):
        def replace(self, *args, **kwargs):
          return super()._replace(*args, **kwargs)
    """)


test_base.main(globals(), __name__ == "__main__")
