"""Tests of builtins (in pytd/builtins/__builtins__.pytd).

File 3/3. Split into parts to enable better test parallelism.
"""

import unittest


from pytype import abstract
from pytype import utils
from pytype.tests import test_inference


class BuiltinTests2(test_inference.InferenceTest):
  """Tests for builtin methods and classes."""

  def testSuperAttribute(self):
    ty = self.Infer("""
      x = super.__name__
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: str
    """)

  def testSlice(self):
    ty = self.Infer("""
      x1 = [1,2,3][1:None]
      x2 = [1,2,3][None:2]
      x3 = [1,2,3][None:None]
      x4 = [1,2,3][1:3:None]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: List[int]
      x2 = ...  # type: List[int]
      x3 = ...  # type: List[int]
      x4 = ...  # type: List[int]
    """)

  def testImportExternalFunction(self):
    ty = self.Infer("""
      from __builtin__ import next
      v = next(iter([1, 2, 3]))
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: int
    """)

  def testAddStrAndBytearray(self):
    ty = self.Infer("""
      v = "abc" + bytearray()
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: bytearray
    """)

  def testImplicitTypeVarImport(self):
    ty, errors = self.InferAndCheck("v = " + abstract.T)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      v = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(1, "name-error")])

  def testExplicitTypeVarImport(self):
    self.assertNoErrors("""
      from __builtin__ import _T
      _T
    """)

  def testClassOfType(self):
    ty = self.Infer("""
      v = int.__class__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      v = ...  # type: Type[type]
    """)

  def testExceptionMessage(self):
    ty = self.Infer("""
      class MyException(Exception):
        def get_message(self):
          return self.message
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class MyException(Exception):
        def get_message(self) -> str
    """)

  def testIterItems(self):
    ty = self.Infer("""
      lst = list({"a": 1}.iteritems())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      lst = ...  # type: List[Tuple[str, int]]
    """)

  def testSuper(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Type
        def f(x: type): ...
        def g(x: Type[super]): ...
      """)
      ty = self.Infer("""
        from __future__ import google_type_annotations
        from typing import Any, Type
        import foo
        def f(x): ...
        def g(x: object): ...
        def h(x: Any): ...
        def i(x: type): ...
        def j(x: Type[super]): ...
        f(super)
        g(super)
        h(super)
        i(super)
        j(super)
        foo.f(super)
        foo.g(super)
        v = super
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Type
        foo = ...  # type: module
        def f(x) -> None: ...
        def g(x: object) -> None: ...
        def h(x: Any) -> None: ...
        def i(x: type) -> None: ...
        def j(x: Type[super]) -> None: ...
        v = ...  # type: Type[super]
      """)

  @unittest.skip("broken")
  def testClear(self):
    ty = self.Infer("""\
      x = {1, 2}
      x.clear()
      y = {"foo": 1}
      y.clear()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set
      x = ...  # type: Set[nothing]
      y = ...  # type: Dict[nothing, nothing]
    """)

  def testCmp(self):
    ty = self.Infer("""
      if not cmp(4, 4):
        x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
    """)

  def testRepr(self):
    ty = self.Infer("""
      if repr("hello world"):
        x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
    """)

  def testIntInit(self):
    _, errors = self.InferAndCheck("""\
      int()
      int(0)
      int("0")
      int("0", 10)
      int(u"0")
      int(u"0", 10)
      int(0, 1, 2)  # line 7: wrong argcount
      int(0, 1)  # line 8: expected str or unicode, got int for first arg
    """)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-count", r"1.*4"),
                                   (8, "wrong-arg-types",
                                    r"Union\[str, unicode\].*int")])


if __name__ == "__main__":
  test_inference.main()
