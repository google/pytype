"""Tests for PEP-593 typing.Annotated types."""

from pytype import file_utils
from pytype.tests import test_base


class AnnotatedTest(test_base.TargetPython3FeatureTest):
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

  def test_annotated_in_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Annotated
        class A:
          x: Annotated[int, 'tag'] = ...
      """)
      ty = self.Infer("""
        import a
        x = a.A().x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a: module
        x: int
      """)

  def test_annotated_type_in_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Annotated
        class Foo:
          w: int
        class A:
          x: Annotated[Foo, 'tag'] = ...
      """)
      ty = self.Infer("""
        import a
        x = a.A().x.w
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a: module
        x: int
      """)

  def test_subclass_annotated_in_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Annotated
        class A:
          x: Annotated[int, 'tag1', 'tag2'] = ...
      """)
      ty = self.Infer("""
        import a
        class B(a.A):
          pass
        x = B().x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a: module
        class B(a.A): ...
        x: int
      """)


test_base.main(globals(), __name__ == "__main__")
