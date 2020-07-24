"""Tests for handling GenericType."""

from pytype import file_utils
from pytype.tests import test_base


class GenericBasicTest(test_base.TargetPython3BasicTest):
  """Tests for User-defined Generic Type."""

  def test_generic_type_params_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Generic

      class A(Generic[int]):  # invalid-annotation[e]
        pass
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Parameters.*Generic.*must.*type variables"})

  def test_mro_error(self):
    self.InferWithErrors("""
      from typing import Generic, Iterator, Generator, TypeVar

      T = TypeVar('T')

      class A(Generic[T],  Iterator[T], Generator):  # mro-error
        pass
    """)

  def test_template_order_error(self):
    _, errors = self.InferWithErrors("""
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
      A.func(5, "5") # wrong-arg-types[e1]
      A.func("5", 5) # OK
      B.func(5, "5") # OK
      B.func("5", 5) # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"str.*int", "e2": r"int.*str"})

  def test_type_erasure_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Optional, TypeVar, Generic

      T = TypeVar('T', int, float)
      S = TypeVar('S')

      class MyClass(Generic[T, S]):
        def __init__(self, x: Optional[T] = None, y: Optional[S] = None):
            pass

        def fun(self, x: T, y: S):
            pass

      o1 = MyClass[str, str]()  # bad-concrete-type[e1]
      o2 = MyClass[int, int]()
      o2.fun("5", 5)  # wrong-arg-types[e2]
      o2.fun(5, "5")  # wrong-arg-types[e3]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Union\[float, int\].*str",
                                     "e2": r"x: int.*x: str",
                                     "e3": r"y: int.*y: str"})

  def test_inheric_plain_generic_error(self):
    _, errors = self.InferWithErrors("""
     from typing import Generic

     class A(Generic):  # invalid-annotation[e]
       pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Cannot inherit.*plain Generic"})

  def test_generic_with_dup_type_error(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar

        T = TypeVar('T')
        class A(Generic[T, T]): ...
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"Duplicate.*T.*a.A"})

  def test_multi_generic_error(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar

        T = TypeVar('T')
        V = TypeVar('V')
        class A(Generic[T], Generic[V]): ...
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e": r"Cannot inherit.*Generic.*multiple times"})

  def test_generic_with_type_miss_error(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar, Dict

        K = TypeVar('K')
        V = TypeVar('V')
        class A(Dict[K, V], Generic[K]): ...
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e": r"V.*are not listed in Generic.*a.A"})

  def test_class_in_func_error(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar, Generic, Union

      T = TypeVar('T')
      S = TypeVar('S')

      def func(x: T, y: S) -> Union[T, S]:
        class InnerCls1(Generic[T]):  # invalid-annotation[e1]  # invalid-annotation[e2]
          class InnerCls2(Generic[S]):
            pass

        return x + y
    """)
    self.assertErrorRegexes(errors, {"e1": r"func.*InnerCls2.*S",
                                     "e2": r"func.*InnerCls1.*T"})

  def test_class_in_class_error(self):
    _, errors = self.InferWithErrors("""
     from typing import Optional, TypeVar, Generic, Iterator

     T = TypeVar('T', int, float, str)
     S = TypeVar('S')

     class MyClass(Generic[T, S]):  # invalid-annotation[e1]
       def __init__(self, x: Optional[T] = None, y: Optional[S] = None):
         pass

       def f(self, x: T, y: S):
         pass

       class InnerClass1(Iterator[T]):
         pass

     class A(Generic[T]):  # invalid-annotation[e2]
       class B(Generic[S]):
         class C(Generic[T]):
           pass
    """)
    self.assertErrorRegexes(errors, {"e1": r"MyClass.*InnerClass1.*T",
                                     "e2": r"A.*C.*T"})

  def test_signature_type_param(self):
    _, errors = self.InferWithErrors("""
      from typing import Optional, TypeVar, Generic

      T = TypeVar('T', int, float, str)
      S = TypeVar('S')
      V = TypeVar('V')

      class MyClass(Generic[T, S]):
        def __init__(self, x: Optional[T] = None, y: Optional[S] = None):
            pass

        def func1(self, x: T, y: S): pass

        def func2(self, x: V): pass  # invalid-annotation[e1]

      def func1(x: S): pass  # invalid-annotation[e2]

      def func2(x: S) -> S:
        return x

      def func3(x: T): pass
    """)
    self.assertErrorRegexes(errors, {"e1": r"Invalid type annotation 'V'",
                                     "e2": r"Invalid type annotation 'S'"})

  def test_pyi_output(self):
    ty = self.Infer("""
      from typing import Optional, TypeVar, Generic

      S = TypeVar('S')
      T = TypeVar('T')
      U = TypeVar('U')
      V = TypeVar('V')

      class MyClass(Generic[T, S]):
        def __init__(self, x: Optional[T] = None, y: Optional[S] = None):
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

  def test_signature_type_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Generic, TypeVar

      T = TypeVar('T')
      V = TypeVar('V')

      class MyClass(Generic[T]):
        def __init__(self, x: T, y: V):  # invalid-annotation[e]
          pass
    """)
    self.assertErrorRegexes(
        errors, {"e": r"V.*Appears only once in the signature"})

  def test_type_parameter_without_substitution(self):
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

  def test_pytd_class_instantiation(self):
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

  def test_func_match_for_interpreter_class_error(self):
    _, errors = self.InferWithErrors("""
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
      o.fun1("5", "5")  # wrong-arg-types[e1]
      o.fun2("5", "5")  # wrong-arg-types[e2]
      o.fun3("5", "5")  # wrong-arg-types[e3]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"int.*str", "e2": r"int.*str", "e3": r"int.*str"})

  def test_func_match_for_pytd_class_error(self):
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
      _, errors = self.InferWithErrors("""
        import a

        o = a.C[int, int]()

        o.fun1("5", "5")  # wrong-arg-types[e1]
        o.fun2("5", "5")  # wrong-arg-types[e2]
        o.fun3("5", "5")  # wrong-arg-types[e3]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e1": r"int.*str", "e2": r"int.*str", "e3": r"int.*str"})

  def test_type_renaming_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Generic, TypeVar

      T = TypeVar('T', int, float)
      V = TypeVar('V')
      S = TypeVar('S')
      U = TypeVar('U', bound=int)
      W = TypeVar('W')

      class A(Generic[T]): pass
      class B(A[V]): pass  # not-supported-yet[e1]

      class C(Generic[V]): pass
      class D(C[T]): pass
      class E(D[S]): pass  # not-supported-yet[e2]

      class F(Generic[U]): pass
      class G(F[W]): pass  # not-supported-yet[e3]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Renaming TypeVar `T`.*",
                                     "e2": r"Renaming TypeVar `T`.*",
                                     "e3": r"Renaming TypeVar `U`.*"})

  def test_type_parameter_conflict_error(self):
    ty, errors = self.InferWithErrors("""
      from typing import Generic, TypeVar

      T = TypeVar('T')
      V = TypeVar('V')
      S = TypeVar('S')
      U = TypeVar('U')

      class A(Generic[T]): pass
      class B(A[V]): pass

      class D(B[S], A[U]): pass
      class E(D[int, str]): pass  # invalid-annotation[e1]

      d = D[int, str]()  # invalid-annotation[e2]
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
    self.assertErrorRegexes(errors, {"e1": r"Conflicting value for TypeVar",
                                     "e2": r"Conflicting value for TypeVar"})

  def test_unbound_type_parameter_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Generic, TypeVar

      T = TypeVar('T')
      U = TypeVar('U')

      class A(Generic[T]): pass
      class B(A): pass
      class D(B, A[U]): pass  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Conflicting value for TypeVar D.U"})

  def test_self_type_parameter(self):
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

  def test_any_match_all_types(self):
    _, errors = self.InferWithErrors("""
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
      y = d2["123"]  # unsupported-operands[e1]
      z = d3["123"]  # unsupported-operands[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"str.*int", "e2": r"str.*int"})

  def test_no_self_annot(self):
    self.Check("""
      from typing import Any, Generic, List, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, children: List['Foo[Any]']):
          pass
    """)

  def test_illegal_self_annot(self):
    errors = self.CheckWithErrors("""
      from typing import Any, Generic, List, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self: 'Foo', children: List['Foo[Any]']):
          pass  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"self.*__init__"})

  def test_parameterized_forward_reference(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')

      v = None  # type: "Foo[int]"

      class Foo(Generic[T]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')
      v: Foo[int]
      class Foo(Generic[T]): ...
    """)

  def test_bad_parameterized_forward_reference(self):
    errors = self.CheckWithErrors("""
      from typing import Generic, TypeVar
      T = TypeVar('T')

      v = None  # type: "Foo[int, str]"  # invalid-annotation[e]

      class Foo(Generic[T]):
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"1.*2"})

  def test_recursive_class(self):
    self.Check("""
      from typing import List
      class Foo(List["Foo"]):
        pass
    """)

  def test_type_parameter_count(self):
    self.Check("""
      from typing import Generic, List, TypeVar

      T = TypeVar('T')
      SomeAlias = List[T]

      class Foo(Generic[T]):
        def __init__(self, x: T, y: SomeAlias):
          pass

      def f(x: T) -> SomeAlias:
        return [x]
    """)


class GenericFeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for User-defined Generic Type."""

  def test_type_parameter_duplicated(self):
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

  def test_typevar_under_decorator(self):
    self.Check("""
      import abc
      from typing import Generic, Tuple, TypeVar
      T = TypeVar('T')
      class Foo(abc.ABC, Generic[T]):
        @abc.abstractmethod
        def parse(self) -> Tuple[T]:
          raise NotImplementedError()
    """)


test_base.main(globals(), __name__ == "__main__")
