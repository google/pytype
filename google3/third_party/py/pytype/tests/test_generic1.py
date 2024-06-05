"""Tests for handling GenericType."""

from pytype.tests import test_base
from pytype.tests import test_utils


class GenericTest(test_base.BaseTest):
  """Tests for GenericType."""

  def test_basic(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]): pass
        def f() -> A[int]: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> a.A[int]: ...
      """)

  def test_binop(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]): pass
      """)
      ty = self.Infer("""
        from a import A
        def f():
          return A() + [42]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Type
        A = ...  # type: Type[a.A]
        def f() -> List[int]: ...
      """)

  def test_specialized(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Dict[K, V]): pass
        class B(A[str, int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.B()
        def bar():
          x = foo()
          return {list(x.keys())[0]: list(x.values())[0]}
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def foo() -> a.B: ...
        def bar() -> dict[str, int]: ...
      """)

  def test_specialized_mutation(self):
    with test_utils.Tempdir() as d1:
      with test_utils.Tempdir() as d2:
        d1.create_file("a.pyi", """
          from typing import List, TypeVar
          T = TypeVar("T")
          class A(List[T]): pass
        """)
        d2.create_file("b.pyi", """
          import a
          class B(a.A[int]): pass
        """)
        ty = self.Infer("""
          import b
          def foo():
            x = b.B()
            x.extend(["str"])
            return x
          def bar():
            return foo()[0]
        """, pythonpath=[d1.path, d2.path])
        self.assertTypesMatchPytd(ty, """
          import b
          from typing import Union
          def foo() -> b.B: ...
          def bar() -> Union[int, str]: ...
        """)

  def test_specialized_partial(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, TypeVar
        V = TypeVar("V")
        class A(Dict[str, V]): pass
        class B(A[int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.A()
        def bar():
          return list(foo().keys())
        def baz():
          return a.B()
        def qux():
          return list(baz().items())
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Tuple
        import a
        def foo() -> a.A[nothing]: ...
        def bar() -> List[str]: ...
        def baz() -> a.B: ...
        def qux() -> List[Tuple[str, int]]: ...
      """)

  def test_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def bar(self) -> T: ...
        class B(A[int]): ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.B().bar()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        def f() -> int: ...
      """)

  def test_type_parameter_renaming(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        U = TypeVar("U")
        class A(List[U]): pass
        class B(A[int]): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.A()
        def bar():
          return a.B()[0]
        def baz():
          x = a.B()
          x.extend(["str"])
          return x[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        import a
        def foo() -> a.A[nothing]: ...
        def bar() -> int: ...
        def baz() -> Union[int, str]: ...
      """)

  def test_type_parameter_renaming_chain(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, Set, TypeVar, Union
        A = TypeVar("A")
        B = TypeVar("B")
        class Foo(List[A]):
          def foo(self) -> None:
            self = Foo[Union[A, complex]]
        class Bar(Foo[B], Set[B]):
          def bar(self) -> B: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.Bar([42])
          x.foo()
          x.extend(["str"])
          x.add(float(3))
          return x.bar()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        import a
        def f() -> Union[int, float, complex, str]: ...
      """)

  def test_type_parameter_renaming_conflict1(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Tuple, TypeVar
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        T3 = TypeVar("T3")
        class A(Generic[T1]):
          def f(self) -> T1: ...
        class B(Generic[T1]):
          def g(self) -> T1: ...
        class C(A[T2], B[T3]):
          def __init__(self):
            self = C[int, str]
          def h(self) -> Tuple[T2, T3]: ...
      """)
      ty = self.Infer("""
        import a
        v1 = a.C().f()
        v2 = a.C().g()
        v3 = a.C().h()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Tuple
        import a
        v1 = ...  # type: int
        v2 = ...  # type: str
        v3 = ...  # type: Tuple[int, str]
      """)

  def test_type_parameter_renaming_conflict2(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        T3 = TypeVar("T3")
        class A(Generic[T1]):
          def f(self) -> T1: ...
        class B(Generic[T2]):
          def g(self) -> T2: ...
        class C(A[T3], B[T3]):
          def __init__(self):
            self = C[str]
      """)
      ty = self.Infer("""
        import a
        v = a.C().f()
        w = a.C().g()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        v = ...  # type: str
        w = ...  # type: str
      """)

  def test_change_multiply_renamed_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        T3 = TypeVar("T3")
        class A(Generic[T1]):
          def f(self):
            self = A[str]
        class B(Generic[T1]): ...
        class C(A[T2], B[T3]):
          def g(self):
            self= C[int, float]
      """)
      ty = self.Infer("""
        import a
        v = a.C()
        v.f()
        v.g()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        # T1, T2, and T3 are all set to Any due to T1 being an alias for both
        # T2 and T3.
        v: a.C[int, float]
      """)

  def test_type_parameter_deep(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        U = TypeVar("U")
        V = TypeVar("V")
        class A(Generic[U]):
          def bar(self) -> U: ...
        class B(A[V], Generic[V]): ...
        def baz() -> B[int]: ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.baz().bar()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        def f() -> int: ...
      """)

  def test_type_parameter_import(self):
    with test_utils.Tempdir() as d1:
      d1.create_file("a.pyi", """
        T = TypeVar("T")
      """)
      with test_utils.Tempdir() as d2:
        d2.create_file("b.pyi", """
          from typing import Generic, Union
          from a import T
          class A(Generic[T]):
            def __init__(self, x: T) -> None:
              self = A[Union[int, T]]
            def a(self) -> T: ...
        """)
        ty = self.Infer("""
          import b
          def f():
            return b.A("hello world")
          def g():
            return b.A(3.14).a()
        """, pythonpath=[d1.path, d2.path])
        self.assertTypesMatchPytd(ty, """
          import b
          from typing import Union
          def f() -> b.A[Union[int, str]]: ...
          def g() -> Union[int, float]: ...
        """)

  def test_type_parameter_conflict(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        K = TypeVar("K")
        V = TypeVar("V")
        class MyIterable(Generic[T]): pass
        class MyList(MyIterable[T]): pass
        class MyDict(MyIterable[K], Generic[K, V]): pass
        class Custom(MyDict[K, V], MyList[V]): pass
      """)
      ty = self.Infer("""
        import a
        x = a.Custom()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        x = ...  # type: a.Custom[nothing, nothing]
      """)

  def test_type_parameter_ambiguous(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List
        T = TypeVar("T")
        class A(Generic[T]): pass
        class B(A[int]): pass
        class C(List[T], B): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.C()
          return x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> a.C[nothing]: ...
      """)

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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a

        import a
        def f() -> a.A[int]: ...
      """)

  def test_union(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, Union
        class A(List[Union[int, str]]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()
        def g():
          return f()[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        import a
        def f() -> a.A: ...
        def g() -> Union[int, str]: ...
      """)

  def test_multiple_templates(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class MyDict(Generic[K, V]): pass
        class A(MyDict[K, V], List[V]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.extend([42])
          return x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> a.A[nothing, int]: ...
      """)

  def test_multiple_templates_flipped(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, Generic, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class MyList(Generic[V]):
          def __getitem__(self, x: int) -> V: ...
        class A(MyList[V], Dict[K, V]):
          def a(self) -> K: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.update({"hello": 0})
          return x
        def g():
          return f().a()
        def h():
          return f()[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> a.A[str, int]: ...
        def g() -> str: ...
        def h() -> int: ...
      """)

  def test_type_parameter_empty(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def f(self) -> List[T]: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A().f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        def f() -> List[nothing]: ...
      """)

  @test_base.skip("Needs better GenericType support")
  def test_type_parameter_limits(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr, Generic
        class A(Generic[AnyStr]):
          def f(self) -> AnyStr: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A().f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        import a
        def f() -> Union[str, unicode]: ...
      """)

  def test_prevent_infinite_loop_on_type_param_collision(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class Foo(List[T]): pass
      """)
      self.assertNoCrash(self.Check, """
        import a
        def f():
          x = a.Foo()
          x.append(42)
          return x
        g = lambda y: y+1
      """, pythonpath=[d.path])

  def test_template_construction(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, Generic, List, TypeVar
        T = TypeVar("T")
        U = TypeVar("U")
        class A(Dict[T, U], List[T], Generic[T, U]):
          def f(self) -> None:
            self = A[int, str]
          def g(self) -> T: ...
          def h(self) -> U: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x.f()
          return x
        def g():
          return f().g()
        def h():
          return f().h()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import a
        # T was made unsolvable by an AliasingDictConflictError.
        def f() -> a.A[int, str]: ...
        def g() -> int: ...
        def h() -> str: ...
      """)

  def test_aliasing_dict_conflict_error(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, Generic, List, TypeVar
        T = TypeVar("T")
        U = TypeVar("U")
        class A(Dict[T, U], List[T], Generic[T, U]): ...
      """)
      ty = self.Infer("""
        import a
        v = a.A()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import a
        v = ...  # type: a.A[nothing, nothing]
      """)

  def test_recursive_container(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List
        class A(List[A]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()[0]
        def g():
          return a.A()[0][0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> a.A: ...
        def g() -> a.A: ...
      """)

  def test_pytd_subclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          def __init__(self) -> None:
            self = A[str]
          def f(self) -> T: ...
        class B(A): pass
      """)
      ty = self.Infer("""
        import a
        def foo():
          return a.B().f()
        def bar():
          return a.B()[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def foo() -> str: ...
        def bar() -> str: ...
      """)

  def test_interpreter_subclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          def __init__(self) -> None:
            self = A[str]
          def f(self) -> T: ...
      """)
      ty = self.Infer("""
        import a
        class B(a.A): pass
        def foo():
          return B().f()
        def bar():
          return B()[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        class B(a.A): pass
        def foo() -> str: ...
        def bar() -> str: ...
      """)

  def test_instance_attribute(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict, TypeVar
        T1 = TypeVar("T1", int, float)
        T2 = TypeVar("T2", bound=complex)
        class A(Dict[T1, T2]):
          x: T1
          y: T2
      """)
      ty = self.Infer("""
        import a
        def f():
          v = a.A()
          return (v.x, v.y)
        def g():
          v = a.A({0: 4.2})
          return (v.x, v.y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        from typing import Tuple, Union
        def f() -> Tuple[Union[int, float], complex]: ...
        def g() -> Tuple[int, float]: ...
      """)

  def test_instance_attribute_visible(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class MyPattern(Generic[T]):
          pattern = ...  # type: T
          def __init__(self, x: T):
            self = MyPattern[T]
      """)
      ty = self.Infer("""
        import a
        RE = a.MyPattern("")
        def f(x):
          if x:
            raise ValueError(RE.pattern)
        def g():
          return RE.pattern
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        RE = ...  # type: a.MyPattern[str]
        def f(x) -> None: ...
        def g() -> str: ...
      """)

  def test_instance_attribute_change(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        N = TypeVar("N")
        class A(Generic[T]):
          x = ...  # type: T
          def f(self, x: N) -> None:
            self = A[N]
      """)
      ty = self.Infer("""
        import a
        def f():
          inst = a.A()
          inst.f(0)
          inst.x
          inst.f("")
          return inst.x
        def g():
          inst = a.A()
          inst.f(0)
          inst.x = True
          inst.f("")
          return inst.x
        def h():
          inst = a.A()
          inst.f(0)
          x = inst.x
          inst.f("")
          return x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> str: ...
        def g() -> bool: ...
        def h() -> int: ...
      """)

  def test_instance_attribute_inherited(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T", int, float)
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        from typing import TypeVar
        import a
        T = TypeVar("T")
        class B(a.A[T]): pass
        def f():
          return B().x
        def g():
          return B([42]).x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, TypeVar, Union
        import a
        T = TypeVar("T")
        class B(a.A[T]):
          x = ...  # type: Union[int, float]
        def f() -> Union[int, float]: ...
        def g() -> int: ...
      """)

  def test_instance_attribute_set(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          def f(self) -> T: ...
      """)
      ty = self.Infer("""
        import a
        def f():
          inst = a.A()
          inst.x = inst.f()
          return inst.x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import a
        def f() -> Any: ...
      """)

  def test_instance_attribute_conditional(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        import a
        def f(x):
          inst = a.A([4.2])
          if x:
            inst.x = 42
          return inst.x
        def g(x):
          inst = a.A([4.2])
          if x:
            inst.x = 42
          else:
            return inst.x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Optional, Union
        import a
        def f(x) -> Union[int, float]: ...
        def g(x) -> Optional[float]: ...
      """)

  def test_instance_attribute_method(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        class A(List[T]):
          x = ...  # type: T
      """)
      ty = self.Infer("""
        import a
        def f():
          return abs(a.A([42]).x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        def f() -> int: ...
      """)

  def test_inherited_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A1(Generic[T]):
          def f(self) -> T: ...
        class A2(A1): pass
      """)
      ty = self.Infer("""
        import a
        def f(x):
          return x.f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import a
        def f(x) -> Any: ...
      """)

  def test_attribute_on_anything_type_parameter(self):
    """Test that we can access an attribute on "Any"."""
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, List
        class A(List[Any]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          return a.A()[0].someproperty
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import a
        def f() -> Any: ...
      """)

  def test_match_anything_type_parameter(self):
    """Test that we can match "Any" against a formal function argument."""
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any, List
        class A(List[Any]): pass
      """)
      ty = self.Infer("""
        import a
        n = len(a.A()[0])
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        n = ...  # type: int
      """)

  def test_renamed_type_parameter_match(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Iterable, TypeVar
        Q = TypeVar("Q")
        def f(x: Iterable[Q]) -> Q: ...
      """)
      ty = self.Infer("""
        import a
        x = a.f({True: "false"})
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        x = ...  # type: bool
      """)

  def test_type_parameter_union(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar, Union
        K = TypeVar("K")
        V = TypeVar("V")
        class Foo(List[Union[K, V]]):
          def __init__(self):
            self = Foo[int, str]
      """)
      ty = self.Infer("""
        import foo
        v = list(foo.Foo())
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        v = ...  # type: list[Union[int, str]]
      """)

  def test_type_parameter_subclass(self):
    """Test subclassing A[T] with T undefined and a type that depends on T."""
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List
        T = TypeVar("T")
        class A(Generic[T]):
          data = ...  # type: List[T]
      """)
      ty = self.Infer("""
        import a
        class B(a.A):
          def foo(self):
            return self.data
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        class B(a.A):
          data = ...  # type: list
          def foo(self) -> list: ...
      """)

  def test_constrained_type_parameter_subclass(self):
    """Test subclassing A[T] with T undefined and a type that depends on T."""
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List
        T = TypeVar("T", int, str)
        class A(Generic[T]):
          data = ...  # type: List[T]
      """)
      ty = self.Infer("""
        import a
        class B(a.A):
          def foo(self):
            return self.data
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Union
        import a
        class B(a.A):
          data = ...  # type: List[Union[int, str]]
          def foo(self) -> List[Union[int, str]]: ...
      """)

  def test_bounded_type_parameter_subclass(self):
    """Test subclassing A[T] with T undefined and a type that depends on T."""
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, List
        T = TypeVar("T", bound=complex)
        class A(List[T], Generic[T]):
          data = ...  # type: List[T]
      """)
      ty = self.Infer("""
        import a
        class B(a.A):
          def foo(self):
            return self.data
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        class B(a.A):
          data = ...  # type: List[complex]
          def foo(self) -> List[complex]: ...
      """)

  def test_constrained_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T", int, float)
        class A(Generic[T]):
          v = ...  # type: T
        def make_A() -> A: ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.make_A().v
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        v = ...  # type: Union[int, float]
      """)

  def test_bounded_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T", bound=float)
        class A(Generic[T]):
          v = ...  # type: T
        def make_A() -> A: ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.make_A().v
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        v = ...  # type: float
      """)

  def test_mutate_call(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        _T = TypeVar("_T")
        class A(Generic[_T]):
          def to_str(self):
            self = A[str]
          def to_int(self):
            self = A[int]
      """)
      ty = self.Infer("""
        import foo
        a = foo.A()
        a.to_str()
        a.to_int()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        a = ...  # type: foo.A[int]
      """)

  def test_override_inherited_method(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Base(Generic[T]):
          def __init__(self, x: T) -> None: ...
      """)
      ty = self.Infer("""
        import a
        class Derived(a.Base):
          def __init__(self):
            pass
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import a
        class Derived(a.Base):
          def __init__(self) -> None: ...
      """)

  def test_bad_mro(self):
    self.CheckWithErrors("""
      from typing import Iterator, TypeVar
      T = TypeVar('T')
      U = TypeVar('U')
      V = TypeVar('V')

      class A(Iterator[T]):
        pass
      class B(Iterator[U], A[V]):   # mro-error
        pass
    """)

  def test_generic_class_attribute(self):
    # Tests that a reference to a generic class does not trigger pytype's
    # template check for nested generic class definitions.
    self.Check("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def copy(self):
          cls = self.__class__
          return cls()
    """)

  @test_base.skip("b/169446275: TypeVar currently checks for any common parent")
  def test_generic_classes_enforce_types(self):
    # Given two classes C1 and C2 with a common parent class C0, a generic class
    # which is parameterized with C1 should NOT accept C2 or C0.
    self.CheckWithErrors("""
      from typing import Generic, TypeVar, Union
      _T = TypeVar("_T")
      class Clz(Generic[_T]):
        def set(self, val: _T): ...

      class Base: ...

      class SubA(Base): ...
      class SubB(Base): ...

      clz_a: Clz[SubA]
      # TODO(b/169446275): remove this note and test_base.skip() once fixed.
      clz_a.set(SubB())  # wrong-arg-types
      # Safety check (this already works): only common superclass is 'object'.
      clz_a.set(123)  # wrong-arg-types

      # Regression test: subclasses should be allowed.
      clz_base: Clz[Base]
      clz_base.set(SubB())
      # Regression test: Unions should allow all members.
      clz_union: Clz[Union[SubA, SubB]]
      clz_union.set(SubA())
      clz_union.set(SubB())
      # But still prevent incorrect types, including parents.
      clz_union.set(123)  # wrong-arg-types
      # TODO(b/169446275): remove this note and test_base.skip() once fixed.
      clz_union.set(Base())  # wrong-arg-types
    """)


if __name__ == "__main__":
  test_base.main()
