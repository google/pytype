"""Tests for handling PYI code."""

from pytype import utils
from pytype.tests import test_base


class PYITest(test_base.TargetPython27FeatureTest):
  """Tests for PYI."""

  def testBytes(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f() -> bytes
      """)
      ty = self.Infer("""
        import foo
        x = foo.f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: str
      """)

  def testVarargs(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_varargs(x: int, *args: T, z: int, **kws: int) -> T: ...
      """)
      ty, errors = self.InferWithErrors("""\
        from typing import Union
        import a
        l1 = None  # type: list[str]
        l2 = None  # type: list[Union[str, complex]]
        v1 = a.get_varargs(1, *l1)
        v2 = a.get_varargs(1, *l2, z=5)
        v3 = a.get_varargs(1, True, 2.0, z=5)
        v4 = a.get_varargs(1, 2j, "foo", z=5)  # bad: conflicting args types
        v5 = a.get_varargs(1, *None)  # bad: None not iterable
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        l1 = ...  # type: list[str]
        l2 = ...  # type: list[str or complex]
        v1 = ...  # type: str
        v2 = ...  # type: str or complex
        v3 = ...  # type: bool or float
        v4 = ...  # type: Any
        v5 = ...  # type: Any
      """)
      msg1 = (r"Expected: \(x, _, _2: complex, \.\.\.\).*"
              r"Actually passed: \(x, _, _2: str, \.\.\.\)")
      msg2 = (r"Expected: \(x, \*args: Iterable, \.\.\.\).*"
              r"Actually passed: \(x, args: None\)")
      self.assertErrorLogIs(errors, [(8, "wrong-arg-types", msg1),
                                     (9, "wrong-arg-types", msg2)])

  # TODO(sivachandra): Make this a target independent test after
  # after b/78785264 is fixed.
  def testKwargs(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def get_kwargs(x: int, *args: int, z: int, **kws: T) -> T: ...
      """)
      ty, errors = self.InferWithErrors("""\
        from typing import Mapping, Union
        import a
        d1 = None  # type: dict[int, int]
        d2 = None  # type: Mapping[str, Union[str, complex]]
        v1 = a.get_kwargs(1, 2, 3, z=5, **d1)  # bad: K must be str
        v2 = a.get_kwargs(1, 2, 3, z=5, **d2)
        v3 = a.get_kwargs(1, 2, 3, z=5, v=0, u=3j)
        # bad: conflicting kwargs types
        v4 = a.get_kwargs(1, 2, 3, z=5, v="", u=3j)
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Mapping
        a = ...  # type: module
        d1 = ...  # type: dict[int, int]
        d2 = ...  # type: Mapping[str, str or complex]
        v1 = ...  # type: Any
        v2 = ...  # type: str or complex
        v3 = ...  # type: int or complex
        v4 = ...  # type: Any
      """)
      msg1 = (r"Expected: \(x, \*args, z, \*\*kws: Mapping\[str, Any\]\).*"
              r"Actually passed: \(x, _, _, z, kws: Dict\[int, int\]\)")
      msg2 = (r"Expected: \(x, _, _, u, v: complex, \.\.\.\).*"
              r"Actually passed: \(x, _, _, u, v: str, \.\.\.\)")
      self.assertErrorLogIs(errors, [(5, "wrong-arg-types", msg1),
                                     (9, "wrong-arg-types", msg2)])


test_base.main(globals(), __name__ == "__main__")
