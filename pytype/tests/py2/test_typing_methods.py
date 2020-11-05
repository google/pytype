"""Tests for the methods in the typing module."""

from pytype import file_utils
from pytype.tests import test_base


class TypingMethodsTest(test_base.TargetPython27FeatureTest):
  """Tests for typing.py."""

  def test_mapping(self):
    with file_utils.Tempdir() as d:
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
        h = [x for x in m.iteritems()]
        i = [x for x in m.iterkeys()]
        j = [x for x in m.itervalues()]
        k = [x for x in m.viewitems()]
        l = [x for x in m.viewkeys()]
        n = [x for x in m.viewvalues()]
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Tuple, Union
        import foo
        foo = ...  # type: module
        m = ...  # type: foo.MyDict[str, int]
        a = ...  # type: typing.Mapping[str, int]
        b = ...  # type: bool
        c = ...  # type: int
        d = ...  # type: int
        e = ...  # type: List[Tuple[str, int]]
        f = ...  # type: List[str]
        g = ...  # type: List[int]
        h = ...  # type: List[Tuple[str, int]]
        i = ...  # type: List[str]
        j = ...  # type: List[int]
        k = ...  # type: List[Tuple[str, int]]
        l = ...  # type: List[str]
        n = ...  # type: List[int]
        x = ...  # type: Union[int, str, Tuple[str, int]]
      """)


test_base.main(globals(), __name__ == "__main__")
