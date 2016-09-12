
"""Tests for typing.py."""

import os
from pytype.tests import test_inference


class TypingTest(test_inference.InferenceTest):
  """Tests for typing.py."""


  _TEMPLATE = """
    from __future__ import google_type_annotations
    from typing import List, Union, Sequence
    def f(s: %(annotation)s):
      return s
    f(%(arg)s)
  """

  def _test_match(self, arg, annotation):
    self.assertNoErrors(self._TEMPLATE % locals())

  def _test_no_match(self, arg, annotation):
    _, errors = self.InferAndCheck(self._TEMPLATE % locals())
    self.assertNotEqual(0, len(errors))

  def test_list(self):
    self._test_match("[1, 2, 3]", "List")
    self._test_match("[1, 2, 3]", "List[int]")
    self._test_match("[1, 2, 3.1]", "List[Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "List[int]")

  def test_sequence(self):
    self._test_match("[1, 2, 3]", "Sequence")
    self._test_match("[1, 2, 3]", "Sequence[int]")
    self._test_match("(1, 2, 3.1)", "Sequence[Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "Sequence[int]")


if __name__ == "__main__":
  test_inference.main()
