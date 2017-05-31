"""Tests for inline annotations."""


from pytype.tests import test_inference


class AnyStrTest(test_inference.InferenceTest):
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


if __name__ == "__main__":
  test_inference.main()
