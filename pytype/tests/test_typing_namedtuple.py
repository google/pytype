"""Tests for the typing.NamedTuple overlay."""

from pytype.tests import test_base


class NamedTupleTest(test_base.TargetIndependentTest):
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
      class Foo(object):
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
      class Foo(object):
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
    self.assertErrorRegexes(errors, {"e1": r"List.*str", "e2": r"Tuple.*str"})


test_base.main(globals(), __name__ == "__main__")
