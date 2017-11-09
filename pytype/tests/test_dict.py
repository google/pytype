"""Tests for dictionaries."""

from pytype.tests import test_base


class DictTest(test_base.BaseTest):
  """Tests for dictionaries."""

  def testFilteredGetItem(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import Union
      MAP = {0: "foo"}
      def foo(x: Union[int, None]):
        if x is not None:
          return MAP[x]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Union
      MAP = ...  # type: Dict[int, str]
      def foo(x: Union[int, None]) -> Any
    """)


if __name__ == "__main__":
  test_base.main()
