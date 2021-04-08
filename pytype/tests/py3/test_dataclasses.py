# Lint as: python3
"""Tests for the dataclasses overlay."""

from pytype import file_utils
from pytype.tests import test_base


class TestDataclass(test_base.TargetPython3FeatureTest):
  """Tests for @dataclass."""

  def setUp(self):
    super().setUp()
    # Checking field defaults against their types should work even when general
    # variable checking is disabled.
    self.options.tweak(check_variable_types=False)

  def test_basic(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: bool
        y: int
        z: str
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        z: str
        def __init__(self, x: bool, y: int, z: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: 'Foo'
        y: str
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
    """)

  def test_redefine(self):
    """The first annotation should determine the order."""
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: int
        y: int
        x: str = 'hello'
        y = 10
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        y: int
        x: str
        def __init__(self, x: str = ..., y: int = ...) -> None: ...
    """)

  def test_redefine_as_method(self):
    ty, errors = self.InferWithErrors("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: str = 'hello'
        y: int = 10
        def x(self):  # annotation-type-mismatch[e]
          return 10
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: str
        y: int
        def __init__(self, x: str = ..., y: int = ...) -> None: ...
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Annotation: str.*Assignment: Callable"})

  def test_no_init(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass(init=False)
      class Foo(object):
        x: bool
        y: int
        z: str
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        z: str
    """)

  def test_explicit_init(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass(init=True)
      class Foo(object):
        x: bool
        y: int
        def __init__(self, a: bool):
          self.x = a
          self.y = 0
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        def __init__(self, a: bool) -> None: ...
    """)

  def test_field(self):
    ty = self.Infer("""
      from typing import List
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
        x: bool = dataclasses.field(default=True)
        y: List[int] = dataclasses.field(default_factory=list)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      dataclasses: module
      class Foo(object):
        x: bool
        y: List[int]
        def __init__(self, x: bool = ..., y: List[int] = ...) -> None: ...
    """)

  def test_type_mismatch(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
        x: bool = 10  # annotation-type-mismatch
    """)

  def test_type_mismatch_on_none(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
        x: int = None  # annotation-type-mismatch
    """)

  def test_field_type_mismatch(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
        x: bool = dataclasses.field(default=10)  # annotation-type-mismatch
    """)

  def test_factory_type_mismatch(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
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
      class Foo(object):
        x: bool = dataclasses.field(default=True)
        y: int = dataclasses.field(init=False)
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        def __init__(self, x: bool = ...) -> None: ...
    """)

  def test_field_init_no_default(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
        x: bool = dataclasses.field()
        y: int
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        def __init__(self, x: bool, y: int) -> None: ...
    """)

  def test_bad_default_param_order(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):  # invalid-function-definition
        x: int = 10
        y: str
    """)

  def test_any(self):
    self.Check("""
      import dataclasses
      from typing import Any

      @dataclasses.dataclass
      class Foo(object):
        foo: Any = None
    """)

  def test_instantiate_field_type(self):
    self.Check("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        def foo(self):
          for field in dataclasses.fields(self):
            field.type()
    """)

  def test_subclass(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass()
      class Foo(object):
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
      dataclasses: module
      class Foo(object):
        w: float
        x: bool
        y: int
        def __init__(self, w: float, x: bool = ...) -> None: ...
      class Bar(Foo):
        def get_w(self) -> float: ...
        def get_x(self) -> bool : ...
        def get_y(self) -> int: ...
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
      from typing import Optional, Type, Union

      Node: Type[Union[IntLeaf, StrLeaf, Tree]]
      dataclasses: module

      class IntLeaf:
          value: int
          def __init__(self, value: int) -> None: ...

      class StrLeaf:
          label: str
          def __init__(self, label: str) -> None: ...

      class Tree:
          children: Union[IntLeaf, StrLeaf, Tree]
          def __init__(self, children: Union[IntLeaf, StrLeaf, Tree]) -> None: ...
          def get_children(self) -> Union[IntLeaf, StrLeaf, Tree]: ...
          def get_leaf(self) -> int: ...

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
      dataclasses: module
      class A:
        y: int
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
      dataclasses: module
      class A:
        x: str
        y: int
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
      dataclasses: module
      class A:
        x: str
        y: int
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
      dataclasses: module
      class A:
        y: int
        def __init__(self, x: str, y: int = ...) -> None: ...

      class B(A):
        z: int
        def __init__(self, x: str, y: int = ..., z: int = ...) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      from typing import ClassVar
      import dataclasses

      @dataclasses.dataclass
      class Foo(object):
        x: ClassVar[int] = 10
        y: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: int
        y: str
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
      from typing import Type
      dataclasses: module
      class Foo:
        Inner: Type[Inner1]
      class Bar:
        Inner: Type[Inner2]
      class Inner1:
        a: int
        def __init__(self, a: int) -> None: ...
      class Inner2:
        b: str
        def __init__(self, b: str) -> None: ...
    """)

  def test_check_field_against_container(self):
    self.options.tweak(check_variable_types=True)
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
      from typing import Any
      dataclasses: module
      def field_wrapper(**kwargs) -> Any: ...
      class Foo:
        x: int
        y: int
        def __init__(self, x: int = ..., y: int = ...) -> None: ...
    """)

  def test_property(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: bool
        y: int
        @property
        def z(self) -> str:
          return "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Annotated
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        z: Annotated[str, 'property']
        def __init__(self, x: bool, y: int) -> None: ...
    """)


class TestPyiDataclass(test_base.TargetPython3FeatureTest):
  """Tests for @dataclasses in pyi files."""

  def test_basic(self):
    with file_utils.Tempdir() as d:
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

  def test_type_mismatch(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
        dataclasses: module
        foo: module
        class Foo(foo.A):
          z: str
          def __init__(self, x: bool, y: int, z: str = ...) -> None: ...
      """)

  def test_subclass_from_same_pyi(self):
    with file_utils.Tempdir() as d:
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
        dataclasses: module
        foo: module
        class Foo(foo.B):
          a: str
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_subclass_from_different_pyi(self):
    with file_utils.Tempdir() as d:
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
        dataclasses: module
        foo: module
        class Foo(foo.B):
          a: str
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_properties_from_pyi(self):
    with file_utils.Tempdir() as d:
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
        from typing import Annotated
        dataclasses: module
        foo: module
        class Foo(foo.A):
          a: str
          b: Annotated[int, 'property']
          def __init__(self, x: bool, y: int, a: str = ...) -> None: ...
      """)


test_base.main(globals(), __name__ == "__main__")
