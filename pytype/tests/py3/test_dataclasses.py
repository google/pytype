# Lint as: python3
"""Tests for the dataclasses overlay."""

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


test_base.main(globals(), __name__ == "__main__")
