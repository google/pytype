"""Tests for dictionaries."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class DictTest(test_base.TargetIndependentTest):
  """Tests for dictionaries."""

  def test_pop(self):
    ty = self.Infer("""
      d = {"a": 42}
      v1 = d.pop("a")
      v2 = d.pop("b", None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[str, int]
      v1 = ...  # type: int
      v2 = ...  # type: None
    """)

  def test_bad_pop(self):
    ty, errors = self.InferWithErrors("""
      d = {"a": 42}
      v = d.pop("b")  # key-error[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      d = ...  # type: Dict[str, int]
      v = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"b"})

  def test_ambiguous_pop(self):
    ty = self.Infer("""
      d = {"a": 42}
      k = None  # type: str
      v1 = d.pop(k)
      v2 = d.pop(k, None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
      d = ...  # type: Dict[str, int]
      k = ...  # type: str
      v1 = ...  # type: int
      v2 = ...  # type: Optional[int]
    """)

  def test_pop_from_ambiguous_dict(self):
    ty = self.Infer("""
      d = {}
      k = None  # type: str
      v = None  # type: int
      d[k] = v
      v1 = d.pop("a")
      v2 = d.pop("a", None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
      d = ...  # type: Dict[str, int]
      k = ...  # type: str
      v = ...  # type: int
      v1 = ...  # type: int
      v2 = ...  # type: Optional[int]
    """)

  def test_update_empty(self):
    ty = self.Infer("""
      from typing import Dict
      d1 = {}
      d2 = None  # type: Dict[str, int]
      d1.update(d2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d1 = ...  # type: Dict[str, int]
      d2 = ...  # type: Dict[str, int]
    """)

  def test_update_any_subclass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T, y: T = ...) -> T: ...
      """)
      self.Check("""
        from typing import Any
        import foo
        class Foo(Any):
          def f(self):
            kwargs = {}
            kwargs.update(foo.f(self))
      """, pythonpath=[d.path])

  def test_update_noargs(self):
    self.Check("""
      from typing import Dict
      d = {}  # type: Dict
      d.update()
    """)

  def test_determinism(self):
    # Regression test for code on which pytype used to be non-deterministic.
    canonical = None
    for _ in range(10):  # increase the chance of finding non-determinism
      ty = self.Infer("""
        class Foo(object):
          def __init__(self, filenames):
            self._dict = {}
            for filename in filenames:
              d = self._dict
              if __random__:
                d[__any_object__] = {}
                d = d[__any_object__]
              if __random__:
                d[__any_object__] = None
      """)
      out = pytd_utils.Print(ty)
      if canonical is None:
        canonical = out
      else:
        self.assertMultiLineEqual(canonical, out)


test_base.main(globals(), __name__ == "__main__")
