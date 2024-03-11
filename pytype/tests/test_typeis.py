"""Tests for TypeIs (PEP 742)."""

from pytype.tests import test_base


class TypeIsTest(test_base.BaseTest):
  """Tests for typing.TypeIs."""

  def test_positive_narrowing(self):
    self.Check("""
      from typing_extensions import TypeIs

      def is_str(val: object) -> TypeIs[str]:
        return isinstance(val, str)

      def f(val: object):
        if is_str(val):
          assert_type(val, str)
    """)

  def test_negative_narrowing(self):
    self.Check("""
      from typing import Union
      from typing_extensions import TypeIs

      def is_str(val: object) -> TypeIs[str]:
        return isinstance(val, str)

      def f(val: Union[int, str]):
        if is_str(val):
          assert_type(val, str)
        else:
          assert_type(val, int)
    """)

  def test_keep_more_specific_type(self):
    self.Check("""
      from typing import Any, Sequence, Union
      from typing_extensions import TypeIs

      def is_sequence(val: object) -> TypeIs[Sequence[Any]]:
        return isinstance(val, Sequence)

      def f(val: Union[int, Sequence[int]]):
        if is_sequence(val):
          assert_type(val, Sequence[int])
        else:
          assert_type(val, int)
    """)

  def test_check_compatibility(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import TypeIs
      def is_str(val: int) -> TypeIs[str]:  # invalid-function-definition[e]
        return isinstance(val, str)
    """)
    self.assertErrorSequences(errors, {"e": ["TypeIs[str]", "input type int"]})

  def test_pyi(self):
    with self.DepTree([("foo.pyi", """
      from typing_extensions import TypeIs
      def is_str(val: object) -> TypeIs[str]: ...
    """)]):
      self.Check("""
        import foo
        from typing import Union

        def f(val: object):
          if foo.is_str(val):
            assert_type(val, str)

        def g(val: Union[int, str]):
          if foo.is_str(val):
            assert_type(val, str)
          else:
            assert_type(val, int)
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import TypeIs
      def is_str(val: object) -> TypeIs[str]:
        return isinstance(val, str)
    """)]):
      self.Check("""
        import foo
        def f(val: object):
          if foo.is_str(val):
            assert_type(val, str)
      """)


if __name__ == "__main__":
  test_base.main()
