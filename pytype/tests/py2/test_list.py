"""Tests for __builtin__.list."""

from pytype.tests import test_base


class ListTest(test_base.TargetPython27FeatureTest):
  """Tests for __builtin__.list."""

  # __getslice__ is py2 only
  def test_getslice_slot(self):
    ty, errors = self.InferWithErrors("""\
      a = [1, '2', 3, 4]
      b = a[:]
      c = 1 if __random__ else 2
      d = a[c:2]
      e = a[c:]
      f = a[2:]
      g = a[2:None]
      h = a[None:2]
      i = a[None:None]
      j = a[int:str]
      k = a["s":]
      l = a[1:-1]
      m = a[0:0]
      n = a[1:1]
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any, List, Union
      a = ...  # type: List[Union[int, str]]
      b = ...  # type: List[Union[int, str]]
      c = ...  # type: int
      d = ...  # type: List[str]
      e = ...  # type: List[Union[int, str]]
      f = ...  # type: List[int]
      g = ...  # type: List[int]
      h = ...  # type: List[Union[int, str]]
      i = ...  # type: List[Union[int, str]]
      j = ...  # type: Any
      k = ...  # type: Any
      l = ...  # type: List[Union[int, str]]
      m = ...  # type: List[nothing]
      n = ...  # type: List[nothing]
      """)
    self.assertErrorLogIs(errors, [
        (10, "wrong-arg-types", "list.__getslice__"),
        (11, "wrong-arg-types", "list.__getslice__")])


test_base.main(globals(), __name__ == "__main__")
