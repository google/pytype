"""Tests for handling GenericType."""

from pytype import file_utils
from pytype.tests import test_base


class GenericBasicTest(test_base.TargetPython3BasicTest):
  """Tests for User-defined Generic Type."""

  def testGenericTypeParamsError(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic

      class A(Generic[int]):
        pass
    """)
    self.assertErrorLogIs(errors, [
        (3, "invalid-annotation", "Parameters.*Generic.*must.*type variables")])

  def testMroError(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic, Iterator, Generator, TypeVar

      T = TypeVar('T')

      class A(Generic[T],  Iterator[T], Generator):
        pass
    """)
    self.assertErrorLogIs(errors, [(5, "mro-error")])

  def testTemplateOrderError(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic, TypeVar

      T1 = TypeVar('T1')
      S1 = TypeVar('S1')
      T2 = TypeVar('T2')
      S2 = TypeVar('S2')
      T3 = TypeVar('T3')
      S3 = TypeVar('S3')
      K1 = TypeVar('K1')
      V1 = TypeVar('V1')
      K2 = TypeVar('K2')
      V2 = TypeVar('V2')

      class DictA(Generic[T1, S1]): pass
      class DictB(Generic[T2, S2]): pass
      class DictC(Generic[T3, S3]): pass

      # type parameter sequences: K2, K1, V1, V2
      class ClassA(DictA[K1, V1], DictB[K2, V2], DictC[K2, K1]):
        def func(self, x: K1, y: K2):
          pass

      # type parameter sequences: K1, K2, V1, V2
      class ClassB(Generic[K1, K2, V1, V2], DictA[K1, V1],
                   DictB[K2, V2], DictC[K2, K1]):
        def func(self, x: K1, y: K2):
          pass

      A = ClassA[int, str, int, int]()
      B = ClassB[int, str, int, int]()
      A.func(5, "5") # Error
      A.func("5", 5) # OK
      B.func(5, "5") # OK
      B.func("5", 5) # Error
    """)
    self.assertErrorLogIs(errors, [(31, "wrong-arg-types", r"str.*int"),
                                   (34, "wrong-arg-types", r"int.*str")])

  def testTypeErasureError(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar, Generic

      T = TypeVar('T', int, float)
      S = TypeVar('S')

      class MyClass(Generic[T, S]):
        def __init__(self, x: T = None, y: S = None):
            pass

        def fun(self, x: T, y: S):
            pass

      o1 = MyClass[str, str]()
      o2 = MyClass[int, int]()
      o2.fun("5", 5)
      o2.fun(5, "5")
    """)
    self.assertErrorLogIs(errors, [
        (13, "bad-concrete-type", r"Union\[float, int\].*str"),
        (15, "wrong-arg-types", r"x: int.*x: str"),
        (16, "wrong-arg-types", r"y: int.*y: str")])

  def testInhericPlainGenericError(self):
    _, errors = self.InferWithErrors("""\
     from typing import Generic

     class A(Generic):
       pass
    """)
    self.assertErrorLogIs(
        errors, [(3, "invalid-annotation", r"Cannot inherit.*plain Generic")])

  def testGenericWithDupTypeError(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar

        T = TypeVar('T')
        class A(Generic[T, T]): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(
          errors, [(1, "pyi-error", "Duplicate.*T.*a.A")])

  def testMultiGenericError(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar

        T = TypeVar('T')
        V = TypeVar('V')
        class A(Generic[T], Generic[V]): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(
          errors, [(1, "pyi-error",
                    r"Cannot inherit.*Generic.*multiple times")])

  def testGenericWithTypeMissError(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar, Dict

        K = TypeVar('K')
        V = TypeVar('V')
        class A(Dict[K, V], Generic[K]): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(
          errors, [(1, "pyi-error", r"V.*are not listed in Generic.*a.A")])

  def testClassInFuncError(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar, Generic, Union

      T = TypeVar('T')
      S = TypeVar('S')

      def func(x: T, y: S) -> Union[T, S]:
        class InnerCls1(Generic[T]):
          class InnerCls2(Generic[S]):
            pass

        return x + y
    """)
    self.assertErrorLogIs(
        errors, [(7, "invalid-annotation", r"func.*InnerCls1.*T"),
                 (7, "invalid-annotation", r"func.*InnerCls2.*S")])

  def testClassInClassError(self):
    _, errors = self.InferWithErrors("""\
     from typing import TypeVar, Generic, Iterator

     T = TypeVar('T', int, float, str)
     S = TypeVar('S')

     class MyClass(Generic[T, S]):
       def __init__(self, x: T = None, y: S = None):
         pass

       def f(self, x: T, y: S):
         pass

       class InnerClass1(Iterator[T]):
         pass

     class A(Generic[T]):
       class B(Generic[S]):
         class C(Generic[T]):
           pass
    """)
    self.assertErrorLogIs(errors, [
        (6, "invalid-annotation", r"MyClass.*InnerClass1.*T"),
        (16, "invalid-annotation", r"A.*C.*T")])

  def testSignatureTypeParam(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar, Generic

      T = TypeVar('T', int, float, str)
      S = TypeVar('S')
      V = TypeVar('V')

      class MyClass(Generic[T, S]):
        def __init__(self, x: T = None, y: S = None):
            pass

        def func1(self, x: T, y: S): pass

        def func2(self, x: V): pass

      def func1(x: S): pass

      def func2(x: S) -> S:
        return x

      def func3(x: T): pass
    """)
    self.assertErrorLogIs(
        errors, [(13, "invalid-annotation", r"Invalid type annotation 'V'"),
                 (15, "invalid-annotation", r"Invalid type annotation 'S'")])

  def testPyiOutput(self):
    ty = self.Infer("""
      from typing import TypeVar, Generic

      S = TypeVar('S')
      T = TypeVar('T')
      U = TypeVar('U')
      V = TypeVar('V')

      class MyClass(Generic[T, S]):
        def __init__(self, x: T = None, y: S = None):
            pass

        def fun(self, x: T, y: S):
            pass

      x = MyClass[int, int]()
      y = MyClass(5, 5)
      y.fun("5", "5")

      class A(Generic[T, S]):
        pass

      class B(Generic[T, S]):
        pass

      class C(Generic[U, V], A[U, V], B[U, V]):
        pass

      z = C()

      class D(A[V, U]):
        pass

      a = D()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, Optional, TypeVar, Union

      a = ...  # type: D[nothing, nothing]
      x = ...  # type: MyClass[int, int]
      y = ...  # type: MyClass[Union[int, str], Union[int, str]]
      z = ...  # type: C[nothing, nothing]

      S = TypeVar('S')
      T = TypeVar('T')
      U = TypeVar('U')
      V = TypeVar('V')

      class A(Generic[T, S]):
          pass

      class B(Generic[T, S]):
          pass

      class C(Generic[U, V], A[U, V], B[U, V]):
          pass

      class D(A[V, U]):
          pass

      class MyClass(Generic[T, S]):
          def __init__(self, x: Optional[T] = ..., y: Optional[S] = ...) -> None: ...
          def fun(self, x: T, y: S) -> None: ...
    """)

  def testSignatureTypeError(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic, TypeVar

      T = TypeVar('T')
      V = TypeVar('V')

      class MyClass(Generic[T]):
        def __init__(self, x: T, y: V):
          pass
    """)
    self.assertErrorLogIs(errors, [
        (7, "invalid-annotation", r"V.*Appears only once in the signature")])

  def testTypeParameterWithoutSubstitution(self):
    with file_utils.Tempdir() as d:
      d.create_file("base.pyi", """
        from typing import Generic, Type, TypeVar

        T = TypeVar('T')

        class MyClass(Generic[T]):
          @classmethod
          def ProtoClass(cls) -> Type[T]: ...
      """)
      self.Check("""
        from base import MyClass

        class SubClass(MyClass):
          def func(self):
            self.ProtoClass()
      """, pythonpath=[d.path])

  def testPytdClassInstantiation(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def get(self) -> T: ...
          def put(self, elem: T): ...
      """)
      ty = self.Infer("""
        import a
        b = a.A[int]()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a

        a = ...  # type: module
        b = ...  # type: a.A[int]
      """)

  def testFuncMatchForInterpreterClassError(self):
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar, Generic

      T1 = TypeVar('T1')
      S1 = TypeVar('S1')
      T2 = TypeVar('T2')
      S2 = TypeVar('S2')
      T = TypeVar('T')
      S = TypeVar('S')

      class A(Generic[T1, S1]):
        def fun1(self, x: T1, y: S1):
            pass

      class B(Generic[T2, S2]):
        def fun2(self, x: T2, y: S2):
            pass

      class C(Generic[T, S], A[T, S], B[T, S]):
        def fun3(self, x: T, y: S):
            pass

      o = C[int, int]()
      o.fun1("5", "5")
      o.fun2("5", "5")
      o.fun3("5", "5")
    """)
    self.assertErrorLogIs(errors, [
        (23, "wrong-arg-types", r"int.*str"),
        (24, "wrong-arg-types", r"int.*str"),
        (25, "wrong-arg-types", r"int.*str")])

  def testFuncMatchForPytdClassError(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar, Generic

        T1 = TypeVar('T1')
        S1 = TypeVar('S1')
        T2 = TypeVar('T2')
        S2 = TypeVar('S2')
        T = TypeVar('T')
        S = TypeVar('S')

        class A(Generic[T1, S1]):
          def fun1(self, x: T1, y: S1): ...

        class B(Generic[T2, S2]):
          def fun2(self, x: T2, y: S2): ...

        class C(A[T, S], B[T, S], Generic[T, S]):
          def fun3(self, x: T, y: S): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a

        o = a.C[int, int]()

        o.fun1("5", "5")
        o.fun2("5", "5")
        o.fun3("5", "5")
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (5, "wrong-arg-types", r"int.*str"),
          (6, "wrong-arg-types", r"int.*str"),
          (7, "wrong-arg-types", r"int.*str")])

  def testTypeRenamingError(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic, TypeVar

      T = TypeVar('T', int, float)
      V = TypeVar('V')
      S = TypeVar('S')
      U = TypeVar('U', bound=int)
      W = TypeVar('W')

      class A(Generic[T]): pass
      class B(A[V]): pass

      class C(Generic[V]): pass
      class D(C[T]): pass
      class E(D[S]): pass

      class F(Generic[U]): pass
      class G(F[W]): pass
    """)
    self.assertErrorLogIs(errors, [
        (10, "not-supported-yet", r"Renaming TypeVar `T`.*"),
        (14, "not-supported-yet", r"Renaming TypeVar `T`.*"),
        (17, "not-supported-yet", r"Renaming TypeVar `U`.*")])

  def testTypeParameterConflictError(self):
    ty, errors = self.InferWithErrors("""\
      from typing import Generic, TypeVar

      T = TypeVar('T')
      V = TypeVar('V')
      S = TypeVar('S')
      U = TypeVar('U')

      class A(Generic[T]): pass
      class B(A[V]): pass

      class D(B[S], A[U]): pass
      class E(D[int, str]): pass

      d = D[int, str]()
      e = E()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generic, TypeVar

      d = ...  # type: Any
      e = ...  # type: E

      S = TypeVar('S')
      T = TypeVar('T')
      U = TypeVar('U')
      V = TypeVar('V')

      class A(Generic[T]):
          pass

      class B(A[V]):
          pass

      class D(B[S], A[U]):
          pass

      class E(Any):
          pass
     """)
    self.assertErrorLogIs(errors, [
        (12, "invalid-annotation", r"Conflicting value for TypeVar"),
        (14, "invalid-annotation", r"Conflicting value for TypeVar")])

  def testUnboundTypeParameterError(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic, TypeVar

      T = TypeVar('T')
      U = TypeVar('U')

      class A(Generic[T]): pass
      class B(A): pass
      class D(B, A[U]): pass
    """)
    self.assertErrorLogIs(errors, [
        (8, "invalid-annotation", r"Conflicting value for TypeVar D.U")])

  def testSelfTypeParameter(self):
    # The purpose is to verify there is no infinite recursion
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Sequence, Typing, Generic

        AT = TypeVar("AT", bound=A)
        BT = TypeVar("BT", bound=B)
        CT = TypeVar("CT", bound=C)
        T = TypeVar("T")

        class A(Sequence[AT]): ...
        class B(A, Sequence[BT]): ...
        class C(B, Sequence[CT]): ...

        class D(Sequence[D]): ...
        class E(D, Sequence[E]): ...
        class F(E, Sequence[F]): ...

        class G(Sequence[G[int]], Generic[T]): ...
      """)
      self.Check("""
        import a

        c = a.C()
        f = a.F()
        g = a.G[int]()
      """, pythonpath=[d.path])

  def testAnyMatchAllTypes(self):
    _, errors = self.InferWithErrors("""\
      import collections, typing

      class DictA(collections.OrderedDict, typing.MutableMapping[int, int]):
        pass

      class DictB(typing.MutableMapping[int, int]):
        pass

      class DictC(collections.OrderedDict, DictB):
        pass

      d1 = collections.OrderedDict()
      d2 = DictA()
      d3 = DictC()
      x = d1["123"]
      y = d2["123"]
      z = d3["123"]
    """)
    self.assertErrorLogIs(errors, [(16, "unsupported-operands", r"str.*int"),
                                   (17, "unsupported-operands", r"str.*int")])


class GenericFeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for User-defined Generic Type."""

  def testTypeParameterDuplicated(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Dict
        T = TypeVar("T")
        class A(Dict[T, T], Generic[T]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x[1] = 2
          return x

        d = None  # type: a.A[int]
        ks, vs = d.keys(), d.values()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a

        a = ...  # type: module
        d = ...  # type: a.A[int]
        ks = ...  # type: dict_keys[int]
        vs = ...  # type: dict_values[int]

        def f() -> a.A[int]: ...
      """)


test_base.main(globals(), __name__ == "__main__")
