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

  def testPop(self):
    ty = self.Infer("""
      d = {"a": 42}
      v1 = d.pop("a")
      v2 = d.pop("b", None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[str, int]
      v1 = ...  # type: int
      v2 = ...  # type: None
    """)

  def testBadPop(self):
    ty, errors = self.InferWithErrors("""\
      d = {"a": 42}
      v = d.pop("b")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      d = ...  # type: Dict[str, int]
      v = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(2, "key-error", r"b")])

  def testAmbiguousPop(self):
    ty = self.Infer("""
      d = {"a": 42}
      k = None  # type: str
      v1 = d.pop(k)
      v2 = d.pop(k, None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
      d = ...  # type: Dict[str, int]
      k = ...  # type: str
      v1 = ...  # type: int
      v2 = ...  # type: Optional[int]
    """)

  def testPopFromAmbiguousDict(self):
    ty = self.Infer("""
      d = {}
      k = None  # type: str
      v = None  # type: int
      d[k] = v
      v1 = d.pop("a")
      v2 = d.pop("a", None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
      d = ...  # type: Dict[str, int]
      k = ...  # type: str
      v = ...  # type: int
      v1 = ...  # type: int
      v2 = ...  # type: Optional[int]
    """)

  def testObjectInDict(self):
    errors = self.CheckWithErrors("""\
      from __future__ import google_type_annotations
      from typing import Any, Dict
      def objectIsStr() -> Dict[str, Any]:
        return {object(): ""}
    """)
    self.assertErrorLogIs(errors, [(4, "bad-return-type")])


if __name__ == "__main__":
  test_base.main()
