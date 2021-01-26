"""Tests for PEP-593 typing.Annotated types."""

from pytype.tests import test_base


class AnnotatedTest(test_base.TargetPython3BasicTest):
  """Tests for typing.Annotated types."""

  def test_basic(self):
    ty = self.Infer("""
      from typing_extensions import Annotated
      i = ... # type: Annotated[int, "foo"]
      s: Annotated[str, "foo", "bar"] = "baz"
    """)
    self.assertTypesMatchPytd(ty, """
      i: int
      s: str
    """)

  def test_nested(self):
    ty = self.Infer("""
      from typing import List
      from typing_extensions import Annotated
      i = ... # type: Annotated[Annotated[int, "foo"], "bar"]
      strings = ... # type: Annotated[List[str], "bar"]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      i: int
      strings: List[str]
    """)

  def test_func(self):
    ty = self.Infer("""
      from typing_extensions import Annotated
      def id(x:  Annotated[int, "foo"]):
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def id(x: int) -> int: ...
    """)

  def test_invalid_type(self):
    _, errors = self.InferWithErrors("""
      from typing_extensions import Annotated
      x: Annotated[0, int] = 0  # invalid-annotation[err]
    """)
    self.assertErrorRegexes(errors, {"err": r"Not a type"})

  def test_missing_type(self):
    _, errors = self.InferWithErrors("""
      from typing_extensions import Annotated
      x: Annotated = 0  # invalid-annotation[err]
    """)
    self.assertErrorRegexes(errors, {"err": r"Not a type"})

  def test_missing_annotation(self):
    _, errors = self.InferWithErrors("""
      from typing_extensions import Annotated
      x: Annotated[int] # invalid-annotation[err]
    """)
    self.assertErrorRegexes(errors, {"err": r"must have at least 1 annotation"})


test_base.main(globals(), __name__ == "__main__")
