"""Tests for the dataclasses overlay."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestDataclass(test_base.BaseTest):
  """Tests for @dataclass."""

  def test_basic(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        z: str
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        z: str
        def __init__(self, x: bool, y: int, z: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: 'Foo'
        y: str
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
    """)

  def test_redefine(self):
    """The first annotation should determine the order."""
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: int
        y: int
        x: str = 'hello'
        y = 10
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        x: str = ...
        y: int = ...
        def __init__(self, x: str = ..., y: int = ...) -> None: ...
    """)

  def test_redefine_as_method(self):
    ty, errors = self.InferWithErrors("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: str = 'hello'
        y: int = 10
        def x(self):  # annotation-type-mismatch[e]
          return 10
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        x: str = ...
        y: int = ...
        def __init__(self, x: str = ..., y: int = ...) -> None: ...
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Annotation: str.*Assignment: Callable"})

  def test_no_init(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass(init=False)
      class Foo:
        x: bool
        y: int
        z: str
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        z: str
    """)

  def test_explicit_init(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass(init=True)
      class Foo:
        x: bool
        y: int
        def __init__(self, a: bool):
          self.x = a
          self.y = 0
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        def __init__(self, a: bool) -> None: ...
    """)

  def test_field(self):
    ty = self.Infer("""
      from typing import List
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: bool = dataclasses.field(default=True)
        y: List[int] = dataclasses.field(default_factory=list)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, List, Union
      @dataclasses.dataclass
      class Foo:
        x: bool = ...
        y: List[int] = ...
        def __init__(self, x: bool = ..., y: List[int] = ...) -> None: ...
    """)

  def test_type_mismatch(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: bool = 10  # annotation-type-mismatch
    """)

  def test_type_mismatch_on_none(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: int = None  # annotation-type-mismatch
    """)

  def test_field_type_mismatch(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: bool = dataclasses.field(default=10)  # annotation-type-mismatch
    """)

  def test_factory_type_mismatch(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: bool = dataclasses.field(default_factory=set)  # annotation-type-mismatch
    """)

  def test_factory_type_mismatch_output(self):
    err = self.CheckWithErrors("""
      import dataclasses
      from typing import Any, List, Union
      def f() -> Union[int, str]:
        if __random__:
          return 1
        else:
          return "hello"
      @dataclasses.dataclass
      class Foo:
        x: List[int] = dataclasses.field(default_factory=f) # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(err, {"e": r"Union\[int, str\]"})

  def test_field_no_init(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: bool = dataclasses.field(default=True)
        y: int = dataclasses.field(init=False)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict
      @dataclasses.dataclass
      class Foo:
        x: bool = ...
        y: int
        def __init__(self, x: bool = ...) -> None: ...
    """)

  def test_field_init_no_default(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        x: bool = dataclasses.field()
        y: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        def __init__(self, x: bool, y: int) -> None: ...
    """)

  def test_bad_default_param_order(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()  # invalid-function-definition>=3.11
      class Foo:  # invalid-function-definition<3.11
        x: int = 10
        y: str
    """)

  def test_any(self):
    self.Check("""
      import dataclasses
      from typing import Any

      @dataclasses.dataclass
      class Foo:
        foo: Any = None
    """)

  def test_instantiate_field_type(self):
    self.Check("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        def foo(self):
          for field in dataclasses.fields(self):
            field.type()
    """)

  def test_subclass(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo:
        w: float
        x: bool = dataclasses.field(default=True)
        y: int = dataclasses.field(init=False)
      class Bar(Foo):
        def get_w(self):
          return self.w
        def get_x(self):
          return self.x
        def get_y(self):
          return self.y
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        w: float
        x: bool = ...
        y: int
        def __init__(self, w: float, x: bool = ...) -> None: ...
      class Bar(Foo):
        def get_w(self) -> float: ...
        def get_x(self) -> bool : ...
        def get_y(self) -> int: ...
    """)

  def test_subclass_override(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        w: float
        x: bool = dataclasses.field(default=True)
        y: int = dataclasses.field(init=False)
      @dataclasses.dataclass
      class Bar(Foo):
        w: int
        z: bool = dataclasses.field(default=True)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class Foo:
        w: float
        x: bool = ...
        y: int
        def __init__(self, w: float, x: bool = ...) -> None: ...
      @dataclasses.dataclass
      class Bar(Foo):
        w: int
        z: bool = ...
        def __init__(self, w: int, x: bool = ..., z: bool = ...) -> None: ...
    """)

  def test_multiple_inheritance(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class A:
        a: int
      @dataclasses.dataclass
      class B:
        b: str
      @dataclasses.dataclass
      class C(B, A):
        c: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class A:
        a: int
        def __init__(self, a: int) -> None: ...
      @dataclasses.dataclass
      class B:
        b: str
        def __init__(self, b: str) -> None: ...
      @dataclasses.dataclass
      class C(B, A):
        c: int
        def __init__(self, a: int, b: str, c: int) -> None: ...
    """)

  def test_use_late_annotation(self):
    self.Check("""
      import dataclasses
      from typing import Optional

      @dataclasses.dataclass
      class Foo:
        foo: Optional['Foo'] = None

      @dataclasses.dataclass
      class Bar:
        bar: Foo = dataclasses.field(default_factory=Foo)
    """)

  def test_union(self):
    self.Check("""
      import dataclasses
      from typing import Optional
      @dataclasses.dataclass
      class Foo:
        foo: Optional[str] = ''
    """)

  def test_union_late_annotation(self):
    # This test is deliberately complicated to exercise various aspects of late
    # initialization and method body analysis.
    ty = self.Infer("""
      import dataclasses
      from typing import Optional, Union

      @dataclasses.dataclass
      class Tree:
        children: 'Node'

        def get_children(self) -> 'Node':
          return self.children

        def get_leaf(self) -> int:
          if not isinstance(self.children, Tree):
            return self.children.value
          return 0

      @dataclasses.dataclass
      class Root(Tree):
        pass

      @dataclasses.dataclass
      class IntLeaf:
        value: int

      @dataclasses.dataclass
      class StrLeaf:
        label: str

      def get_value(x: Root):
        ch = x.get_children()
        if isinstance(ch, Tree):
          return None
        elif isinstance(ch, IntLeaf):
          return ch.value
        else:
          return ch.label

      Node = Union[Tree, IntLeaf, StrLeaf]
    """)

    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional, Union

      import dataclasses
      Node = Union[IntLeaf, StrLeaf, Tree]

      @dataclasses.dataclass
      class IntLeaf:
          value: int
          def __init__(self, value: int) -> None: ...

      @dataclasses.dataclass
      class StrLeaf:
          label: str
          def __init__(self, label: str) -> None: ...

      @dataclasses.dataclass
      class Tree:
          children: Union[IntLeaf, StrLeaf, Tree]
          def __init__(self, children: Union[IntLeaf, StrLeaf, Tree]) -> None: ...
          def get_children(self) -> Union[IntLeaf, StrLeaf, Tree]: ...
          def get_leaf(self) -> int: ...

      @dataclasses.dataclass
      class Root(Tree):
          def __init__(self, children: Union[IntLeaf, StrLeaf, Tree]) -> None: ...

      def get_value(x: Root) -> Optional[Union[int, str]]: ...
    """)

  def test_reuse_attribute_name(self):
    self.Check("""
      import dataclasses
      from typing import Optional

      @dataclasses.dataclass
      class Foo:
        x: Optional[str] = None

      @dataclasses.dataclass
      class Bar:
        x: str
    """)

  def test_initvar(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass
      class A:
        x: dataclasses.InitVar[str]
        y: int = 10
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class A:
        y: int = ...
        def __init__(self, x: str, y: int = ...) -> None: ...
    """)

  def test_initvar_default(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass
      class A:
        x: dataclasses.InitVar[str] = 'hello'
        y: int = 10
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class A:
        x: dataclasses.InitVar[str] = ...
        y: int = ...
        def __init__(self, x: str = ..., y: int = ...) -> None: ...
    """)

  def test_initvar_late(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass
      class A:
        w: dataclasses.InitVar['Foo']
        x: dataclasses.InitVar['str'] = 'hello'
        y: int = 10

      class Foo:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class A:
        x: dataclasses.InitVar[str] = ...
        y: int = ...
        def __init__(self, w: Foo, x: str = ..., y: int = ...) -> None: ...

      class Foo: ...
    """)

  def test_initvar_inheritance(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass
      class A:
        x: dataclasses.InitVar[str]
        y: int = 10

      @dataclasses.dataclass
      class B(A):
        z: dataclasses.InitVar[int] = 42
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Union
      @dataclasses.dataclass
      class A:
        y: int = ...
        def __init__(self, x: str, y: int = ...) -> None: ...

      @dataclasses.dataclass
      class B(A):
        z: dataclasses.InitVar[int] = ...
        def __init__(self, x: str, y: int = ..., z: int = ...) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      from typing import ClassVar
      import dataclasses

      @dataclasses.dataclass
      class Foo:
        x: ClassVar[int] = 10
        y: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import ClassVar, Dict
      @dataclasses.dataclass
      class Foo:
        y: str = ...
        x: ClassVar[int]
        def __init__(self, y: str = ...) -> None: ...
    """)

  def test_duplicate_inner_class(self):
    ty = self.Infer("""
      import dataclasses
      class Foo:
        @dataclasses.dataclass
        class Inner:
          a: int
      class Bar:
        @dataclasses.dataclass
        class Inner:
          b: str
      Inner1 = Foo.Inner
      Inner2 = Bar.Inner
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict
      class Foo:
        @dataclasses.dataclass
        class Inner:
          a: int
          def __init__(self, a: int) -> None: ...
      class Bar:
        @dataclasses.dataclass
        class Inner:
          b: str
          def __init__(self, b: str) -> None: ...
      Inner1 = Foo.Inner
      Inner2 = Bar.Inner
    """)

  def test_check_field_against_container(self):
    self.Check("""
      import dataclasses
      from typing import List
      @dataclasses.dataclass
      class NHNetConfig:
        passage_list: List[str] = dataclasses.field(
            default_factory=lambda: [chr(i) for i in range(5)])
    """)

  def test_field_wrapper(self):
    ty = self.Infer("""
      import dataclasses
      def field_wrapper(**kwargs):
        return dataclasses.field(**kwargs)
      @dataclasses.dataclass
      class Foo:
        x: int = dataclasses.field(default=0)
        y: int = field_wrapper(default=1)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Any, Dict
      def field_wrapper(**kwargs) -> Any: ...
      @dataclasses.dataclass
      class Foo:
        x: int = ...
        y: int = ...
        def __init__(self, x: int = ..., y: int = ...) -> None: ...
    """)

  def test_property(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        @property
        def z(self) -> str:
          return "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Annotated, Dict
      @dataclasses.dataclass
      class Foo:
        x: bool
        y: int
        z: Annotated[str, 'property']
        def __init__(self, x: bool, y: int) -> None: ...
    """)

  def test_generic(self):
    ty = self.Infer("""
      import dataclasses
      from typing import Generic, TypeVar
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: T
      foo1 = Foo(x=0)
      x1 = foo1.x
      foo2 = Foo[str](x=__any_object__)
      x2 = foo2.x
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict, Generic, TypeVar
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
      foo1: Foo[int]
      x1: int
      foo2: Foo[str]
      x2: str
    """)

  def test_dataclass_attribute_with_getattr(self):
    # Tests that the type of the 'x' attribute is correct in Child.__init__
    # (i.e., the __getattr__ return type shouldn't be used).
    self.Check("""
      import dataclasses
      from typing import Dict, Sequence

      class Base:
        def __init__(self, x: str):
          self.x = x
        def __getattr__(self, name: str) -> 'Base':
          return self

      class Child(Base):
        def __init__(self, x: str, children: Sequence['Child']):
          super().__init__(x)
          self._children: Dict[str, Child] = {}
          for child in children:
            self._children[child.x] = child

      @dataclasses.dataclass
      class Container:
        child: Child
    """)

  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_sticky_kwonly(self):
    self.Check("""
      import dataclasses

      @dataclasses.dataclass
      class A():
        a1: int
        _: dataclasses.KW_ONLY
        a2: int = dataclasses.field(default_factory=lambda: 0)

      @dataclasses.dataclass
      class B(A):
        b1: str

      b = B(1, '1')
    """)

  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_sticky_kwonly_error(self):
    self.CheckWithErrors("""
      import dataclasses

      @dataclasses.dataclass  # dataclass-error>=3.11
      class A:  # dataclass-error<3.11
        a1: int
        _a: dataclasses.KW_ONLY
        a2: int = dataclasses.field(default_factory=lambda: 0)
        _b: dataclasses.KW_ONLY
        a3: int = 10
    """)

  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_sticky_kwonly_override(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass
      class A():
        a1: int
        _: dataclasses.KW_ONLY
        a2: int = dataclasses.field(default_factory=lambda: 0)
        a3: int = dataclasses.field(kw_only=False)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses

      @dataclasses.dataclass
      class A:
        a1: int
        a2: int = ...
        a3: int
        _: dataclasses.KW_ONLY
        def __init__(self, a1: int, a3: int, *, a2: int = ...) -> None: ...
    """)

  @test_utils.skipBeforePy((3, 10), "KW_ONLY is new in 3.10")
  def test_kwonly_and_nonfield_default(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class C:
        _: dataclasses.KW_ONLY
        x: int = 0
        y: str
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      @dataclasses.dataclass
      class C:
        x: int = ...
        y: str
        _: dataclasses.KW_ONLY
        def __init__(self, *, x: int = ..., y: str) -> None: ...
    """)

  @test_utils.skipBeforePy((3, 10), "KW_ONLY is new in 3.10")
  def test_kwonly_and_kwargs(self):
    self.Check("""
      import dataclasses
      @dataclasses.dataclass
      class C:
        _: dataclasses.KW_ONLY
        x: int
      def f(**kwargs):
        return C(**kwargs)
    """)

  def test_star_import(self):
    with self.DepTree([("foo.pyi", """
      import dataclasses
    """)]):
      ty = self.Infer("""
        import dataclasses
        from foo import *
        @dataclasses.dataclass
        class X:
          b: int
          a: str = ...
      """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      @dataclasses.dataclass
      class X:
        b: int
        a: str = ...
        def __init__(self, b: int, a: str = ...) -> None: ...
    """)

  def test_replace_wrong_keyword_args(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass
      class Test:
        x: int
      x = Test(1)
      dataclasses.replace(x, y=1, z=2)  # wrong-keyword-args
    """)

  def test_replace_not_a_dataclass(self):
    self.CheckWithErrors("""
      import dataclasses
      class Test:
        pass
      dataclasses.replace(Test(), y=1, z=2)  # wrong-arg-types
    """)

  def test_replace_late_annotation(self):
    # Regression test: LateAnnotations (like `z: Z`) should behave
    # like their underlying types once resolved. The dataclass overlay
    # relies on this behavior.
    self.Check("""
      from __future__ import annotations
      import dataclasses
      @dataclasses.dataclass
      class A:
        z: Z
        def do(self):
          return dataclasses.replace(self.z, name="A")
      @dataclasses.dataclass
      class Z:
        name: str
    """)

  def test_replace_as_method_with_kwargs(self):
    # This is a weird case where replace is added as a method, then called
    # with kwargs. This makes pytype unable to see that `self` is the object
    # being modified, and also caused a crash when the dataclass overlay tries
    # to unpack the object being modified from the args.
    self.Check("""
      import dataclasses
      @dataclasses.dataclass
      class WithKwargs:
        replace = dataclasses.replace
        def do(self, **kwargs):
            return self.replace(**kwargs)
    """)

  def test_replace_subclass(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass
      class Base:
        name: str
      @dataclasses.dataclass
      class Sub(Base):
        index: int
      a = Sub(name="a", index=0)
      dataclasses.replace(a, name="b", index=2)
      dataclasses.replace(a, name="c", idx=3)  # wrong-keyword-args
    """)


class TestPyiDataclass(test_base.BaseTest):
  """Tests for @dataclasses in pyi files."""

  def test_basic(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: int
          y: str
      """)
      self.Check("""
        import foo
        x = foo.A(10, 'hello')
      """, pythonpath=[d.path])

  def test_protocol(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: int
          y: str
      """)
      self.Check("""
        import foo
        import dataclasses
        x = foo.A(10, 'hello')
        y = dataclasses.fields(x)
      """, pythonpath=[d.path])

  def test_type_mismatch(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: int
          y: str
      """)
      self.CheckWithErrors("""
        import foo
        x = foo.A(10, 20)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_subclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: bool
          y: int
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Foo(foo.A):
          z: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Dict, Union
        @dataclasses.dataclass
        class Foo(foo.A):
          z: str = ...
          def __init__(self, x: bool, y: int, z: str = ...) -> None: ...
      """)

  def test_subclass_from_same_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: bool
          y: int

        @dataclass
        class B(A):
          z: str
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Foo(foo.B):
          a: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Dict, Union
        @dataclasses.dataclass
        class Foo(foo.B):
          a: str = ...
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_subclass_from_different_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file("bar.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: bool
          y: int
      """)
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        import bar
        @dataclass
        class B(bar.A):
          z: str
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Foo(foo.B):
          a: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Dict, Union
        @dataclasses.dataclass
        class Foo(foo.B):
          a: str = ...
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_default_params(self):
    with test_utils.Tempdir() as d:
      d.create_file("bar.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: bool
          y: int = ...
      """)
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        import bar
        @dataclass
        class B(bar.A):
          z: str = ...
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Foo(foo.B):
          a: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Dict, Union
        @dataclasses.dataclass
        class Foo(foo.B):
          a: str = ...
          def __init__(self, x: bool, y: int = ..., z: str = ..., a: str = ...) -> None: ...
      """)

  def test_subclass_classvar(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import ClassVar
        from dataclasses import dataclass
        @dataclass
        class A:
          x: ClassVar[bool]
          y: int
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Foo(foo.A):
          z: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Dict, Union
        @dataclasses.dataclass
        class Foo(foo.A):
          z: str = ...
          def __init__(self, y: int, z: str = ...) -> None: ...
      """)

  def test_properties_from_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from dataclasses import dataclass
        @dataclass
        class A:
          x: bool
          y: int
          @property
          def z(self) -> int: ...
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Foo(foo.A):
          a: str = "hello"
          @property
          def b(self) -> int:
            return 42
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Annotated, Dict, Union
        @dataclasses.dataclass
        class Foo(foo.A):
          a: str = ...
          b: Annotated[int, 'property']
          def __init__(self, x: bool, y: int, a: str = ...) -> None: ...
      """)

  def test_recursion(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import dataclasses
        from typing import Callable, Optional, List
        @dataclasses.dataclass
        class A:
          x: Optional[A]
          y: str
          z: List[A]
      """)
      ty = self.Infer("""
        import foo
        x = foo.A(None, 'hello', [])
        y = foo.A(x, "world", [x])
        a = y.x
        b = y.y
        c = y.z
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Any, Optional, List
        x: foo.A
        y: foo.A
        a: Optional[foo.A]
        b: str
        c: List[foo.A]
      """)

  def test_recursion_with_subclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import dataclasses
        from typing import Callable, Optional, List
        @dataclasses.dataclass
        class A:
          x: Optional[A]
          y: str
          z: List[A]
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class B(foo.A):
          w: int
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Any, Dict, List, Union
        @dataclasses.dataclass
        class B(foo.A):
          w: int
          def __init__(self, x, y: str, z: list, w: int) -> None: ...
      """)

  def test_multi_step_recursion(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import dataclasses
        @dataclasses.dataclass
        class A:
          x: B

        class B(A):
          y: int
      """)
      ty = self.Infer("""
        import dataclasses
        import foo
        @dataclasses.dataclass
        class C(foo.A):
          w: int
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Any, Dict, List, Union
        @dataclasses.dataclass
        class C(foo.A):
          w: int
          def __init__(self, x: foo.B, w: int) -> None: ...
      """)

  def test_parameterized_generic(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      import dataclasses
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: str
        y: T
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Generic, TypeVar, Union
      import dataclasses
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: str
        y: T
        def __init__(self, x: str, y: T) -> None:
            self = Foo[T]
    """)

  def test_parameterized_subclass(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar
      import dataclasses
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: str
        y: T
      @dataclasses.dataclass
      class Bar(Foo[int]):
        z: float
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Generic, TypeVar, Union
      import dataclasses
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: str
        y: T
        def __init__(self, x: str, y: T) -> None:
            self = Foo[T]
      @dataclasses.dataclass
      class Bar(Foo[int]):
        z: float
        def __init__(self, x: str, y: int, z: float) -> None: ...
    """)

  def test_parameterized_subclass_error_count(self):
    self.CheckWithErrors("""
      from typing import Generic, TypeVar
      import dataclasses
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: str
        y: T
      @dataclasses.dataclass
      class Bar(Foo[int]):
        z: float
      bar = Bar('test', 10, .4, .4)  # wrong-arg-count
    """)

  def test_parameterized_subclass_error_type(self):
    self.CheckWithErrors("""
      from typing import Generic, TypeVar
      import dataclasses
      T = TypeVar('T')
      @dataclasses.dataclass
      class Foo(Generic[T]):
        x: str
        y: T
      @dataclasses.dataclass
      class Bar(Foo[int]):
        z: float
      bar = Bar('test', .4, .4)  # wrong-arg-types
    """)

  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_kwonly_constructor(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass(kw_only=True)
      class A():
        a1: int
        a2: int = dataclasses.field(default_factory=lambda: 0)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict

      @dataclasses.dataclass
      class A:
          a1: int
          a2: int = ...
          def __init__(self, *, a1: int, a2: int = ...) -> None: ...
    """)

  @test_base.skip("Doesn't work due to b/268530497")
  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_inherited_kwonly_constructor(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass(kw_only=True)
      class A():
        a1: int
        a2: int = dataclasses.field(default_factory=lambda: 0)

      @dataclasses.dataclass
      class B(A):
        b1: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict

      @dataclasses.dataclass
      class A:
          a1: int
          a2: int
          def __init__(self, *, a1: int, a2: int = ...) -> None: ...

      @dataclasses.dataclass
      class B(A):
          b1: int
          def __init__(self, b1: int, *, a1: int, a2: int = ...) -> None: ...
    """)

  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_kwonly(self):
    ty = self.Infer("""
      import dataclasses

      @dataclasses.dataclass
      class A():
        a1: int
        a2: int = dataclasses.field(default_factory=lambda: 0, kw_only=True)

      @dataclasses.dataclass
      class B(A):
        b1: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Dict

      @dataclasses.dataclass
      class A:
          a1: int
          a2: int = ...
          def __init__(self, a1: int, *, a2: int = ...) -> None: ...

      @dataclasses.dataclass
      class B(A):
          b1: int
          def __init__(self, a1: int, b1: int, *, a2: int = ...) -> None: ...
    """)

  @test_utils.skipBeforePy((3, 10), "kw_only parameter is new in 3.10")
  def test_sticky_kwonly(self):
    with self.DepTree([("foo.pyi", """
      import dataclasses

      @dataclasses.dataclass
      class A():
        a1: int
        _: dataclasses.KW_ONLY
        a2: int = ...
    """)]):
      self.Check("""
        import dataclasses
        import foo

        @dataclasses.dataclass
        class B(foo.A):
          b1: str

        b = B(1, '1')
      """)

  def test_replace_wrong_keyword_args(self):
    with self.DepTree([("foo.pyi", """
        import dataclasses
        @dataclasses.dataclass
        class Test:
            x: int
            def __init__(self, x: int) -> None: ...
    """)]):
      self.CheckWithErrors("""
        import dataclasses
        import foo
        x = foo.Test(1)
        dataclasses.replace(x, y=1, z=2)  # wrong-keyword-args
      """)

  def test_no_name_mangling(self):
    # attrs turns _x into x in `__init__`. We account for this in
    # PytdClass._init_attr_metadata_from_pytd by replacing "x" with "_x" when
    # reconstructing the class's attr metadata.
    # However, dataclasses does *not* do this name mangling.
    with self.DepTree([("foo.pyi", """
      import dataclasses
      from typing import Annotated
      @dataclasses.dataclass
      class A:
          x: int
          _x: Annotated[int, 'property']
          def __init__(self, x: int) -> None: ...
    """)]):
      self.Check("""
        import dataclasses
        import foo
        dataclasses.replace(foo.A(1), x=2)
      """)


@test_utils.skipBeforePy((3, 10), "Pattern matching is new in 3.10.")
class TestPatternMatch(test_base.BaseTest):
  """Tests for pattern matching on dataclasses."""

  def test_match(self):
    self.Check("""
      import dataclasses
      @dataclasses.dataclass
      class Point:
        x: float
        y: float
      def f(x, y):
        p = Point(x, y)
        match p:
          case Point(x, y):
            print(f"({x}, {y})")
          case _:
            print("not matched")
    """)

  def test_match_with_pyi_dataclass(self):
    with self.DepTree([("foo.pyi", """
      import dataclasses
      @dataclasses.dataclass
      class Point:
        x: float
        y: float
    """)]):
      self.Check("""
        import foo
        def f(x, y):
          p = foo.Point(x, y)
          match p:
            case foo.Point(x, y):
              print(f"({x}, {y})")
            case _:
              print("not matched")
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      import dataclasses
      @dataclasses.dataclass
      class Point:
        x: float
        y: float
    """)]):
      self.Check("""
        import foo
        def f(x, y):
          p = foo.Point(x, y)
          match p:
            case foo.Point(x, y):
              print(f"({x}, {y})")
            case _:
              print("not matched")
      """)


if __name__ == "__main__":
  test_base.main()
