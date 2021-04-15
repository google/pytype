"""Tests of builtins.tuple."""

from pytype.tests import test_base


class TupleTest(test_base.TargetIndependentTest):
  """Tests for builtins.tuple."""

  def test_getitem_int(self):
    ty = self.Infer("""
      t = ("", 42)
      v1 = t[0]
      v2 = t[1]
      v3 = t[2]
      v4 = t[-1]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      t = ...   # type: Tuple[str, int]
      v1 = ...  # type: str
      v2 = ...  # type: int
      v3 = ...  # type: Union[str, int]
      v4 = ...  # type: int
    """)

  @test_base.skip("Needs better slice support in abstract.Tuple, convert.py.")
  def test_getitem_slice(self):
    ty = self.Infer("""
      t = ("", 42)
      v1 = t[:]
      v2 = t[:1]
      v3 = t[1:]
      v4 = t[0:1]
      v5 = t[0:2:2]
      v6 = t[:][0]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t = ...  # type: Tuple[str, int]
      v1 = ...  # type: Tuple[str, int]
      v2 = ...  # type: Tuple[str]
      v3 = ...  # type: Tuple[int]
      v4 = ...  # type: Tuple[str]
      v5 = ...  # type: Tuple[str]
      v6 = ...  # type: str
    """)

  def test_unpack_tuple(self):
    ty = self.Infer("""
      v1, v2 = ("", 42)
      _, w = ("", 42)
      x, (y, z) = ("", (3.14, True))
    """)
    self.assertTypesMatchPytd(ty, """
      v1 = ...  # type: str
      v2 = ...  # type: int
      _ = ...  # type: str
      w = ...  # type: int
      x = ...  # type: str
      y = ...  # type: float
      z = ...  # type: bool
    """)

  def test_bad_unpacking(self):
    ty, errors = self.InferWithErrors("""
      tup = (1, "")
      a, = tup  # bad-unpacking[e1]
      b, c, d = tup  # bad-unpacking[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      tup = ...  # type: Tuple[int, str]
      a = ...  # type: Union[int, str]
      b = ...  # type: Union[int, str]
      c = ...  # type: Union[int, str]
      d = ...  # type: Union[int, str]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"2 values.*1 variable", "e2": r"2 values.*3 variables"})

  def test_mutable_item(self):
    ty = self.Infer("""
      v = {}
      w = v.setdefault("", ([], []))
      w[1].append(42)
      u = w[2]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: dict[str, tuple[list[nothing], list[int]]]
      w = ...  # type: tuple[list[nothing], list[int]]
      u = ...  # type: list[int]
    """)

  def test_bad_tuple_class_getitem(self):
    errors = self.CheckWithErrors("""
      v = type((3, ""))
      w = v[0]  # invalid-annotation[e1]  # invalid-annotation[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Expected 0 parameter\(s\), got 1",
                                     "e2": r"'0'.*Not a type"})

  def test_tuple_isinstance(self):
    ty = self.Infer("""
      x = ()
      if isinstance(x, tuple):
        y = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      x = ...  # type: Tuple[()]
      y = ...  # type: int
    """)

  def test_add_twice(self):
    self.Check("() + () + ()")

  def test_inplace_add(self):
    ty = self.Infer("""
      a = ()
      a += (42,)
      b = ()
      b += (42,)
      b += ("foo",)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      a = ...  # type: Tuple[int, ...]
      b = ...  # type: Tuple[Union[int, str], ...]
    """)

  def test_tuple_of_tuple(self):
    self.assertNoCrash(self.Infer, """
      def f(x=()):
        x = (x,)
        enumerate(x)
        lambda: x
        return x
    """)

  def test_tuple_container_matching(self):
    # Regression test for crash introduced by using
    # matcher.match_var_against_type() for container mutation checking without
    # fully populating the view.
    self.Check("""
      from typing import Dict, Tuple

      class Foo:
        pass

      class _SupplyPoolAsset:
        def __init__(self):
          self._resources_available = {}
          self._resources_used = {}  # type: Dict[str, Tuple[Foo, Foo]]
          self._PopulateResources()

        def _PopulateResources(self):
          for x, y, z in __any_object__:
            self._resources_available[x] = (y, z)
          for x, y, z in __any_object__:
            self._resources_available[x] = (y, z)

        def RequestResource(self, resource):
          self._resources_used[
              resource.Name()] = self._resources_available[resource.Name()]
    """)

  def test_bad_extra_parameterization(self):
    errors = self.CheckWithErrors("""
      from typing import Tuple
      X = Tuple[int][str]  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 0 parameter\(s\), got 1"})

  def test_legal_extra_parameterization(self):
    ty = self.Infer("""
      from typing import Tuple, TypeVar
      T = TypeVar('T')
      X = Tuple[T][T][str]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, TypeVar
      T = TypeVar('T')
      X = Tuple[str]
    """)


test_base.main(globals(), __name__ == "__main__")
