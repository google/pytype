"""Tests for import."""

from pytype import file_utils
from pytype.tests import test_base


class ImportTest(test_base.TargetPython3FeatureTest):
  """Tests for import."""

  def test_module_attributes(self):
    ty = self.Infer("""
      import os
      f = os.__file__
      n = os.__name__
      d = os.__doc__
      p = os.__package__
      """)
    self.assertTypesMatchPytd(ty, """
       from typing import Optional
       os = ...  # type: module
       f = ...  # type: str
       n = ...  # type: str
       d = ...  # type: str
       p = ...  # type: Optional[str]
    """)

  def test_import_sys2(self):
    ty = self.Infer("""
      import sys
      import bad_import  # doesn't exist
      def f():
        return sys.stderr
      def g():
        return sys.maxsize
      def h():
        return sys.getrecursionlimit()
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TextIO
      bad_import = ...  # type: Any
      sys = ...  # type: module
      def f() -> TextIO: ...
      def g() -> int: ...
      def h() -> int: ...
    """)

  def test_relative_priority(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", "x = ...  # type: int")
      d.create_file("b/a.pyi", "x = ...  # type: complex")
      ty = self.Infer("""
        import a
        x = a.x
      """, deep=False, pythonpath=[d.path], module_name="b.main")
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)


test_base.main(globals(), __name__ == "__main__")
