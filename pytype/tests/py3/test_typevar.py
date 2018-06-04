"""Tests for TypeVar."""

from pytype import file_utils
from pytype.tests import test_base


class TypeVarTest(test_base.TargetPython3BasicTest):
  """Tests for TypeVar."""

  def testId(self):
    ty = self.Infer("""

      import typing
      T = typing.TypeVar("T")
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
      w = f("")
    """)
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

      from typing import List, TypeVar
      S = TypeVar("S")  # unused
      T = TypeVar("T")
      def f(x: List[T]) -> T:
        return __any_object__
      v = f(["hello world"])
      w = f([True])
    """)
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

      from typing import List, TypeVar
      T = TypeVar("T")
      def f(x: T) -> List[T]:
        return __any_object__
      v = f(True)
      w = f(3.14)
    """)
    self.assertTypesMatchPytd(ty, """
      T = TypeVar("T")
      def f(x: T) -> typing.List[T]: ...
      v = ...  # type: typing.List[bool]
      w = ...  # type: typing.List[float]
    """)

  def testImportTypeVarNameChange(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        X = TypeVar("X")
      """)
      _, errors = self.InferWithErrors("""\

        # This is illegal: A TypeVar("T") needs to be stored under the name "T".
        from a import T as T2
        from a import X
        Y = X
        def f(x: T2) -> T2: ...
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [
        (3, "invalid-typevar", "T.*T2"),
        (5, "invalid-typevar", "X.*Y"),
    ])

  def testMultipleSubstitution(self):
    ty = self.Infer("""\

      from typing import Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]:
        return __any_object__
      v = f({})
      w = f({"test": 42})
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]: ...
      v = ...  # type: Tuple[Any, Any]
      w = ...  # type: Tuple[int, str]
    """)

  def testUnion(self):
    ty = self.Infer("""\

      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]:
        return __any_object__
      v = f("", 42)
      w = f(3.14, False)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]: ...
      v = ...  # type: Union[str, int]
      w = ...  # type: Union[float, bool]
    """)

  def testBadSubstitution(self):
    _, errors = self.InferWithErrors("""\

      from typing import List, TypeVar
      S = TypeVar("S")
      T = TypeVar("T")
      def f1(x: S) -> List[S]:
        return {x}
      def f2(x: S) -> S:
        return 42  # no error because never called
      def f3(x: S) -> S:
        return 42
      def f4(x: S, y: T, z: T) -> List[S]:
        return [y]
      f3("")
      f3(16)  # ok
      f3(False)
      f4(True, 3.14, 0)
      f4("hello", "world", "domination")  # ok
    """)
    self.assertErrorLogIs(errors, [
        (6, "bad-return-type", r"List\[S\].*set"),
        (10, "bad-return-type", r"str.*int"),
        (10, "bad-return-type", r"bool.*int"),
        (12, "bad-return-type", r"List\[bool\].*List\[Union\[float, int\]\]")])

  def testUseConstraints(self):
    ty, errors = self.InferWithErrors("""\

      from typing import TypeVar
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

  def testTypeParameterType(self):
    ty = self.Infer("""\

      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T:
        return __any_object__
      v = f(int)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T: ...
      v = ...  # type: int
    """)

  def testPrintNestedTypeParameter(self):
    _, errors = self.InferWithErrors("""\

      from typing import List, TypeVar
      T = TypeVar("T", int, float)
      def f(x: List[T]): ...
      f([""])
    """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types", r"List\[Union\[float, int\]\].*List\[str\]")])

  def testConstraintSubtyping(self):
    _, errors = self.InferWithErrors("""\

      from typing import TypeVar
      T = TypeVar("T", int, float)
      def f(x: T, y: T): ...
      f(True, False)  # ok
      f(True, 42)
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Expected.*y: bool.*Actual.*y: int")])

  def testFilterValue(self):
    _, errors = self.InferWithErrors("""\

      from typing import TypeVar
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
    _, errors = self.InferWithErrors("""\

      from typing import TypeVar
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

      from typing import TypeVar
      T = TypeVar("T", int, type(None))
      def f(x: T) -> T:
        return __any_object__
      if __random__:
        x = None
      else:
        x = 3
      v = id(x) if x else 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      import types
      from typing import Optional, TypeVar
      v = ...  # type: int
      x = ...  # type: Optional[int]
      T = TypeVar("T", int, None)
      def f(x: T) -> T: ...
    """)

  def testEnforceNonConstrainedTypeVar(self):
    _, errors = self.InferWithErrors("""\

      from typing import TypeVar
      T = TypeVar("T")
      def f(x: T, y: T): ...
      f(42, True)  # ok
      f(42, "")
      f(42, 16j)  # ok
      f(object(), 42)  # ok
      f(42, object())  # ok
      f(42.0, "")
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"Expected.*y: int.*Actual.*y: str"),
                                   (10, "wrong-arg-types",
                                    r"Expected.*y: float.*Actual.*y: str")])

  def testUselessTypeVar(self):
    _, errors = self.InferWithErrors("""\

      from typing import Tuple, TypeVar
      T = TypeVar("T")
      S = TypeVar("S", int, float)
      def f1(x: T): ...
      def f2() -> T: ...
      def f3(x: Tuple[T]): ...
      def f4(x: Tuple[T, T]): ...  # ok
      def f5(x: S): ...  # ok
      def f6(x: "U"): ...
      def f7(x: T, y: "T"): ...  # ok
      def f8(x: "U") -> "U": ...  # ok
      U = TypeVar("U")
    """)
    self.assertErrorLogIs(errors, [(5, "invalid-annotation"),
                                   (6, "invalid-annotation"),
                                   (7, "invalid-annotation"),
                                   (10, "invalid-annotation")])

  def testUseBound(self):
    ty, errors = self.InferWithErrors("""\

      from typing import TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T:
        return x
      v1 = f(__any_object__)  # ok
      v2 = f(True)  # ok
      v3 = f(42)  # ok
      v4 = f(3.14)  # ok
      v5 = f("")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T
      v1 = ...  # type: float
      v2 = ...  # type: bool
      v3 = ...  # type: int
      v4 = ...  # type: float
      v5 = ...  # type: Any
    """)
    self.assertErrorLogIs(
        errors, [(10, "wrong-arg-types", r"x: float.*x: str")])

  def testBadReturn(self):
    self.assertNoCrash(self.Check, """\

      from typing import AnyStr, Dict

      class Foo(object):
        def f(self) -> AnyStr: return __any_object__
        def g(self) -> Dict[AnyStr, Dict[AnyStr, AnyStr]]:
          return {'foo': {'bar': self.f()}}
    """)

  def testOptionalTypeVar(self):
    _, errors = self.InferWithErrors("""\

      from typing import Optional, TypeVar
      T = TypeVar("T", bound=str)
      def f() -> Optional[T]:
        return 42 if __random__ else None
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(5, "bad-return-type", r"Optional\[T\].*int")])

  def testUnicodeLiterals(self):
    ty = self.Infer("""

      from __future__ import unicode_literals
      import typing
      T = typing.TypeVar("T")
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
    """)
    self.assertTypesMatchPytd(ty, """
      import __future__
      from typing import Any
      typing = ...  # type: module
      unicode_literals = ...  # type: __future__._Feature
      T = TypeVar("T")
      def f(x: T) -> T: ...
      v = ...  # type: int
    """)

  def testAnyAsBound(self):
    self.Check("""

      from typing import Any, TypeVar
      T = TypeVar("T", bound=Any)
      def f(x: T) -> T:
        return x
      f(42)
    """)

  def testAnyAsConstraint(self):
    self.Check("""

      from typing import Any, TypeVar
      T = TypeVar("T", str, Any)
      def f(x: T) -> T:
        return x
      f(42)
    """)


class TypeVarTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for TypeVar in Python 3."""

  def testUseConstraintsFromPyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """\
        from typing import AnyStr, TypeVar
        T = TypeVar("T", int, float)
        def f(x: T) -> T: ...
        def g(x: AnyStr) -> AnyStr: ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f("")
        foo.g(0)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (2, "wrong-arg-types", r"Union\[float, int\].*str"),
          (3, "wrong-arg-types", r"Union\[bytes, str\].*int")])


test_base.main(globals(), __name__ == "__main__")
