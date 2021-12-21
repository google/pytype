"""Tests for typing.TypedDict."""

from pytype.tests import test_base


class TypedDictTest(test_base.BaseTest):
  """Tests for typing.TypedDict."""

  def setUp(self):
    super().setUp()
    self.options.tweak(enable_typed_dicts=True)

  def test_init(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a = A(x=1, y='2')
      b = A(x=1, y=2)  # wrong-arg-types[e1]
      c = A(x=1)  # missing-parameter[e2]
      d = A(y='1')  # missing-parameter
      e = A(1, '2')  # missing-parameter
    """)
    self.assertErrorSequences(err, {
        "e1": ["Expected", "(*, x, y: str)", "Actual", "(x, y: int)"],
        "e2": ["Expected", "(*, x, y)", "Actual", "(x)"]
    })

  def test_key_error(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a = A(x=1, y="2")
      a["z"] = 10  # typed-dict-error[e1]
      a[10] = 10  # typed-dict-error[e2]
      b = a["z"]  # typed-dict-error
      del a["z"]  # typed-dict-error
    """)
    self.assertErrorSequences(err, {
        "e1": ["TypedDict A", "key z"],
        "e2": ["TypedDict A", "requires all keys", "strings"],
    })

  def test_value_error(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a = A(x=1, y="2")
      a["x"] = "10"  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Type annotation", "key x", "TypedDict A",
        "Annotation: int", "Assignment: str"
    ]})

  def test_union_type(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      from typing import Union
      class A(TypedDict):
        x: Union[int, str]
        y: Union[int, str]
      a = A(x=1, y="2")
      a["x"] = "10"
      a["y"] = []  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Type annotation", "key y", "TypedDict A",
        "Annotation: Union[int, str]", "Assignment: List[nothing]"
    ]})

  def test_bad_base_class(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo: pass
      class Bar(TypedDict, Foo):  # base-class-error[e]
        x: int
    """)
    self.assertErrorSequences(err, {"e": [
        "Invalid base class", "Foo", "TypedDict Bar", "cannot inherit"
    ]})

  def test_inheritance(self):
    self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: int
      class Bar(TypedDict):
        y: str
      class Baz(Foo, Bar):
        z: bool
      a = Baz(x=1, y='2', z=False)
      a['x'] = 1
      a['y'] = 2  # annotation-type-mismatch
      a['z'] = True
      a['w'] = True  # typed-dict-error
    """)

  def test_inheritance_clash(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: int
      class Bar(TypedDict):
        y: str
      class Baz(Foo, Bar):  # base-class-error[e]
        x: bool
    """)
    self.assertErrorSequences(err, {"e": [
        "Duplicate", "key x", "Foo", "Baz"
    ]})

  def test_annotation(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a: A = {'x': '10', 'z': 20}  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Annotation: A(TypedDict)",
        "extra keys", "z",
        "type errors", "{'x': ...}", "expected int", "got str"
    ]})

  def test_return_type(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      def f() -> A:
        return {'x': '10', 'z': 20}  # bad-return-type[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Expected: A(TypedDict)",
        "extra keys", "z",
        "type errors", "{'x': ...}", "expected int", "got str"
    ]})

  def test_functional_constructor(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      A = TypedDict("A", {'x': int, 'y': str})  # not-supported-yet[e]
    """)
    self.assertErrorSequences(err, {"e": ["Use the class definition form"]})


if __name__ == "__main__":
  test_base.main()
