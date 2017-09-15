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

  def testSliceAttributes(self):
    ty = self.Infer("""
      v = slice(1)
      start = v.start
      stop = v.stop
      step = v.step
      indices = v.indices(0)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Tuple
      v = ...  # type: slice
      start = ...  # type: Optional[int]
      stop = ...  # type: Optional[int]
      step = ...  # type: Optional[int]
      indices = ...  # type: Tuple[int, int, int]
    """)

  def testNextFunction(self):
    ty = self.Infer("""
      a = next(iter([1, 2, 3]))
      b = next(iter([1, 2, 3]), default = 4)
      c = next(iter([1, 2, 3]), "hello")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: Union[int, str]
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

  def testNewlines(self):
    with utils.Tempdir() as d:
      d.create_file("newlines.txt", """\
          1
          2
          3
          """)
      self.assertNoErrors("""\
          with open("newlines.txt", "rU") as f:
            for line in f:
              print line
            print f.newlines
          """)

  def testInitWithUnicode(self):
    self.assertNoErrors("""
        int(u"123.0")
        float(u"123.0")
        complex(u"123.0")
    """)

  def testIOWrite(self):
    self.assertNoErrors("""
        import sys
        sys.stdout.write(bytearray([1,2,3]))
    """)

  def testHasAttrNone(self):
    self.assertNoCrash("hasattr(int, None)")

  def testNumberAttrs(self):
    ty = self.Infer("""\
      a = (42).denominator
      b = (42).numerator
      c = (42).real
      d = (42).imag
      e = (3.14).conjugate()
      f = (3.14).is_integer()
      g = (3.14).real
      h = (3.14).imag
      i = (2j).conjugate()
      j = (2j).real
      k = (2j).imag
    """)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: int
      d = ...  # type: int
      e = ...  # type: float
      f = ...  # type: bool
      g = ...  # type: float
      h = ...  # type: float
      i = ...  # type: complex
      j = ...  # type: float
      k = ...  # type: float
    """)

  def testFilename(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      def foo(s: str) -> str:
        return s
      foo(__file__)
      """)

  def testBuiltins(self):
    # This module doesn't exist, on Python 2. However, it exists in typeshed, so
    # make sure that we don't break (report pyi-error) when we import it.
    self.assertNoErrors("""
      import builtins  # pytype: disable=import-error
    """)

  def testSpecialBuiltinTypes(self):
    _, errors = self.InferAndCheck("""\
      isinstance(1, int)
      isinstance(1, "no")
      issubclass(int, object)
      issubclass(0, 0)
      issubclass(int, 0)
      hasattr(str, "upper")
      hasattr(int, int)
      """)
    self.assertErrorLogIs(errors, [
        (2, "wrong-arg-types"),
        (4, "wrong-arg-types"),
        (5, "wrong-arg-types"),
        (7, "wrong-arg-types"),
    ])

  def testUnpackList(self):
    ty = self.Infer("""
      x = [1, ""]
      a, b = x
      x.append(2)
      c, d, e = x
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: list[int or str]
      a = ...  # type: int
      b = ...  # type: str
      c = ...  # type: int or str
      d = ...  # type: int or str
      e = ...  # type: int or str
    """)


if __name__ == "__main__":
  test_inference.main()
