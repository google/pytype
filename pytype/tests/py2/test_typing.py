"""Tests for typing.py."""

from pytype import file_utils
from pytype.tests import test_base


class TypingTest(test_base.TargetPython27FeatureTest):
  """Tests for typing.py."""

  def test_namedtuple_item(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        def f() -> NamedTuple("ret", [("x", int), ("y", unicode)]): ...
      """)
      ty = self.Infer("""
        import foo
        w = foo.f()[-1]
        x = foo.f()[0]
        y = foo.f()[1]
        z = foo.f()[2]  # out of bounds, fall back to the combined element type
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        foo = ...  # type: module
        w = ...  # type: unicode
        x = ...  # type: int
        y = ...  # type: unicode
        z = ...  # type: Union[int, unicode]
      """)

  def test_match(self):
    ty = self.Infer("""
      import re
      match1 = re.search("(?P<foo>.*)", "bar")
      match2 = re.search("(?P<foo>.*)", u"bar")
      assert match1 and match2
      v1 = match1.group(u"foo")
      v2 = match2.group("foo")
      v3 = match1.group(u"foo", u"foo")
      v4 = match1.start(u"foo")
      v5 = match1.end(u"foo")
      v6 = match1.span(u"foo")
      v7 = match1.groups("foo")
      v8 = match1.groups()
      v9 = match1.groups(None)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Match, Optional, Tuple
      re = ...  # type: module
      match1 = ...  # type: Optional[Match[str]]
      match2 = ...  # type: Optional[Match[unicode]]
      v1 = ...  # type: str
      v2 = ...  # type: unicode
      v3 = ...  # type: Tuple[str, ...]
      v4 = ...  # type: int
      v5 = ...  # type: int
      v6 = ...  # type: Tuple[int, int]
      v7 = ...  # type: Tuple[str, ...]
      v8 = ...  # type: Tuple[Optional[str], ...]
      v9 = ...  # type: Tuple[Optional[str], ...]
    """)


test_base.main(globals(), __name__ == "__main__")
