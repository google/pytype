"""Tests for handling PYI code."""

from pytype import file_utils
from pytype.tests import test_base


class PYITest(test_base.TargetPython27FeatureTest):
  """Tests for PYI."""

  def test_bytes(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f() -> bytes: ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: str
      """)

  def test_varargs(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_varargs(x: int, *args: T, z: int, **kws: int) -> T: ...
      """)
      ty, errors = self.InferWithErrors("""
        from typing import Union
        import a
        l1 = None  # type: list[str]
        l2 = None  # type: list[Union[str, complex]]
        v1 = a.get_varargs(1, *l1)
        v2 = a.get_varargs(1, *l2, z=5)
        v3 = a.get_varargs(1, True, 2.0, z=5)
        # bad: conflicting args types
        v4 = a.get_varargs(1, 2j, "foo", z=5)  # wrong-arg-types[e1]
        # bad: None not iterable
        v5 = a.get_varargs(1, *None)  # wrong-arg-types[e2]
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Union
        a = ...  # type: module
        l1 = ...  # type: list[str]
        l2 = ...  # type: list[Union[str, complex]]
        v1 = ...  # type: str
        v2 = ...  # type: Union[str, complex]
        v3 = ...  # type: Union[bool, float]
        v4 = ...  # type: Any
        v5 = ...  # type: Any
      """)
      msg1 = (r"Expected: \(x, _, _2: complex, \.\.\.\).*"
              r"Actually passed: \(x, _, _2: str, \.\.\.\)")
      msg2 = (r"Expected: \(x, \*args: Iterable, \.\.\.\).*"
              r"Actually passed: \(x, args: None\)")
      self.assertErrorRegexes(errors, {"e1": msg1, "e2": msg2})

  def test_kwargs(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_kwargs(x: int, *args: int, z: int, **kws: T) -> T: ...
      """)
      ty, errors = self.InferWithErrors("""
        from typing import Mapping, Union
        import a
        d1 = None  # type: dict[int, int]
        d2 = None  # type: Mapping[str, Union[str, complex]]
        # bad: K must be str
        v1 = a.get_kwargs(1, 2, 3, z=5, **d1)  # wrong-arg-types[e1]
        v2 = a.get_kwargs(1, 2, 3, z=5, **d2)
        v3 = a.get_kwargs(1, 2, 3, z=5, v=0, u=3j)
        # bad: conflicting kwargs types
        v4 = a.get_kwargs(1, 2, 3, z=5, v="", u=3j)  # wrong-arg-types[e2]
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Mapping, Union
        a = ...  # type: module
        d1 = ...  # type: dict[int, int]
        d2 = ...  # type: Mapping[str, Union[str, complex]]
        v1 = ...  # type: Any
        v2 = ...  # type: Union[str, complex]
        v3 = ...  # type: Union[int, complex]
        v4 = ...  # type: Any
      """)
      msg1 = (r"Expected: \(x, \*args, z, \*\*kws: Mapping\[str, Any\]\).*"
              r"Actually passed: \(x, _, _, z, kws: Dict\[int, int\]\)")
      msg2 = (r"Expected: \(x, _, _, u, v: complex, \.\.\.\).*"
              r"Actually passed: \(x, _, _, u, v: str, \.\.\.\)")
      self.assertErrorRegexes(errors, {"e1": msg1, "e2": msg2})


test_base.main(globals(), __name__ == "__main__")
