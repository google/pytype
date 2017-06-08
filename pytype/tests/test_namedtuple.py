"""Tests for the namedtuple implementation in collections_overlay.py."""
import textwrap


from pytype import collections_overlay
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import utils as pytd_utils
from pytype.tests import test_inference


class NamedtupleTests(test_inference.InferenceTest):
  """Tests for collections.namedtuple."""

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
    (alias, (name, fields)), = kws.items()
    name = collections_overlay.namedtuple_name(name, fields)
    suffix += textwrap.dedent("""
      collections = ...  # type: module
      {alias} = {name}""").format(alias=alias, name=name)
    return pytd.Print(collections_overlay.namedtuple_ast(name, fields)) + suffix

  def test_basic_namedtuple(self):
    ty = self.Infer("""
      import collections

      X = collections.namedtuple("X", ["y", "z"])
      a = X(y=1, z=2)
      """)
    self.assertTypesMatchPytd(ty, self._namedtuple_def(
        X=("X", ["y", "z"]), suffix="a = ...  # type: X"))

  def test_no_fields(self):
    ty = self.Infer("""
        import collections

        F = collections.namedtuple("F", [])
        a = F()
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def(F=("F", []), suffix="a = ...  # type: F"))

  def test_str_args(self):
    ty = self.Infer("""
        import collections

        S = collections.namedtuple("S", "a b c")
        b = S(1, 2, 3)
    """)
    self.assertTypesMatchPytd(ty, self._namedtuple_def(
        S=("S", ["a", "b", "c"]), suffix="b = ...  # type: S"))

  def test_str_args2(self):
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "a,b,c")
        """)
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "a, b, c")
        """)
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "a ,b")
        """)

  def test_bad_fieldnames(self):
    _, errorlog = self.InferAndCheck("""\
        import collections
        collections.namedtuple("_", ["abc", "def", "ghi"])
        collections.namedtuple("_", "_")
        collections.namedtuple("_", "a, 1")
        collections.namedtuple("_", "a, !")
        collections.namedtuple("_", "a, b, c, a")
        collections.namedtuple("1", "")
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "invalid-namedtuple-arg"),
                           (3, "invalid-namedtuple-arg"),
                           (4, "invalid-namedtuple-arg"),
                           (5, "invalid-namedtuple-arg"),
                           (6, "invalid-namedtuple-arg"),
                           (7, "invalid-namedtuple-arg")])

  def test_rename(self):
    ty = self.Infer("""
        import collections

        S = collections.namedtuple("S", "abc def ghi abc", rename=True)
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def(S=("S", ["abc", "_1", "ghi", "_3"])))

  def test_bad_initialize(self):
    _, errlog = self.InferAndCheck("""\
        from collections import namedtuple

        X = namedtuple("X", "y z")
        a = X(1)
        b = X(y = 2)
        c = X(w = 3)
        d = X(y = "hello", z = 4j)  # works
        """)
    self.assertErrorLogIs(errlog, [
        (4, "missing-parameter"),
        (5, "missing-parameter"),
        (6, "wrong-keyword-args")])

  def test_class_name(self):
    ty = self.Infer(
        """\
        import collections
        F = collections.namedtuple("S", ['a', 'b', 'c'])
        """)
    self.assertTypesMatchPytd(
        ty, self._namedtuple_def(F=("S", ["a", "b", "c"])))

  def test_calls(self):
    self.assertNoErrors("""
        import collections
        collections.namedtuple("_", "")
        collections.namedtuple(typename="_", field_names="a")
        collections.namedtuple("_", "", True, False)
        """)
    self.assertNoCrash("""
      collections.namedtuple(u"foo", [])
      collections.namedtuple(u"foo", [], replace=True if __random__ else False)
      collections.namedtuple(1.0, [])
      collections.namedtuple("foo", [1j, 2j])
      collections.namedtuple(__any_object__, __any_object__)
      collections.namedtuple(__any_object__, [__any_object__])
      """)

  def test_bad_call(self):
    _, errorlog = self.InferAndCheck("""\
        import collections
        collections.namedtuple()
        collections.namedtuple("_")
        collections.namedtuple("_", "", True, True, True)
        collections.namedtuple("_", "", True, verbose=True)
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "missing-parameter"),
                           (3, "missing-parameter"),
                           (4, "wrong-arg-count"),
                           (5, "duplicate-keyword-argument")])

  def test_constructors(self):
    self.assertNoErrors("""
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

  def test_namedtuple_match(self):
    self.assertNoErrors("""\
        from __future__ import google_type_annotations
        import collections
        from typing import Any, Dict

        X = collections.namedtuple("X", ["a"])

        def GetRefillSeekerRanks() -> Dict[str, X]:
          return {"hello": X(__any_object__)}
        """)

  def test_instantiate_pyi_namedtuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple('X', [('y', str), ('z', int)])): ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.X()  # wrong arg count
        foo.X(0, "")  # wrong types
        foo.X(z="", y=0)  # wrong types
        foo.X("", 0)
        foo.X(y="", z=0)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "missing-parameter", r"y"),
                                     (3, "wrong-arg-types", r"str.*int"),
                                     (4, "wrong-arg-types", r"str.*int")])

  def test_use_pyi_namedtuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple("X", [])): ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.X()._replace()
        foo.X().nonsense
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "attribute-error", r"nonsense.*X")])

  def test_subclass_pyi_namedtuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(NamedTuple("X", [("y", int)])): ...
      """)
      self.assertNoErrors("""
        import foo
        class Y(foo.X):
          def __new__(cls):
            return super(Y, cls).__new__(cls, 0)
        Y()
      """, pythonpath=[d.path])

  def test_varargs(self):
    self.assertNoErrors("""
      import collections
      X = collections.namedtuple("X", [])
      args = None  # type: list
      X(*args)
    """)

  def test_kwargs(self):
    self.assertNoErrors("""
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
    """)
    name_x = collections_overlay.namedtuple_name("_", [])
    name_z = collections_overlay.namedtuple_name("_", ["a"])
    ast_x = collections_overlay.namedtuple_ast(name_x, [])
    ast_z = collections_overlay.namedtuple_ast(name_z, ["a"])
    ast = pytd_utils.Concat(ast_x, ast_z)
    expected = pytd.Print(ast) + textwrap.dedent("""\
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
    """, deep=True)
    name = collections_overlay.namedtuple_name("X", [])
    ast = collections_overlay.namedtuple_ast(name, [])
    expected = pytd.Print(ast) + textwrap.dedent("""\
      collections = ...  # type: module
      _TX = TypeVar("_TX", bound=X)
      class X({name}):
        def __new__(cls: Type[_TX], _) -> _TX: ...""").format(name=name)
    self.assertTypesMatchPytd(ty, expected)


if __name__ == "__main__":
  test_inference.main()
