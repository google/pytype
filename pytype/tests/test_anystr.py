"""Tests for inline annotations."""


from pytype import utils
from pytype.tests import test_base


class AnyStrTest(test_base.BaseTest):
  """Tests for issues related to AnyStr."""

  def testCallable(self):
    """Tests Callable + AnyStr."""
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import AnyStr, Callable

      def f1(f: Callable[[AnyStr], AnyStr]):
        f2(f)
      def f2(f: Callable[[AnyStr], AnyStr]):
        pass
      """)

  def testUnknownAgainstMultipleAnyStr(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Any, Dict, Tuple, AnyStr

      def foo(x: Dict[Tuple[AnyStr], AnyStr]): ...
      foo(__any_object__)
    """)

  def testMultipleUnknownAgainstMultipleAnyStr(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import AnyStr, List
      def foo(x: List[AnyStr], y: List[AnyStr]): ...
      foo(__any_object__, [__any_object__])
    """)

  def testTypeParameters(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr
      """)
      ty = self.Infer("""
        import a
        if a.f(""):
          x = 3
        if a.f("hello"):
          y = 3
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
        y = ...  # type: int
      """)


if __name__ == "__main__":
  test_base.main()
