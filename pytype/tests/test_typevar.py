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
      def f(x: AnyStr) -> AnyStr:
        return __any_object__
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      AnyStr = TypeVar("AnyStr", str, unicode)
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
        AnyStr = TypeVar("AnyStr", str, unicode)
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
      T = typevar("T", int, str if __any_object__ else unicode)
      T = typevar("T", 0, float)
      T = typevar("T", str)
      # pytype: disable=not-supported-yet
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
        (6, "invalid-typevar", r"constant str"),
        (7, "invalid-typevar", r"unambiguous type"),
        (8, "invalid-typevar", r"unambiguous type"),
        (9, "invalid-typevar", r"0 or more than 1"),
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

  def testPrintConstraints(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      S = TypeVar("S", str, unicode, covariant=True)  # pytype: disable=not-supported-yet
      T = TypeVar("T", str, unicode)
      U = TypeVar("U", List[str], List[unicode])
    """)
    # The "covariant" keyword is ignored for now.
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar
      S = TypeVar("S", str, unicode)
      T = TypeVar("T", str, unicode)
      U = TypeVar("U", List[str], List[unicode])
    """)

  def testUseConstraints(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      def f(x: T) -> T:
        return __any_object__
      v = f("")
      w = f(True)  # ok
      u = f(__any_object__)  # ok
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      T = TypeVar("T", int, float)
      def f(x: T) -> T: ...
      v = ...  # type: Any
      w = ...  # type: bool
      u = ...  # type: int or float
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Union\[float, int\].*str")])

  def testUseConstraintsFromPyi(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """\
        from typing import AnyStr, TypeVar
        T = TypeVar("T", int, float)
        def f(x: T) -> T: ...
        def g(x: AnyStr) -> AnyStr: ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.f("")
        foo.g(0)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (2, "wrong-arg-types", r"Union\[float, int\].*str"),
          (3, "wrong-arg-types", r"Union\[str, unicode\].*int")])

  def testUseAnyStrConstraints(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import AnyStr, TypeVar  # pytype: disable=not-supported-yet
      def f(x: AnyStr, y: AnyStr) -> AnyStr:
        return __any_object__
      v1 = f(__any_object__, u"")  # ok
      v2 = f(__any_object__, 42)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      AnyStr = TypeVar("AnyStr", str, unicode)
      def f(x: AnyStr, y: AnyStr) -> AnyStr: ...
      v1 = ...  # type: unicode
      v2 = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Union\[str, unicode\].*int")])

  def testTypeParameterType(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Type, TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
      def f(x: Type[T]) -> T:
        return __any_object__
      v = f(int)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T: ...
      v = ...  # type: int
    """)

  def testPrintNestedTypeParameter(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      def f(x: List[T]): ...
      f([""])
    """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types", r"List\[Union\[float, int\]\].*List\[str\]")])

  def testInferTypeVars(self):
    ty = self.Infer("""
      def id(x):
        return x
      def wrap_tuple(x, y):
        return (x, y)
      def wrap_list(x, y):
        return [x, y]
      def wrap_dict(x, y):
        return {x: y}
      def return_second(x, y):
        return y
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Tuple, Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def id(x: _T0) -> _T0
      def wrap_tuple(x: _T0, y: _T1) -> Tuple[_T0, _T1]
      def wrap_list(x: _T0, y: _T1) -> List[Union[_T0, _T1]]
      def wrap_dict(x: _T0, y: _T1) -> Dict[_T0, _T1]
      def return_second(x, y: _T1) -> _T1
    """)

  def testInferUnion(self):
    ty = self.Infer("""
      def return_either(x, y):
        return x or y
      def return_arg_or_42(x):
        return x or 42
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def return_either(x: _T0, y: _T1) -> Union[_T0, _T1]
      def return_arg_or_42(x: _T0) -> Union[_T0, int]
    """)

  def testConstraintMismatch(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import AnyStr  # pytype: disable=not-supported-yet
      def f(x: AnyStr, y: AnyStr): ...
      f("", "")  # ok
      f("", u"")
      f(u"", u"")  # ok
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types",
                                    r"Expected.*y: str.*Actual.*y: unicode")])

  def testConstraintSubtyping(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      def f(x: T, y: T): ...
      f(True, False)  # ok
      f(True, 42)
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Expected.*y: bool.*Actual.*y: int")])

  def testFilterValue(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      def f(x: T, y: T): ...
      x = 3
      x = 42.0
      f(x, 3)
      f(x, 42.0)  # ok
    """)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types",
                                    r"Expected.*y: float.*Actual.*y: int")])

  def testFilterClass(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import TypeVar  # pytype: disable=not-supported-yet
      class A(object): pass
      class B(object): pass
      T = TypeVar("T", A, B)
      def f(x: T, y: T): ...
      x = A()
      x.__class__ = B
      f(x, A())
      f(x, B())  # ok
    """)
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types",
                                    r"Expected.*y: B.*Actual.*y: A")])

  def testSplit(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      import types
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, types.NoneType)
      def f(x: T) -> T:
        return __any_object__
      if __any_object__:
        x = None
      else:
        x = 3
      v = id(x) if x else 42
    """)
    self.assertTypesMatchPytd(ty, """
      import types
      from typing import Optional, TypeVar
      types = ...  # type: module
      v = ...  # type: int
      x = ...  # type: Optional[int]
      T = TypeVar("T", int, types.NoneType)
      def f(x: T) -> T: ...
    """)

  def testEnforceNonConstrainedTypeVar(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
      def f(x: T, y: T): ...
      f(42, True)  # ok
      f(42, "")
      f(42, 16j)  # ok
      f(object(), 42)  # ok
      f(42, object())  # ok
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Expected.*y: int.*Actual.*y: str")])

  def testTypeVarInTypeComment(self):
    self.assertNoErrors("""\
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
      x = None  # type: T
      y = None  # type: List[T]
    """)

  def testBaseClassWithTypeVar(self):
    ty, errors = self.InferAndCheck("""\
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
      class A(List[T]): pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar
      T = TypeVar("T")
      class A(List[T]): ...
    """)
    self.assertErrorLogIs(errors, [(3, "not-supported-yet")])

  def testOverwriteBaseClassWithTypeVar(self):
    self.assertNoErrors("""
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
      l = List[T]
      l = list
      class X(l): pass
    """)

  def testBound(self):
    _, errors = self.InferAndCheck("""\
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float, bound=str)  # pytype: disable=not-supported-yet
      S = TypeVar("S", bound="")
      U = TypeVar("U", bound=str)
      V = TypeVar("V", bound=int if __any_object__ else float)
    """)
    self.assertErrorLogIs(errors, [
        (2, "invalid-typevar", r"mutually exclusive"),
        (3, "invalid-typevar", r"Expected.*Type.*Actual.*str"),
        (4, "not-supported-yet"),
        (5, "invalid-typevar", r"unambiguous")])

  def testCovariant(self):
    _, errors = self.InferAndCheck("""\
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", covariant=True)
      S = TypeVar("S", covariant=42)
      U = TypeVar("U", covariant=True if __any_object__ else False)
    """)
    self.assertErrorLogIs(errors, [
        (2, "not-supported-yet"),
        (3, "invalid-typevar", r"Expected.*bool.*Actual.*int"),
        (4, "invalid-typevar", r"constant")])

  def testContravariant(self):
    _, errors = self.InferAndCheck("""\
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", contravariant=True)
      S = TypeVar("S", contravariant=42)
      U = TypeVar("U", contravariant=True if __any_object__ else False)
    """)
    self.assertErrorLogIs(errors, [
        (2, "not-supported-yet"),
        (3, "invalid-typevar", r"Expected.*bool.*Actual.*int"),
        (4, "invalid-typevar", r"constant")])

  def testExtraArguments(self):
    _, errors = self.InferAndCheck("""\
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T", extra_arg=42)
      S = TypeVar("S", *__any_object__)
      U = TypeVar("U", **__any_object__)
    """)
    self.assertErrorLogIs(errors, [
        (2, "invalid-typevar", r"extra_arg"),
        (3, "invalid-typevar", r"\*args"),
        (4, "invalid-typevar", r"\*\*kwargs")])

  def testSimplifyArgsAndKwargs(self):
    ty = self.Infer("""
      from typing import TypeVar  # pytype: disable=not-supported-yet
      constraints = (int, str)
      kwargs = {"covariant": True}
      T = TypeVar("T", *constraints, **kwargs)  # pytype: disable=not-supported-yet
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Tuple, Type, TypeVar
      T = TypeVar("T", int, str)
      constraints = ...  # type: Tuple[Type[int], Type[str]]
      kwargs = ...  # type: Dict[str, bool]
    """)


if __name__ == "__main__":
  test_inference.main()
