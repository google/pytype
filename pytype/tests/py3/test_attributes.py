"""Test instance and class attributes."""

from pytype.tests import test_base


class TestStrictNone(test_base.BaseTest):
  """Tests for strict attribute checking on None."""

  def test_explicit_none(self):
    errors = self.CheckWithErrors("""
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_closure(self):
    self.Check("""
      from typing import Optional
      d = ...  # type: Optional[dict]
      if d:
        formatter = lambda x: d.get(x, '')
      else:
        formatter = lambda x: ''
      formatter('key')
    """)

  def test_overwrite_global(self):
    errors = self.CheckWithErrors("""
      from typing import Optional
      d = ...  # type: Optional[dict]
      if d:
        formatter = lambda x: d.get(x, '')  # attribute-error[e]
      else:
        formatter = lambda x: ''
      d = None
      formatter('key')  # line 8
    """)
    self.assertErrorRegexes(errors, {"e": r"get.*None.*traceback.*line 8"})


class TestAttributes(test_base.BaseTest):
  """Tests for attributes."""

  def test_attr_on_optional(self):
    errors = self.CheckWithErrors("""
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_any_annotation(self):
    self.Check("""
      from typing import Any
      def f(x: Any):
        if __random__:
          x = 42
        x.upper()
    """)

  def test_non_init_annotation(self):
    ty, errors = self.InferWithErrors("""
      from typing import List
      class Foo:
        def __init__(self):
          # This annotation should be used when inferring the attribute type.
          self.x = []  # type: List[int]
        def f1(self):
          # This annotation should be applied to the attribute value but ignored
          # when inferring the attribute type.
          self.x = []  # type: List[str]
          return self.x
        def f2(self):
          # This assignment should be checked against the __init__ annotation.
          self.x = ['']  # annotation-type-mismatch[e]
        def f3(self):
          # The return type should reflect all assignments, even ones that
          # violate the __init__ annotation.
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      class Foo:
        x: List[int]
        def __init__(self) -> None: ...
        def f1(self) -> List[str]: ...
        def f2(self) -> None: ...
        def f3(self) -> List[Union[int, str]]: ...
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Annotation: List\[int\].*Assignment: List\[str\]"})


class TestAttributesPython3FeatureTest(test_base.BaseTest):
  """Tests for attributes over target code using Python 3 features."""

  def test_empty_type_parameter_instance(self):
    self.Check("""
      args = {}
      for x, y in sorted(args.items()):
        x.values
    """)

  def test_type_parameter_instance_multiple_bindings(self):
    _, errors = self.InferWithErrors("""
      class A:
        values = 42
      args = {A() if __random__ else True: ""}
      for x, y in sorted(args.items()):
        x.values  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"'values' on bool"})

  def test_type_parameter_instance_set_attr(self):
    ty = self.Infer("""
      class Foo:
        pass
      class Bar:
        def bar(self):
          d = {42: Foo()}
          for _, foo in sorted(d.items()):
            foo.x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x = ...  # type: int
      class Bar:
        def bar(self) -> None: ...
    """)

  def test_type_parameter_instance(self):
    ty = self.Infer("""
      class A:
        values = 42
      args = {A(): ""}
      for x, y in sorted(args.items()):
        z = x.values
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      class A:
        values = ...  # type: int
      args = ...  # type: Dict[A, str]
      x = ...  # type: A
      y = ...  # type: str
      z = ...  # type: int
    """)

  def test_filter_subclass_attribute(self):
    self.Check("""
      from typing import List

      class NamedObject:
        name = ...  # type: str
      class UnnamedObject:
        pass
      class ObjectHolder:
        named = ...  # type: NamedObject
        unnamed = ...  # type: UnnamedObject

      class Base:
        def __init__(self):
          self.objects = []  # type: List

      class Foo(Base):
        def __init__(self, holder: ObjectHolder):
          Base.__init__(self)
          self.objects.append(holder.named)
        def get_name(self):
          return self.objects[0].name

      class Bar(Base):
        def __init__(self, holder: ObjectHolder):
          Base.__init__(self)
          self.objects = []
          self.objects.append(holder.unnamed)
    """)

  @test_base.skip("Needs vm._get_iter() to iterate over individual bindings.")
  def test_metaclass_iter(self):
    self.Check("""
      class Meta(type):
        def __iter__(cls):
          return iter([])
      class Foo(metaclass=Meta):
        def __iter__(self):
          return iter([])
      for _ in Foo:
        pass
    """)

  @test_base.skip("Needs better handling of __getitem__ in vm._get_iter().")
  def test_metaclass_getitem(self):
    self.Check("""
      class Meta(type):
        def __getitem__(cls, x):
          return 0
      class Foo(metaclass=Meta):
        def __getitem__(self, x):
          return 0
      for _ in Foo:
        pass
    """)

  def test_check_variable_annotation(self):
    errors = self.CheckWithErrors("""
      class Foo:
        x: int
        def foo(self):
          self.x = 'hello, world'  # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_pep526_annotation(self):
    ty, _ = self.InferWithErrors("""
      class Foo:
        def __init__(self):
          self.x: int = None
        def do_something(self, x: str):
          self.x = x  # annotation-type-mismatch
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x: int
        def __init__(self) -> None: ...
        def do_something(self, x: str) -> None: ...
    """)

  def test_inherit_declared_attribute(self):
    ty = self.Infer("""
      class Foo:
        x: int
      class Bar(Foo):
        def f(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x: int
      class Bar(Foo):
        def f(self) -> int: ...
    """)


if __name__ == "__main__":
  test_base.main()
