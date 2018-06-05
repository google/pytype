"""Tests for dictionaries."""

from pytype.tests import test_base


class DictTest(test_base.TargetIndependentTest):
  """Tests for dictionaries."""

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

  def testUpdateEmpty(self):
    ty = self.Infer("""
      from typing import Dict
      d1 = {}
      d2 = None  # type: Dict[str, int]
      d1.update(d2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d1 = ...  # type: Dict[str, int]
      d2 = ...  # type: Dict[str, int]
    """)


test_base.main(globals(), __name__ == "__main__")
