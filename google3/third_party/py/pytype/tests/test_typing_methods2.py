"""Tests for the methods in the typing module."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TypingMethodsTest(test_base.BaseTest):
  """Tests for typing.py."""

  def test_mapping(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Mapping
        K = TypeVar("K")
        V = TypeVar("V")
        class MyDict(Mapping[K, V]): ...
        def f() -> MyDict[str, int]: ...
      """)
      ty = self.Infer("""
        import foo
        m = foo.f()
        a = m.copy()
        b = "foo" in m
        c = m["foo"]
        d = m.get("foo", 3)
        e = [x for x in m.items()]
        f = [x for x in m.keys()]
        g = [x for x in m.values()]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Tuple, Union
        import foo
        m = ...  # type: foo.MyDict[str, int]
        a = ...  # type: typing.Mapping[str, int]
        b = ...  # type: bool
        c = ...  # type: int
        d = ...  # type: int
        e = ...  # type: List[Tuple[str, int]]
        f = ...  # type: List[str]
        g = ...  # type: List[int]
      """)

  def test_supportsbytes(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import SupportsBytes
        def f() -> SupportsBytes: ...
      """)
      self.Check("""
        import foo
        x = foo.f()
        bytes(x)
      """, pythonpath=[d.path])

  def test_assert_never(self):
    self.Check("""
      from typing import Union
      from typing_extensions import assert_never
      def int_or_str(arg: Union[int, str]) -> None:
        if isinstance(arg, int):
          pass
        elif isinstance(arg, str):
          pass
        else:
          assert_never("oops!")
    """)

  def test_assert_never_failure(self):
    errors = self.CheckWithErrors("""
      from typing import Union
      from typing_extensions import assert_never
      def int_or_str(arg: Union[int, str]) -> None:
        if isinstance(arg, int):
          pass
        else:
          assert_never("oops!")  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(
        errors, {"e": ["Expected", "empty", "Actual", "str"]})


if __name__ == "__main__":
  test_base.main()
