"""Tests for the typing.NamedTuple overlay."""

from pytype.tests import test_base


class NamedTupleTest(test_base.TargetIndependentTest):
  """Tests for the typing.NamedTuple overlay."""

  def test_basic_calls(self):
    errors = self.CheckWithErrors("""\
      import typing
      Basic = typing.NamedTuple("Basic", [('a', str)])
      ex = Basic("hello world")
      ea = ex.a
      ey = Basic()  # Should fail
      ez = Basic("a", "b")  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "missing-parameter"),
        (6, "wrong-arg-count")])

  def test_optional_field_type(self):
    errors = self.CheckWithErrors("""\
      import typing
      X = typing.NamedTuple("X", [('a', str), ('b', typing.Optional[int])])
      xa = X('hello', None)
      xb = X('world', 2)
      xc = X('nope', '2')  # Should fail
      xd = X()  # Should fail
      xe = X(1, "nope")  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types"),
        (6, "missing-parameter"),
        (7, "wrong-arg-types")])

  def test_class_field_type(self):
    errors = self.CheckWithErrors("""\
      import typing
      class Foo(object):
        pass
      Y = typing.NamedTuple("Y", [('a', str), ('b', Foo)])
      ya = Y('a', Foo())
      yb = Y('a', 1)  # Should fail
      yc = Y(Foo())  # Should fail
      yd = Y(1)  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (6, "wrong-arg-types"),
        (7, "missing-parameter"),
        (8, "missing-parameter")])

  def test_late_annotation(self):
    errors = self.CheckWithErrors("""\
      import typing
      class Foo(object):
        pass
      X = typing.NamedTuple("X", [('a', 'Foo')]) # should be fine
      Y = typing.NamedTuple("Y", [('a', 'Bar')]) # should fail
      """)
    self.assertErrorLogIs(errors, [(5, "name-error", "Bar")])

  def test_nested_containers(self):
    errors = self.CheckWithErrors("""\
      import typing
      Z = typing.NamedTuple("Z", [('a', typing.List[typing.Optional[int]])])
      za = Z([1])
      zb = Z([None, 2])
      zc = Z(1)  # Should fail

      import typing
      A = typing.NamedTuple("A", [('a', typing.Dict[int, str]), ('b', typing.Tuple[int, int])])
      aa = A({1: '1'}, (1, 2))
      ab = A({}, (1, 2))
      ac = A(1, 2)  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types"),
        (11, "wrong-arg-types")])

  def test_pytd_field(self):
    errors = self.CheckWithErrors("""\
      import typing
      import datetime
      B = typing.NamedTuple("B", [('a', datetime.date)])
      ba = B(datetime.date(1,2,3))
      bb = B()  # Should fail
      bc = B(1)  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "missing-parameter"),
        (6, "wrong-arg-types")])

  def test_bad_calls(self):
    _, errorlog = self.InferWithErrors("""\
        import typing
        typing.NamedTuple("_", ["abc", "def", "ghi"])
        # "def" is a keyword, so the call on the next line fails.
        typing.NamedTuple("_", [("abc", int), ("def", int), ("ghi", int)])
        typing.NamedTuple("1", [("a", int)])
        typing.NamedTuple("_", [[int, "a"]])
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "wrong-arg-types"),
                           (4, "invalid-namedtuple-arg"),
                           (5, "invalid-namedtuple-arg"),
                           (6, "wrong-arg-types")])

  def test_empty_args(self):
    self.Check(
        """
        import typing
        X = typing.NamedTuple("X", [])
        """)

  def test_tuple_fields(self):
    errors = self.CheckWithErrors("""\
      from typing import NamedTuple
      X = NamedTuple("X", (("a", str),))
      X(a="")
      X(a=42)
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types", r"str.*int")])

  def test_list_field(self):
    errors = self.CheckWithErrors("""\
      from typing import NamedTuple
      X = NamedTuple("X", [["a", str]])
      X(a="")
      X(a=42)
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types", r"str.*int")])

  def test_str_fields_error(self):
    errors = self.CheckWithErrors("""\
      from typing import NamedTuple
      X = NamedTuple("X", "a b")
      Y = NamedTuple("Y", ["ab"])
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"List.*str"),
                                   (3, "wrong-arg-types", r"Tuple.*str")])


test_base.main(globals(), __name__ == "__main__")
