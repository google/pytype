"""Tests for bad-return-type errors."""

from pytype.tests import test_base


class TestReturns(test_base.BaseTest):
  """Tests for bad-return-type."""

  def test_implicit_none(self):
    self.CheckWithErrors("""
      def f(x) -> int:
        pass  # bad-return-type
    """)

  def test_implicit_none_with_decorator(self):
    self.CheckWithErrors("""
      def decorator(f):
        return f
      @decorator
      def f(x) -> int:
        '''docstring'''  # bad-return-type
    """)

  def test_if(self):
    # NOTE(b/233047104): The implict `return None` gets reported at the end of
    # the function even though there is also a correct return on that line.
    self.CheckWithErrors("""
      def f(x) -> int:
        if x:
          pass
        else:
          return 10  # bad-return-type
    """)

  def test_nested_if(self):
    self.CheckWithErrors("""
      def f(x) -> int:
        if x:
          if __random__:
            pass
          else:
            return 'a'  # bad-return-type
        else:
          return 10
        pass  # bad-return-type
    """)

  def test_with(self):
    self.CheckWithErrors("""
      def f(x) -> int:
        with open('foo'):
          if __random__:
            pass
          else:
            return 'a'  # bad-return-type  # bad-return-type
    """)

  def test_nested_with(self):
    self.CheckWithErrors("""
      def f(x) -> int:
        with open('foo'):
          if __random__:
            with open('bar'):
              if __random__:
                pass
              else:
                return 'a'  # bad-return-type  # bad-return-type
    """)

  def test_no_return_any(self):
    self.options.set_feature_flags({"no-return-any"})
    self.CheckWithErrors("""
      from typing import Any

      def f(x: Any):
        return x  # bad-return-type
    """)


if __name__ == "__main__":
  test_base.main()
