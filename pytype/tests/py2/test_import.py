"""Tests for import."""

from pytype import utils
from pytype.tests import test_base


class ImportTest(test_base.TargetPython27FeatureTest):
  """Tests for import."""

  def testModuleAttributes(self):
    ty = self.Infer("""\
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
       d = ...  # type: str or unicode
       p = ...  # type: Optional[str]
    """)

  def testImportSys2(self):
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
      from typing import IO
      bad_import = ...  # type: ?
      sys = ...  # type: module
      def f() -> IO[str]
      def g() -> int
      def h() -> int
    """)

  def testModuleName(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      bar = """
        import baz
        x = baz.x
      """
      d.create_file("foo/bar.py", bar)
      ty = self.Infer(bar, module_name="foo.bar", pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        x = ...  # type: int
    """)

  def testRelativeName(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      d.create_file("foo/bar.py", """
        import baz
        x = baz.x
      """)
      d.create_file("foo/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["foo/bar.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        x = ...  # type: int
    """)

  def testStdlib(self):
    ty = self.Infer("""
      import StringIO
      def f():
        return StringIO.StringIO().isatty()
    """)
    self.assertTypesMatchPytd(ty, """
      StringIO = ...  # type: module
      def f() -> bool
    """)


test_base.main(globals(), __name__ == "__main__")
