"""Tests for structural pattern matching (PEP-634)."""

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy((3, 10), "New syntax in 3.10")
class MatchTest(test_base.BaseTest):
  """Test match statement."""

  def test_basic(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case 1:
            return 'a'
          case 2:
            return 10
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int | str | None: ...
    """)

  def test_default(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case 1:
            return 'a'
          case 2:
            return 10
          case _:
            return 20
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int | str: ...
    """)

  def test_sequence1(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case [a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x) -> Any: ...
    """)

  def test_sequence2(self):
    ty = self.Infer("""
      def f(x: int):
        match x:
          case [a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> None: ...
    """)

  def test_list1(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case [a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int | None: ...
    """)

  def test_list2(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case [a]:
            return a
          case [a, *rest]:
            return rest
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int | list[int] | None: ...
    """)

  @test_base.skip("Exhaustiveness checks not implemented")
  def test_list3(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case []:
            return 0
          case [a]:
            return a
          case [a, *rest]:
            return rest
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int | list[int]: ...
    """)

  def test_list4(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case [*all]:
            return 0
          case _:
            return '1'
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int: ...
    """)

  def test_tuple(self):
    ty = self.Infer("""
      def f(x: tuple[int, str]):
        match x:
          case [a, b]:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: tuple[int, str]) -> str: ...
    """)

  def test_tuple2(self):
    ty = self.Infer("""
      def f(x: tuple[int, str]):
        match x:
          case [a, b, *rest]:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: tuple[int, str]) -> str: ...
    """)


if __name__ == "__main__":
  test_base.main()
