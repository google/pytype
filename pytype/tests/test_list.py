"""Tests for __builtin__.list."""

from pytype.tests import test_base


class ListTest(test_base.TargetIndependentTest):
  """Tests for __builtin__.list."""

  def test_add(self):
    ty = self.Infer("""
      a = []
      a = a + [42]
      b = []
      b = b + [42]
      b = b + ["foo"]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[int]
      b = ...  # type: List[Union[int, str]]
    """)

  def test_inplace_add(self):
    ty = self.Infer("""
      a = []
      a += [42]
      b = []
      b += [42]
      b += ["foo"]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[int]
      b = ...  # type: List[Union[int, str]]
    """)

  def test_inplace_mutates(self):
    ty = self.Infer("""
      a = []
      b = a
      a += [42]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[int]
      b = ...  # type: List[int]
    """)

  def test_add_string(self):
    ty = self.Infer("""
      a = []
      a += "foo"
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[str]
    """)

  def test_extend_with_empty(self):
    ty = self.Infer("""
      from typing import List
      v = []  # type: List[str]
      for x in []:
        v.extend(x)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      v = ...  # type: List[str]
      x = ...  # type: Any
    """)

  def test_getitem_slot(self):
    ty, errors = self.InferWithErrors("""
      a = [1, '2', 3, 4]
      b = a[1]
      c = 1 if __random__ else 2
      d = a[c]
      e = a["s"]  # unsupported-operands[e]
      f = a[-1]
      g = a[slice(1,2)]  # should be List[str]
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Union
      a = ...  # type: List[Union[int, str]]
      b = ...  # type: str
      c = ...  # type: int
      d = ...  # type: Union[int, str]
      e = ...  # type: Any
      f = ...  # type: int
      g = ...  # type: List[Union[int, str]]
      """)
    self.assertErrorRegexes(errors, {"e": r"__getitem__ on List"})

  def test_index_out_of_range(self):
    ty = self.Infer("""
      a = [0] if __random__ else []
      b = 0
      if b < len(a):
        c = a[b]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      a = ...  # type: List[int]
      b = ...  # type: int
      c = ...  # type: int
    """)


test_base.main(globals(), __name__ == "__main__")
