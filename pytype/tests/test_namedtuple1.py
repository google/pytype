"""Tests for the namedtuple implementation in collections_overlay.py."""

import textwrap

from pytype import file_utils
from pytype.overlays import collections_overlay
from pytype.pytd import escape
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class NamedtupleTests(test_base.BaseTest):
  """Tests for collections.namedtuple."""

  def _namedtuple_ast(self, name, fields):
    return collections_overlay.namedtuple_ast(
        name,
        fields, [False] * len(fields),
        python_version=self.python_version,
        strict_namedtuple_checks=self.options.strict_namedtuple_checks)

  def _namedtuple_def(self, suffix="", **kws):
    """Generate the expected pyi for a simple namedtuple definition.

    Args:
      suffix: Optionally, extra text to append to the pyi.
      **kws: Must contain exactly one argument of the form
        alias=(name, [<fields>]). For example, to generate a definition for
        X = namedtuple("_X", "y z"), the method call should be
        _namedtuple_def(X=("_X", ["y", "z"])).

    Returns:
      The expected pyi for the namedtuple instance.
    """
    (alias, (name, fields)), = kws.items()  # pylint: disable=unbalanced-tuple-unpacking
    name = escape.pack_namedtuple(name, fields)
    suffix += textwrap.dedent("""
      collections = ...  # type: module
      {alias} = {name}""").format(alias=alias, name=name)
    return pytd_utils.Print(self._namedtuple_ast(name, fields)) + "\n" + suffix

  def test_basic_namedtuple(self):
    ty = self.Infer("""
      import collections

      X = collections.namedtuple("X", ["y", "z"])
      a = X(y=1, z=2)
      """, deep=False)
    self.assertTypesMatchPytd(ty, self._namedtuple_def(
        X=("X", ["y", "z"]), suffix="a = ...  # type: X"))

  def test_no_fields(self):
    ty = self.Infer("""
        import collections

        F = collections.namedtuple("F", [])
        a = F()
        """, deep=False)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def(F=("F", []), suffix="a = ...  # type: F"))

  def test_str_args(self):
    ty = self.Infer("""
        import collections

        S = collections.namedtuple("S", "a b c")
        b = S(1, 2, 3)
    """, deep=False)
    self.assertTypesMatchPytd(ty, self._namedtuple_def(
        S=("S", ["a", "b", "c"]), suffix="b = ...  # type: S"))

  def test_str_args2(self):
    self.Check("""
        import collections
        collections.namedtuple("_", "a,b,c")
        """)
    self.Check("""
        import collections
        collections.namedtuple("_", "a, b, c")
        """)
    self.Check("""
        import collections
        collections.namedtuple("_", "a ,b")
        """)

  def test_bad_fieldnames(self):
    self.InferWithErrors("""
        import collections
        collections.namedtuple("_", ["abc", "def", "ghi"])  # invalid-namedtuple-arg
        collections.namedtuple("_", "_")  # invalid-namedtuple-arg
        collections.namedtuple("_", "a, 1")  # invalid-namedtuple-arg
        collections.namedtuple("_", "a, !")  # invalid-namedtuple-arg
        collections.namedtuple("_", "a, b, c, a")  # invalid-namedtuple-arg
        collections.namedtuple("1", "")  # invalid-namedtuple-arg
        """)

  def test_rename(self):
    ty = self.Infer("""
        import collections

        S = collections.namedtuple("S", "abc def ghi abc", rename=True)
        """, deep=False)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def(S=("S", ["abc", "_1", "ghi", "_3"])))

  def test_bad_initialize(self):
    self.InferWithErrors("""
        from collections import namedtuple

        X = namedtuple("X", "y z")
        a = X(1)  # missing-parameter
        b = X(y = 2)  # missing-parameter
        c = X(w = 3)  # wrong-keyword-args
        d = X(y = "hello", z = 4j)  # works
        """)

  def test_class_name(self):
    ty = self.Infer(
        """
        import collections
        F = collections.namedtuple("S", ['a', 'b', 'c'])
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def(F=("S", ["a", "b", "c"])))

  def test_constructors(self):
    self.Check("""
        import collections
        X = collections.namedtuple("X", "a b c")
        g = X(1, 2, 3)
        i = X._make((7, 8, 9))
        j = X._make((10, 11, 12), tuple.__new__, len)
        """)

  def test_instance_types(self):
    ty = self.Infer(
        """
        import collections
        X = collections.namedtuple("X", "a b c")
        a = X._make((1, 2, 3))
        """)
    self.assertTypesMatchPytd(ty, self._namedtuple_def(
        X=("X", ["a", "b", "c"]), suffix="a = ...  # type: X"))

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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    ty = self.Infer("""
      import collections
      X = collections.namedtuple("_", [])
      Y = collections.namedtuple("_", [])
      Z = collections.namedtuple("_", "a")
    """, deep=False)
    name_x = escape.pack_namedtuple("_", [])
    name_z = escape.pack_namedtuple("_", ["a"])
    ast_x = self._namedtuple_ast(name_x, [])
    ast_z = self._namedtuple_ast(name_z, ["a"])
    ast = pytd_utils.Concat(ast_x, ast_z)
    expected = pytd_utils.Print(ast) + textwrap.dedent("""
      collections = ...  # type: module
      X = {name_x}
      Y = {name_x}
      Z = {name_z}""").format(name_x=name_x, name_z=name_z)
    self.assertTypesMatchPytd(ty, expected)

  def test_subclass(self):
    ty = self.Infer("""
      import collections
      class X(collections.namedtuple("X", [])):
        def __new__(cls, _):
          return super(X, cls).__new__(cls)
    """)
    name = escape.pack_namedtuple("X", [])
    ast = self._namedtuple_ast(name, [])
    expected = pytd_utils.Print(ast) + textwrap.dedent("""
      collections = ...  # type: module
      _TX = TypeVar("_TX", bound=X)
      class X({name}):
        def __new__(cls: Type[_TX], _) -> _TX: ...""").format(name=name)
    self.assertTypesMatchPytd(ty, expected)

  def test_subclass_replace(self):
    ty = self.Infer("""
      import collections
      X = collections.namedtuple("X", "a")
      class Y(X): pass
      z = Y(1)._replace(a=2)
    """)
    self.assertEqual(pytd_utils.Print(ty.Lookup("z")), "z: Y")

  def test_subclass_make(self):
    ty = self.Infer("""
      import collections
      X = collections.namedtuple("X", "a")
      class Y(X): pass
      z = Y._make([1])
    """)
    self.assertEqual(pytd_utils.Print(ty.Lookup("z")), "z: Y")

if __name__ == "__main__":
  test_base.main()
