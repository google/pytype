"""Tests for handling GenericType."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class GenericBasicTest(test_base.BaseTest):
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
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
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

      a: D[nothing, nothing]
      x: MyClass[int, int]
      y: MyClass[int, int]
      z: C[nothing, nothing]

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
          def __init__(self, x: Optional[T] = ..., y: Optional[S] = ...) -> None:
            self = MyClass[T, S]
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
        errors, {"e": r"V.*appears only once in the function signature"})

  def test_type_parameter_without_substitution(self):
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
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
      class B(A[V]): pass  # bad-concrete-type[e1]

      class C(Generic[V]): pass
      class D(C[T]): pass
      class E(D[S]): pass  # bad-concrete-type[e2]

      class F(Generic[U]): pass
      class G(F[W]): pass  # bad-concrete-type[e3]
    """)
    self.assertErrorSequences(errors, {
        "e1": ["Expected: T", "Actually passed: V",
               "T and V have incompatible"],
        "e2": ["Expected: T", "Actually passed: S",
               "T and S have incompatible"],
        "e3": ["Expected: U", "Actually passed: W",
               "U and W have incompatible"],
    })

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
    with test_utils.Tempdir() as d:
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

  def test_late_annotations(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar

      T = TypeVar('T')

      class A(Generic[T]): ...
      class B(Generic[T]): ...

      class C(A['C']): ...
      class D(A['B[D]']): ...
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')

      class A(Generic[T]): ...
      class B(Generic[T]): ...

      class C(A[C]): ...
      class D(A[B[D]]): ...
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

  def test_return_type_param(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
        def f(self) -> T:
          return self.x
      def g():
        return Foo(0).f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
        def f(self) -> T: ...
      def g() -> int: ...
    """)

  def test_generic_function_in_generic_class(self):
    ty = self.Infer("""
      from typing import Generic, Tuple, TypeVar
      S = TypeVar('S')
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
        def f(self, x: S) -> Tuple[S, T]:
          return (x, self.x)
      def g(x):
        return Foo(0).f('hello world')
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generic, Tuple, TypeVar
      S = TypeVar('S')
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
        def f(self, x: S) -> Tuple[S, T]: ...
      def g(x) -> Tuple[str, int]: ...
    """)

  def test_generic_abc_with_getitem(self):
    # Regression test for b/219709586 - the metaclass should not lead to
    # incorrectly calling __getitem__ on the generic class for type subscripts.
    self.Check("""
      import abc
      from typing import Any, Generic, Optional, Tuple, TypeVar

      T = TypeVar('T')

      class Filterable(Generic[T], abc.ABC):
        @abc.abstractmethod
        def get_filtered(self) -> T:
          pass

      class SequenceHolder(Generic[T], Filterable[Any]):
        def __init__(self, *sequence: Optional[T]) -> None:
          self._sequence = sequence

        def __getitem__(self, key: int) -> Optional[T]:
          return self._sequence[key]

        def get_filtered(self) -> 'SequenceHolder[T]':
          filtered_sequence = tuple(
              item for item in self._sequence if item is not None)
          return SequenceHolder(*filtered_sequence)

      sequence_holder = SequenceHolder('Hello', None, 'World')
    """)

  def test_check_class_param(self):
    errors = self.CheckWithErrors("""
      from typing import Generic, Tuple, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
        def f(self, x: T):
          pass
      foo = Foo(0)
      foo.f(1)  # okay
      foo.f('1')  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected.*int.*Actual.*str"})

  def test_instantiate_parameterized_class(self):
    ty = self.Infer("""
      from typing import Any, Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
      def f(x: Foo[int]):
        return x.x
      def g(x: Any):
        return Foo[int](x)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
      def f(x: Foo[int]) -> int: ...
      def g(x: Any) -> Foo[int]: ...
    """)

  def test_constructor_typevar_container(self):
    ty = self.Infer("""
      from typing import Generic, List, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: List[T]):
          self.x = x
          self.y = x[0]
        def f(self) -> T:
          return self.y
      def g():
        return Foo([0]).f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, List, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: List[T]
        y: T
        def __init__(self, x: List[T]) -> None:
          self = Foo[T]
        def f(self) -> T: ...
      def g() -> int: ...
    """)

  def test_reinherit_generic(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
      # Inheriting from Foo (unparameterized) is equivalent to inheriting from
      # Foo[Any]. This is likely a mistake, but we should still do something
      # reasonable.
      class Bar(Foo, Generic[T]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
      class Bar(Foo, Generic[T]):
        x: Any
    """)

  def test_generic_substitution(self):
    # Tests a complicated use of generics distilled from real user code.
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Dict, Generic, List, Optional, Protocol, TypeVar

        AD = TypeVar('AD', bound=AsDictable)
        T = TypeVar('T')

        class AsDictable(Protocol):
          def _asdict(self) -> Dict[str, Any]: ...
        class AsDictableListField(Field[List[AD]]): ...
        class Field(Generic[T]):
          def __call__(self) -> T: ...
        class FieldDeclaration(Generic[T]):
          def __call__(self) -> T: ...
      """)
      d.create_file("bar.pyi", """
        import foo
        from typing import Any, Dict

        BarFieldDeclaration: foo.FieldDeclaration[foo.AsDictableListField[X]]

        class X:
          def _asdict(self) -> Dict[str, Any]: ...
      """)
      self.Check("""
        import bar
        from typing import Sequence

        def f(x: Sequence[bar.X]):
          pass
        def g():
          f(bar.BarFieldDeclaration()())
      """, pythonpath=[d.path])

  def test_subclass_typevar(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Stack(Generic[T]):
        def peek(self) -> T:
          return __any_object__
      class IntStack(Stack[int]):
        pass
      x = IntStack().peek()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Stack(Generic[T]):
        def peek(self) -> T: ...
      class IntStack(Stack[int]): ...
      x: int
    """)

  def test_inference_with_subclass(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T', int, str)
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
      class Bar(Foo[int]): ...
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T', int, str)
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
      class Bar(Foo[int]):
        x: int
    """)

  def test_rename_bounded_typevar(self):
    self.CheckWithErrors("""
      from typing import Callable, Generic, TypeVar

      T = TypeVar('T', bound=int)
      No = TypeVar('No', bound=float)
      Ok = TypeVar('Ok', bound=bool)

      class Box(Generic[T]):
        def __init__(self, x: T):
          self.x = x
        def error(self, f: Callable[[T], No]) -> 'Box[No]':  # bad-concrete-type
          return Box(f(self.x))  # wrong-arg-types
        def good(self, f: Callable[[T], Ok]) -> 'Box[Ok]':
          return Box(f(self.x))
    """)

  def test_property(self):
    self.Check("""
      from typing import Generic, TypeVar, Union
      T = TypeVar('T', bound=Union[int, str])
      class Foo(Generic[T]):
        @property
        def foo(self) -> T:
          return __any_object__
      x: Foo[int]
      assert_type(x.foo, int)
    """)

  def test_property_with_init_parameter(self):
    self.Check("""
      from typing import Generic, TypeVar, Union
      T = TypeVar('T', bound=Union[int, str])
      class Foo(Generic[T]):
        def __init__(self, foo: T):
          self._foo = foo
        @property
        def foo(self) -> T:
          return self._foo
      x = Foo(0)
      assert_type(x.foo, int)
    """)

  def test_property_with_inheritance(self):
    self.Check("""
      from typing import Generic, TypeVar, Union
      T = TypeVar('T', bound=Union[int, str])
      class Foo(Generic[T]):
        def __init__(self, foo: T):
          self._foo = foo
        @property
        def foo(self) -> T:
          return self._foo
      class Bar(Foo[int]):
        pass
      x: Bar
      assert_type(x.foo, int)
    """)

  def test_pyi_property(self):
    with self.DepTree([("foo.py", """
        from typing import Generic, TypeVar, Union
        T = TypeVar('T', bound=Union[int, str])
        class Foo(Generic[T]):
          @property
          def foo(self) -> T:
            return __any_object__
    """)]):
      self.Check("""
        import foo
        x: foo.Foo[int]
        assert_type(x.foo, int)
      """)

  def test_pyi_property_with_inheritance(self):
    with self.DepTree([("foo.py", """
      from typing import Generic, Type, TypeVar
      T = TypeVar('T')
      class Base(Generic[T]):
        @property
        def x(self) -> Type[T]:
          return __any_object__
      class Foo(Base[T]):
        pass
    """)]):
      self.Check("""
        import foo
        def f(x: foo.Foo):
          return x.x
      """)

  def test_pyi_property_setter(self):
    with self.DepTree([("foo.pyi", """
      from typing import Annotated, Any, Callable, Generic, TypeVar
      ValueType = TypeVar('ValueType')
      class Data(Generic[ValueType]):
        value: Annotated[ValueType, 'property']
      class Manager:
        def get_data(
            self, x: Callable[[ValueType], Any], y: Data[ValueType]
        ) -> Data[ValueType]: ...
    """)]):
      self.Check("""
        import foo
        class Bar:
          def __init__(self, x: foo.Manager):
            self.data = x.get_data(__any_object__, __any_object__)
            self.data.value = None
      """)

  def test_parameterize_generic_with_generic(self):
    with self.DepTree([("foo.pyi", """
      from typing import Generic, TypeVar, Union
      class A: ...
      class B: ...
      T = TypeVar('T', bound=Union[A, B])
      class Foo(Generic[T]): ...
    """)]):
      self.CheckWithErrors("""
        from typing import Any, Generic, TypeVar
        import foo

        T = TypeVar('T')
        class C(Generic[T]):
          pass

        class Bar(foo.Foo[C[Any]]):  # bad-concrete-type
          def __init__(self):
            pass
          def f(self, c: C[Any]):
            pass
      """)


class GenericFeatureTest(test_base.BaseTest):
  """Tests for User-defined Generic Type."""

  def test_type_parameter_duplicated(self):
    with test_utils.Tempdir() as d:
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

  def test_typevar_in_class_attribute(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
      x = Foo[int]().x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
      x: int
    """)

  def test_bad_typevar_in_class_attribute(self):
    errors = self.CheckWithErrors("""
      from typing import Generic, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      class Foo(Generic[T1]):
        x: T2  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"TypeVar\(s\) 'T2' not in scope for class 'Foo'"})

  def test_typevar_in_instance_attribute(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x, y):
          self.x: T = x
          self.y = y  # type: T
      foo = Foo[int](__any_object__, __any_object__)
      x, y = foo.x, foo.y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        x: T
        y: T
        def __init__(self, x, y) -> None: ...
      foo: Foo[int]
      x: int
      y: int
    """)

  def test_bad_typevar_in_instance_attribute(self):
    errors = self.CheckWithErrors("""
      from typing import Generic, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      class Foo(Generic[T1]):
        def __init__(self, x, y):
          self.x: T2 = x  # invalid-annotation[e1]
          self.y = y  # type: T2  # invalid-annotation[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"TypeVar\(s\) 'T2' not in scope for class 'Foo'",
                 "e2": r"TypeVar\(s\) 'T2' not in scope for class 'Foo'"})

  def test_reingest_generic(self):
    foo = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        x1 = foo.Foo(0).x
        x2 = foo.Foo[str](__any_object__).x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        x1: int
        x2: str
      """)

  def test_inherit_from_nested_generic(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo:
        class Bar(Generic[T]):
          pass
        class Baz(Bar[T]):
          pass
      class Qux(Foo.Bar[T]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo:
        class Bar(Generic[T]): ...
        class Baz(Foo.Bar[T]): ...
      class Qux(Foo.Bar[T]): ...
    """)

  def test_mutation_to_unknown(self):
    with self.DepTree([("foo.pyi", """
      from typing import Generic, TypeVar, overload
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      class A(Generic[T1, T2]):
        @overload
        def f(self, x: str) -> None:
          self = A[bytes, T2]
        @overload
        def f(self, x: int) -> None:
          self = A[float, T2]
    """)]):
      self.Check("""
        import foo
        from typing import Any
        a = foo.A[int, int]()
        a.f(__any_object__)
        assert_type(a, foo.A[Any, int])
      """)

  def test_invalid_mutation(self):
    with self.DepTree([
        ("_typing.pyi", """
            from typing import Any
            NDArray: Any
         """), ("my_numpy.pyi", """
            from _typing import NDArray
            from typing import Any, Generic, TypeVar

            _T1 = TypeVar("_T1")
            _T2 = TypeVar("_T2")

            class ndarray(Generic[_T1, _T2]):
                def __getitem__(self: NDArray[Any], key: str) -> NDArray[Any]: ...
        """)]):
      err = self.CheckWithErrors("""
        import my_numpy as np

        def aggregate_on_columns(matrix: np.ndarray):
          matrix = matrix[None, :]  # invalid-signature-mutation[e]
      """)
      self.assertErrorSequences(err, {
          "e": ["ndarray.__getitem__", "self = Any"]
      })

  def test_class_name_prefix(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Alpha(Generic[T]):
        def __init__(self, x: T):
          pass
      class Alphabet(Alpha[str]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Alpha(Generic[T]):
        def __init__(self, x: T):
          self = Alpha[T]
      class Alphabet(Alpha[str]): ...
    """)

  def test_inherit_generic_namedtuple(self):
    self.Check("""
      from typing import AnyStr, Generic, NamedTuple
      class Base(NamedTuple, Generic[AnyStr]):
        x: AnyStr
      class Child(Base[str]):
        pass
      c: Child
      assert_type(c.x, str)
    """)

  def test_inherit_generic_namedtuple_pyi(self):
    with self.DepTree([("foo.pyi", """
      from typing import AnyStr, Generic, NamedTuple
      class Base(NamedTuple, Generic[AnyStr]):
        x: AnyStr
      class Child(Base[str]): ...
    """)]):
      self.Check("""
        import foo
        c: foo.Child
        assert_type(c.x, str)
      """)


if __name__ == "__main__":
  test_base.main()
