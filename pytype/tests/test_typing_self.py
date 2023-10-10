"""Tests for typing.Self."""

from pytype.tests import test_base


class SelfPyiTest(test_base.BaseTest):
  """Tests for typing.Self usage in type stubs."""

  def test_instance_method_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), foo.A)
        assert_type(B().f(), B)
      """)

  def test_classmethod_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        @classmethod
        def f(cls) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A.f(), foo.A)
        assert_type(B.f(), B)
      """)

  def test_new_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def __new__(cls) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A(), foo.A)
        assert_type(B(), B)
      """)

  def test_parameterized_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self) -> list[Self]: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), "List[foo.A]")
        assert_type(B().f(), "List[B]")
      """)

  def test_parameter(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self, other: Self) -> bool: ...
    """)]):
      errors = self.CheckWithErrors("""
        import foo
        class B(foo.A):
          pass
        B().f(B())  # ok
        B().f(0)  # wrong-arg-types[e]
      """)
      self.assertErrorSequences(
          errors, {"e": ["Expected", "B", "Actual", "int"]})

  def test_nested_class(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        class B:
          def f(self) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class C(foo.A.B):
          pass
        assert_type(foo.A.B().f(), foo.A.B)
        assert_type(C().f(), C)
      """)


if __name__ == "__main__":
  test_base.main()
