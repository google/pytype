"""Tests for the collections.namedtuple implementation."""

from pytype.tests import test_base
from pytype.tests import test_utils


class NamedtupleTests(test_base.BaseTest):
  """Tests for collections.namedtuple."""

  def test_basic_namedtuple(self):
    self.Check("""
      import collections

      X = collections.namedtuple("X", ["y", "z"])
      a = X(y=1, z=2)
      assert_type(a, X)
      """, deep=False)

  def test_pytd(self):
    ty = self.Infer("""
      import collections

      X = collections.namedtuple("X", ["y", "z"])
      a = X(y=1, z=2)
      """, deep=False)
    self.assertTypesMatchPytd(ty, """
      import collections
      from typing import Any, NamedTuple

      a: X

      class X(NamedTuple):
          y: Any
          z: Any
    """)

  def test_no_fields(self):
    self.Check("""
        import collections

        F = collections.namedtuple("F", [])
        a = F()
        """, deep=False)

  def test_str_args(self):
    self.Check("""
        import collections

        S = collections.namedtuple("S", "a b c")
        b = S(1, 2, 3)
        c = (b.a, b.b, b.c)
    """, deep=False)

  def test_str_args2(self):
    self.Check("""
        import collections
        collections.namedtuple("_", "a,b,c")(1, 2, 3)
        """)
    self.Check("""
        import collections
        collections.namedtuple("_", "a, b, c")(1, 2, 3)
        """)
    self.Check("""
        import collections
        collections.namedtuple("_", "a ,b")(1, 2)
        """)

  def test_bad_fieldnames(self):
    self.CheckWithErrors("""
        import collections
        collections.namedtuple("_", ["abc", "def", "ghi"])  # invalid-namedtuple-arg
        collections.namedtuple("_", "_")  # invalid-namedtuple-arg
        collections.namedtuple("_", "a, 1")  # invalid-namedtuple-arg
        collections.namedtuple("_", "a, !")  # invalid-namedtuple-arg
        collections.namedtuple("_", "a, b, c, a")  # invalid-namedtuple-arg
        collections.namedtuple("1", "")  # invalid-namedtuple-arg
        """)

  def test_rename(self):
    self.Check("""
        import collections

        S = collections.namedtuple("S", "abc def ghi abc", rename=True)
        a = S(1, 2, 3, 4)
        b = a._3
        """, deep=False)

  def test_bad_initialize(self):
    self.CheckWithErrors("""
        from collections import namedtuple

        X = namedtuple("X", "y z")
        a = X(1)  # missing-parameter
        b = X(y = 2)  # missing-parameter
        c = X(w = 3)  # wrong-keyword-args
        d = X(y = "hello", z = 4j)  # works
        """)

  def test_class_name(self):
    self.CheckWithErrors(
        """
        import collections
        F = collections.namedtuple("S", ['a', 'b', 'c'])
        a = F(1, 2, 3)
        b = S(1, 2, 3)  # name-error
        """)

  def test_constructors(self):
    self.Check("""
        import collections
        X = collections.namedtuple("X", "a b c")
        g = X(1, 2, 3)
        i = X._make((7, 8, 9))
        j = X._make((10, 11, 12), tuple.__new__, len)
        """)

  def test_instance_types(self):
    self.Check(
        """
        import collections
        X = collections.namedtuple("X", "a b c")
        a = X._make((1, 2, 3))
        """)

  def test_fields(self):
    self.Check(
        """
        import collections
        X = collections.namedtuple("X", "a b c")

        a = X(1, "2", 42.0)

        a_f = a.a
        b_f = a.b
        c_f = a.c
        """)

  def test_unpacking(self):
    self.Check(
        """
        import collections
        X = collections.namedtuple("X", "a b c")

        a = X(1, "2", 42.0)

        a_f, b_f, c_f = a
        """)

  def test_bad_unpacking(self):
    self.CheckWithErrors(
        """
        import collections
        X = collections.namedtuple("X", "a b c")

        a = X(1, "2", 42.0)

        _, _, _, too_many = a  # bad-unpacking
        _, too_few = a  # bad-unpacking
        """)

  def test_is_tuple_and_superclasses(self):
    """Test that a collections.namedtuple behaves like a tuple typewise."""
    self.Check(
        """
        import collections
        from typing import Any, MutableSequence, Sequence, Tuple
        X = collections.namedtuple("X", "a b c")

        a = X(1, "2", 42.0)

        a_tuple = a  # type: tuple
        a_typing_tuple = a  # type: Tuple[Any, Any, Any]
        # Collapses to just plain "tuple"
        a_typing_tuple_ellipses = a  # type: Tuple[Any, ...]
        a_sequence = a  # type: Sequence[Any]
        a_iter = iter(a)  # type: tupleiterator
        a_first = next(iter(a))
        a_second = a[1]
        """)

  def test_is_not_incorrect_types(self):
    self.CheckWithErrors(
        """
        import collections
        from typing import Any, MutableSequence, Sequence, Tuple
        X = collections.namedtuple("X", "a b c")

        x = X(1, "2", 42.0)

        x_not_a_list = x  # type: list  # annotation-type-mismatch
        x_not_a_mutable_seq = x  # type: MutableSequence[Any]  # annotation-type-mismatch  # pylint: disable=line-too-long
        """)

  def test_meets_protocol(self):
    self.Check("""
        import collections
        from typing import Any, Protocol
        X = collections.namedtuple("X", ["a", "b"])

        class DualVarHolder(Protocol):
          a: Any
          b: Any

        class DualPropertyHolder(Protocol):
          @property
          def a(self):
            ...

          @property
          def b(self):
            ...

        a = X(1, "2")
        a_vars_protocol: DualVarHolder = a
        a_property_protocol: DualPropertyHolder = a
    """)

  def test_does_not_meet_mismatching_protocol(self):
    self.CheckWithErrors("""
        import collections
        from typing import Any, Protocol
        X = collections.namedtuple("X", ["a", "b"])

        class TripleVarHolder(Protocol):
          a: Any
          b: Any
          c: Any

        class DualHolder_Alt(Protocol):
          x: Any
          y: Any

        a = X(1, "2")
        a_wrong_names: DualHolder_Alt = a  # annotation-type-mismatch
        a_too_many: TripleVarHolder = a  # annotation-type-mismatch
    """)

  def test_instantiate_pyi_namedtuple(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple('X', [('y', str), ('z', int)])): ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.X()  # missing-parameter[e1]
        foo.X(0, "")  # wrong-arg-types[e2]
        foo.X(z="", y=0)  # wrong-arg-types[e3]
        foo.X("", 0)
        foo.X(y="", z=0)
      """, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e1": r"y", "e2": r"str.*int", "e3": r"str.*int"})

  def test_use_pyi_namedtuple(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple("X", [])): ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.X()._replace()
        foo.X().nonsense  # attribute-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"nonsense.*X"})

  def test_subclass_pyi_namedtuple(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple("X", [("y", int)])): ...
      """)
      self.Check("""
        import foo
        class Y(foo.X):
          def __new__(cls):
            return super(Y, cls).__new__(cls, 0)
        Y()
      """, pythonpath=[d.path])

  def test_varargs(self):
    self.Check("""
      import collections
      X = collections.namedtuple("X", [])
      args = None  # type: list
      X(*args)
    """)

  def test_kwargs(self):
    self.Check("""
      import collections
      X = collections.namedtuple("X", [])
      kwargs = None  # type: dict
      X(**kwargs)
    """)

  def test_name_conflict(self):
    self.Check("""
      import collections
      X = collections.namedtuple("_", [])
      Y = collections.namedtuple("_", [])
      Z = collections.namedtuple("_", "a")
    """, deep=False)

  def test_subclass(self):
    self.Check("""
      import collections
      class X(collections.namedtuple("X", [])):
        def __new__(cls, _):
          return super(X, cls).__new__(cls)
      a = X(1)
      assert_type(a, X)
    """)

  def test_subclass_replace(self):
    self.Check("""
      import collections
      X = collections.namedtuple("X", "a")
      class Y(X): pass
      z = Y(1)._replace(a=2)
    """)

  def test_subclass_make(self):
    self.Check("""
      import collections
      X = collections.namedtuple("X", "a")
      class Y(X): pass
      z = Y._make([1])
      assert_type(z, Y)
    """)


if __name__ == "__main__":
  test_base.main()
