"""Tests for __builtin__.list."""

import unittest

from pytype.tests import test_base


class ListTest(test_base.BaseTest):
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
    ty, errors = self.InferWithErrors("""\
      a = [1, '2', 3, 4]
      b = a[1]
      c = 1 if __random__ else 2
      d = a[c]
      e = a["s"]
      f = a[-1]
      g = a[slice(1,2)]  # should be List[str]
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any, List, Union
      a = ...  # type: List[Union[int, str]]
      b = ...  # type: str
      c = ...  # type: int
      d = ...  # type: Union[int, str]
      e = ...  # type: Any
      f = ...  # type: int
      g = ...  # type: List[Union[int, str]]
      """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", "list.__getitem__")])

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


class ListTestPython3(test_base.BaseTest):
  """Tests for __builtin__.list in Python 3."""
  PYTHON_VERSION = (3, 6)

  def test_getitem_slot(self):
    ty, errors = self.InferWithErrors("""\
      a = [1, '2', 3, 4]
      p = a[1]
      q = 1 if __random__ else 2
      r = a[q]
      s = a["s"]
      t = a[-1]
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any, List, Union
      a = ...  # type: List[Union[int, str]]
      p = ...  # type: str
      q = ...  # type: int
      r = ...  # type: Union[int, str]
      s = ...  # type: Any
      t = ...  # type: int
      """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types")])

  @unittest.skip("Requires more precise slice objects")
  def test_getitem_slice(self):
    # Python 3 uses __getitem__ with slice objects instead of __getslice__.
    # Pytype doesn't support slice objects well, so a lot of results here are
    # imprecise. It also means wrong-arg-types won't be detected.
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
      m = a[1:-1]
      n = a[0:0]
      o = a[1:1]
      p = a[1:2]
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
      m = ...  # type: List[Union[int, str]]
      n = ...  # type: List[nothing]
      o = ...  # type: List[nothing]
      p = ...  # type: List[str]
      """)
    self.assertErrorLogIs(errors, [
        (10, "wrong-arg-types"),
        (11, "wrong-arg-types")])

if __name__ == "__main__":
  test_base.main()
