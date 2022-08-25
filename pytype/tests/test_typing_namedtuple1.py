"""Tests for the typing.NamedTuple overlay."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class NamedTupleTest(test_base.BaseTest):
  """Tests for the typing.NamedTuple overlay."""

  def test_basic_calls(self):
    self.CheckWithErrors("""
      import typing
      Basic = typing.NamedTuple("Basic", [('a', str)])
      ex = Basic("hello world")
      ea = ex.a
      ey = Basic()  # missing-parameter
      ez = Basic("a", "b")  # wrong-arg-count
      """)

  def test_optional_field_type(self):
    self.CheckWithErrors("""
      import typing
      X = typing.NamedTuple("X", [('a', str), ('b', typing.Optional[int])])
      xa = X('hello', None)
      xb = X('world', 2)
      xc = X('nope', '2')  # wrong-arg-types
      xd = X()  # missing-parameter
      xe = X(1, "nope")  # wrong-arg-types
      """)

  def test_class_field_type(self):
    self.CheckWithErrors("""
      import typing
      class Foo:
        pass
      Y = typing.NamedTuple("Y", [('a', str), ('b', Foo)])
      ya = Y('a', Foo())
      yb = Y('a', 1)  # wrong-arg-types
      yc = Y(Foo())  # missing-parameter
      yd = Y(1)  # missing-parameter
      """)

  def test_late_annotation(self):
    errors = self.CheckWithErrors("""
      import typing
      class Foo:
        pass
      X = typing.NamedTuple("X", [('a', 'Foo')]) # should be fine
      Y = typing.NamedTuple("Y", [('a', 'Bar')]) # should fail  # name-error[e]
      """)
    self.assertErrorRegexes(errors, {"e": r"Bar"})

  def test_nested_containers(self):
    self.CheckWithErrors("""
      import typing
      Z = typing.NamedTuple("Z", [('a', typing.List[typing.Optional[int]])])
      za = Z([1])
      zb = Z([None, 2])
      zc = Z(1)  # wrong-arg-types

      import typing
      A = typing.NamedTuple("A", [('a', typing.Dict[int, str]), ('b', typing.Tuple[int, int])])
      aa = A({1: '1'}, (1, 2))
      ab = A({}, (1, 2))
      ac = A(1, 2)  # wrong-arg-types
      """)

  def test_pytd_field(self):
    self.CheckWithErrors("""
      import typing
      import datetime
      B = typing.NamedTuple("B", [('a', datetime.date)])
      ba = B(datetime.date(1,2,3))
      bb = B()  # missing-parameter
      bc = B(1)  # wrong-arg-types
      """)

  def test_bad_calls(self):
    self.InferWithErrors("""
        import typing
        typing.NamedTuple("_", ["abc", "def", "ghi"])  # wrong-arg-types
        # "def" is a keyword, so the call on the next line fails.
        typing.NamedTuple("_", [("abc", int), ("def", int), ("ghi", int)])  # invalid-namedtuple-arg
        typing.NamedTuple("1", [("a", int)])  # invalid-namedtuple-arg
        typing.NamedTuple("_", [[int, "a"]])  # wrong-arg-types
        """)

  def test_empty_args(self):
    self.Check(
        """
        import typing
        X = typing.NamedTuple("X", [])
        """)

  def test_tuple_fields(self):
    errors = self.CheckWithErrors("""
      from typing import NamedTuple
      X = NamedTuple("X", (("a", str),))
      X(a="")
      X(a=42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_list_field(self):
    errors = self.CheckWithErrors("""
      from typing import NamedTuple
      X = NamedTuple("X", [["a", str]])
      X(a="")
      X(a=42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_str_fields_error(self):
    errors = self.CheckWithErrors("""
      from typing import NamedTuple
      X = NamedTuple("X", "a b")  # wrong-arg-types[e1]
      Y = NamedTuple("Y", ["ab"])  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Tuple.*str",
        "e2": r"Tuple.*str"
    })

  def test_typevar(self):
    self.Check("""
      from typing import Callable, NamedTuple, TypeVar
      T = TypeVar('T')
      X = NamedTuple("X", [("f", Callable[[T], T])])
      assert_type(X(f=__any_object__).f(""), str)
    """)

  def test_bad_typevar(self):
    self.CheckWithErrors("""
      from typing import NamedTuple, TypeVar
      T = TypeVar('T')
      X = NamedTuple("X", [("a", T)])  # invalid-annotation
    """)

  def test_reingest(self):
    foo_ty = self.Infer("""
      from typing import Callable, NamedTuple, TypeVar
      T = TypeVar('T')
      X = NamedTuple("X", [("a", Callable[[T], T])])
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.Check("""
        import foo
        assert_type(foo.X(a=__any_object__).a(4.2), float)
      """, pythonpath=[d.path])

  def test_fields(self):
    self.Check("""
      from typing import NamedTuple
      X = NamedTuple("X", [('a', str), ('b', int)])

      v = X("answer", 42)
      a = v.a  # type: str
      b = v.b  # type: int
      """)

  def test_field_wrong_type(self):
    self.CheckWithErrors("""
        from typing import NamedTuple
        X = NamedTuple("X", [('a', str), ('b', int)])

        v = X("answer", 42)
        a_int = v.a  # type: int  # annotation-type-mismatch
      """)

  def test_unpacking(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        X = NamedTuple("X", [('a', str), ('b', int)])
      """)
      ty = self.Infer("""
        import foo
        v = None  # type: foo.X
        a, b = v
      """, deep=False, pythonpath=[d.path])

      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        v = ...  # type: foo.namedtuple_X_0
        a = ...  # type: str
        b = ...  # type: int
      """)

  def test_bad_unpacking(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        X = NamedTuple("X", [('a', str), ('b', int)])
      """)
      self.CheckWithErrors("""
        import foo
        v = None  # type: foo.X
        _, _, too_many = v  # bad-unpacking
        too_few, = v  # bad-unpacking
        a: float
        b: str
        a, b = v  # annotation-type-mismatch # annotation-type-mismatch
      """, deep=False, pythonpath=[d.path])

  def test_is_tuple_type_and_superclasses(self):
    """Test that a NamedTuple (function syntax) behaves like a tuple."""
    self.Check("""
      from typing import MutableSequence, NamedTuple, Sequence, Tuple, Union
      X = NamedTuple("X", [("a", int), ("b", str)])

      a = X(1, "2")
      a_tuple = a  # type: tuple
      a_typing_tuple = a  # type: Tuple[int, str]
      a_typing_tuple_elipses = a  # type: Tuple[Union[int, str], ...]
      a_sequence = a  # type: Sequence[Union[int, str]]
      a_iter = iter(a)  # type: tupleiterator[Union[int, str]]

      a_first = a[0]  # type: int
      a_second = a[1]  # type: str
      a_first_next = next(iter(a))  # We don't know the type through the iter() function
    """)

  def test_is_not_incorrect_types(self):
    self.CheckWithErrors("""
      from typing import MutableSequence, NamedTuple, Sequence, Tuple, Union
      X = NamedTuple("X", [("a", int), ("b", str)])

      x = X(1, "2")

      x_wrong_tuple_types = x  # type: Tuple[str, str]  # annotation-type-mismatch
      x_not_a_list = x  # type: list  # annotation-type-mismatch
      x_not_a_mutable_seq = x  # type: MutableSequence[Union[int, str]]  # annotation-type-mismatch
      x_first_wrong_element_type = x[0]  # type: str  # annotation-type-mismatch
    """)

  def test_meets_protocol(self):
    self.Check("""
      from typing import NamedTuple, Protocol
      X = NamedTuple("X", [("a", int), ("b", str)])

      class IntAndStrHolderVars(Protocol):
        a: int
        b: str

      class IntAndStrHolderProperty(Protocol):
        @property
        def a(self) -> int:
          ...

        @property
        def b(self) -> str:
          ...

      a = X(1, "2")
      a_vars_protocol: IntAndStrHolderVars = a
      a_property_protocol: IntAndStrHolderProperty = a
    """)

  def test_does_not_meet_mismatching_protocol(self):
    self.CheckWithErrors("""
      from typing import NamedTuple, Protocol
      X = NamedTuple("X", [("a", int), ("b", str)])

      class DualStrHolder(Protocol):
        a: str
        b: str

      class IntAndStrHolderVars_Alt(Protocol):
        the_number: int
        the_string: str

      class IntStrIntHolder(Protocol):
        a: int
        b: str
        c: int

      a = X(1, "2")
      a_wrong_types: DualStrHolder = a  # annotation-type-mismatch
      a_wrong_names: IntAndStrHolderVars_Alt = a  # annotation-type-mismatch
      a_too_many: IntStrIntHolder = a  # annotation-type-mismatch
    """)

  def test_generated_members(self):
    ty = self.Infer("""
      from typing import NamedTuple
      X = NamedTuple("X", [('a', int), ('b', str)])""")
    self.assertTypesMatchPytd(ty, """
      from typing import NamedTuple
      class X(NamedTuple):
          a: int
          b: str
      """)


if __name__ == "__main__":
  test_base.main()
