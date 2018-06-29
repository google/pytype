"""Tests for TypeVar."""

from pytype import file_utils
from pytype.tests import test_base


class TypeVarTest(test_base.TargetIndependentTest):
  """Tests for TypeVar."""

  def testUnusedTypeVar(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      T = TypeVar("T")
    """)

  def testImportTypeVar(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """T = TypeVar("T")""")
      ty = self.Infer("""\
        from a import T
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypeVar
        T = TypeVar("T")
      """)

  def testInvalidTypeVar(self):
    ty, errors = self.InferWithErrors("""\
      from typing import TypeVar
      typevar = TypeVar
      T = typevar()
      T = typevar("T")  # ok
      T = typevar(42)
      T = typevar(str())
      T = typevar("T", str, int if __random__ else float)
      T = typevar("T", 0, float)
      T = typevar("T", str)
      # pytype: disable=not-supported-yet
      S = typevar("S", covariant=False)  # ok
      T = typevar("T", covariant=False)  # duplicate ok
      # pytype: enable=not-supported-yet
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      typevar = ...  # type: type
      S = TypeVar("S")
      T = TypeVar("T")
    """)
    self.assertErrorLogIs(errors, [
        (3, "invalid-typevar", r"wrong arguments"),
        (5, "invalid-typevar", r"Expected.*str.*Actual.*int"),
        (6, "invalid-typevar", r"constant str"),
        (7, "invalid-typevar", r"unambiguous type"),
        (8, "invalid-typevar", r"Expected.*_1: type.*Actual.*_1: int"),
        (9, "invalid-typevar", r"0 or more than 1"),
    ])

  def testPrintConstraints(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S", int, float, covariant=True)  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
    """, deep=False)
    # The "covariant" keyword is ignored for now.
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
    """)

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
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def return_either(x: _T0, y: _T1) -> Union[_T0, _T1]
      def return_arg_or_42(x: _T0) -> Union[_T0, int]
    """)

  def testTypeVarInTypeComment(self):
    _, errors = self.InferWithErrors("""\
      from typing import List, TypeVar
      T = TypeVar("T")
      x = None  # type: T
      y = None  # type: List[T]
    """)
    self.assertErrorLogIs(errors, [(3, "not-supported-yet"),
                                   (4, "not-supported-yet")])

  def testBaseClassWithTypeVar(self):
    ty, errors = self.InferWithErrors("""\
      from typing import List, TypeVar
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
    self.Check("""
      from typing import List, TypeVar
      T = TypeVar("T")
      l = List[T]
      l = list
      class X(l): pass
    """)

  def testBound(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar
      T = TypeVar("T", int, float, bound=str)
      S = TypeVar("S", bound="")
      U = TypeVar("U", bound=str)  # ok
      V = TypeVar("V", bound=int if __random__ else float)
    """)
    self.assertErrorLogIs(errors, [
        (2, "invalid-typevar", r"mutually exclusive"),
        (3, "invalid-typevar", r"Expected.*type.*Actual.*str"),
        (5, "invalid-typevar", r"unambiguous")])

  def testCovariant(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar
      T = TypeVar("T", covariant=True)
      S = TypeVar("S", covariant=42)
      U = TypeVar("U", covariant=True if __random__ else False)
    """)
    self.assertErrorLogIs(errors, [
        (2, "not-supported-yet"),
        (3, "invalid-typevar", r"Expected.*bool.*Actual.*int"),
        (4, "invalid-typevar", r"constant")])

  def testContravariant(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar
      T = TypeVar("T", contravariant=True)
      S = TypeVar("S", contravariant=42)
      U = TypeVar("U", contravariant=True if __random__ else False)
    """)
    self.assertErrorLogIs(errors, [
        (2, "not-supported-yet"),
        (3, "invalid-typevar", r"Expected.*bool.*Actual.*int"),
        (4, "invalid-typevar", r"constant")])

  def testDontPropagatePyval(self):
    # in functions like f(x: T) -> T, if T has constraints we should not copy
    # the value of constant types between instances of the typevar.
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        AnyInt = TypeVar('AnyInt', int)
        def f(x: AnyInt) -> AnyInt
      """)
      ty = self.Infer("""
        import a
        if a.f(0):
          x = 3
        if a.f(1):
          y = 3
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
        y = ...  # type: int
      """)

  def testPropertyTypeParam(self):
    # We should allow property signatures of the form f(self: T) -> X[T]
    # without complaining about the class not being parametrised over T
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List
      T = TypeVar('T')
      class A(object):
          @property
          def foo(self: T) -> List[T]: ...
      class B(A): ...
      """)
      ty = self.Infer("""
        import a
        x = a.A().foo
        y = a.B().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        x = ...  # type: List[a.A]
        y = ...  # type: List[a.B]
      """)

  def testPropertyTypeParam2(self):
    # Test for classes inheriting from Generic[X]
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U')
      class A(Generic[U]):
          @property
          def foo(self: T) -> List[T]: ...
      class B(A, Generic[U]): ...
      def make_A() -> A[int]: ...
      def make_B() -> B[int]: ...
      """)
      ty = self.Infer("""
        import a
        x = a.make_A().foo
        y = a.make_B().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        x = ...  # type: List[a.A[int]]
        y = ...  # type: List[a.B[int]]
      """)

  # Skipping due to b/66005735
  @test_base.skip("Type parameter bug")
  def testPropertyTypeParam3(self):
    # Don't mix up the class parameter and the property parameter
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U')
      class A(Generic[U]):
          @property
          def foo(self: T) -> List[U]: ...
      def make_A() -> A[int]: ...
      """)
      ty = self.Infer("""
        import a
        x = a.make_A().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: List[int]
      """)

  def testPropertyTypeParamWithConstraints(self):
    # Test setting self to a constrained type
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U', int, str)
      X = TypeVar('X', int)
      class A(Generic[U]):
          @property
          def foo(self: A[X]) -> List[X]: ...
      def make_A() -> A[int]: ...
      """)
      ty = self.Infer("""
        import a
        x = a.make_A().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        a = ...  # type: module
        x = ...  # type: List[int]
      """)

  def testClassMethodTypeParam(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Type
      T = TypeVar('T')
      class A(object):
          @classmethod
          def foo(self: Type[T]) -> List[T]: ...
      class B(A): ...
      """)
      ty = self.Infer("""
        import a
        v = a.A.foo()
        w = a.B.foo()
        x = a.A().foo()
        y = a.B().foo()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        v = ...  # type: List[a.A]
        w = ...  # type: List[a.B]
        x = ...  # type: List[a.A]
        y = ...  # type: List[a.B]
      """)

  def testMetaclassPropertyTypeParam(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, Type, List
      T = TypeVar('T')
      class Meta():
        @property
        def foo(self: Type[T]) -> List[T]

      class A(metaclass=Meta):
        pass
      """)
      ty = self.Infer("""
        import a
        x = a.A.foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        x = ...  # type: List[a.A]
      """)

  def testTopLevelUnion(self):
    ty = self.Infer("""
      from typing import TypeVar
      if __random__:
        T = TypeVar("T")
      else:
        T = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      T = ...  # type: Any
    """)

  def testStoreTypeVarInDict(self):
    """Convert a typevar to Any when stored as a dict value."""
    # See abstract.Dict.setitem_slot for why this is needed.
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T")
      a = {'key': T}
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, TypeVar
      a = ...  # type: Dict[str, Any]
      T = TypeVar('T')
    """)


test_base.main(globals(), __name__ == "__main__")
