"""Tests for TypeVar."""


from pytype import utils
from pytype.tests import test_inference


class TypeVarTest(test_inference.InferenceTest):
  """Tests for TypeVar."""

  def testId(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      T = typing.TypeVar("T")  # pytype: disable=not-supported-yet
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
      w = f("")
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      typing = ...  # type: module
      T = TypeVar("T")
      def f(x: T) -> T: ...
      v = ...  # type: int
      w = ...  # type: str
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testExtractItem(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      S = TypeVar("S")  # unused
      T = TypeVar("T")
      def f(x: List[T]) -> T:
        return __any_object__
      v = f(["hello world"])
      w = f([True])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: typing.List[T]) -> T: ...
      v = ...  # type: str
      w = ...  # type: bool
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testWrapItem(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
      def f(x: T) -> List[T]:
        return __any_object__
      v = f(True)
      w = f(3.14)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      T = TypeVar("T")
      def f(x: T) -> typing.List[T]: ...
      v = ...  # type: typing.List[bool]
      w = ...  # type: typing.List[float]
    """)

  def testAnyStr(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import AnyStr  # pytype: disable=not-supported-yet
      def f(x: AnyStr) -> AnyStr: ...
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      AnyStr = TypeVar("AnyStr")
      def f(x: AnyStr) -> AnyStr: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testAnyStrFunctionImport(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr
      """)
      ty = self.Infer("""
        from a import f
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypesVar
        AnyStr = TypeVar("AnyStr")
        def f(x: AnyStr) -> AnyStr
      """)

  def testUnusedTypeVar(self):
    ty = self.Infer("""
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      T = TypeVar("T")
    """)

  def testImportTypeVar(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """T = TypeVar("T")""")
      ty, errors = self.InferAndCheck("""\
        from a import T
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypeVar
        T = TypeVar("T")
      """)
      self.assertErrorLogIs(errors, [
          (1, "not-supported-yet", "importing TypeVar")
      ])

  def testInvalidTypeVar(self):
    ty, errors = self.InferAndCheck("""\
      from typing import TypeVar
      typevar = TypeVar
      T = typevar()
      T = typevar("T")  # ok
      T = typevar(42)
      T = typevar(str())
      S = typevar("S", covariant=False)  # ok
      T = typevar("T", covariant=False)  # duplicate ok
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      typevar = ...  # type: type
      S = TypeVar("S")
      T = TypeVar("T")
    """)
    self.assertErrorLogIs(errors, [
        (1, "not-supported-yet"),
        (3, "invalid-typevar", r"wrong arguments"),
        (5, "invalid-typevar", r"Expected.*str.*Actual.*int"),
        (6, "invalid-typevar", r"constant string"),
    ])

  def testImportTypeVarNameChange(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        X = TypeVar("X")
      """)
      _, errors = self.InferAndCheck("""\
        from __future__ import google_type_annotations
        # This is illegal: A TypeVar("T") needs to be stored under the name "T".
        from a import T as T2
        from a import X
        Y = X
        def f(x: T2) -> T2: ...
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [
        (3, "not-supported-yet"),
        (3, "invalid-typevar", "T.*T2"),
        (4, "not-supported-yet"),
        (5, "invalid-typevar", "X.*Y"),
    ])

  def testMultipleSubstitution(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Dict, Tuple, TypeVar  # pytype: disable=not-supported-yet
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]:
        return __any_object__
      v = f({})
      w = f({"test": 42})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]: ...
      v = ...  # type: tuple
      w = ...  # type: Tuple[int, str]
    """)

  def testUnion(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import TypeVar, Union  # pytype: disable=not-supported-yet
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]:
        return __any_object__
      v = f("", 42)
      w = f(3.14, False)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]: ...
      v = ...  # type: Union[str, int]
      w = ...  # type: Union[float, bool]
    """)

  def testBadSubstitution(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      S = TypeVar("S")
      T = TypeVar("T")
      def f1(x: S) -> List[S]:
        return {x}
      def f2(x: S) -> S:
        return 42  # no error because never called
      def f3(x: S) -> S:
        return 42
      def f4(x: S, y: T) -> List[S]:
        return [y]
      f3("")
      f3(16)  # ok
      f3(False)
      f4(True, 3.14)
      f4("hello", "world")  # ok
    """)
    self.assertErrorLogIs(errors, [
        (6, "bad-return-type", r"List\[Any\].*Set\[Any\]"),
        (10, "bad-return-type"),
        (12, "bad-return-type", r"List\[bool\].*List\[float\]")])
    # Make sure that the log contains both of the errors at line 10.
    self.assertErrorLogContains(errors, r"10.*bad-return-type.*str.*int")
    self.assertErrorLogContains(errors, r"10.*bad-return-type.*bool.*int")


if __name__ == "__main__":
  test_inference.main()
