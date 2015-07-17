"""Tests for import."""

import unittest

from pytype import utils
from pytype.tests import test_inference


class ImportTest(test_inference.InferenceTest):
  """Tests for import."""

  def testBasicImport(self):
    with self.Infer("""\
      import sys
      """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
         sys: module
      """)

  def testBasicImport2(self):
    with self.Infer("""\
      import bad_import
      """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        bad_import: ?
      """)

  def testFromImportSmoke(self):
    self.assert_ok("""\
      from sys import exit
      from path.to.module import bar, baz
      """)

  def testPathImport(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pytd",
                    "def qqsv() -> str")
      with self.Infer("""\
      import path.to.my_module
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, solve_unknowns=True,
           pythonpath=[d.path], pytd_import_ext=".pytd") as ty:
        self.assertTypesMatchPytd(ty, """
          path: module
          def foo() -> str
        """)

  def testPathImport2(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pytd",
                    "def qqsv() -> str")
      with self.Infer("""\
      import nonexistant_path.to.my_module
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, solve_unknowns=True,
           pythonpath=[d.path], pytd_import_ext=".pytd") as ty:
        self.assertTypesMatchPytd(ty, """
          nonexistant_path: ?
          def foo() -> ?
        """)

  def testImportAll(self):
    self.assert_ok("""\
      from module import *
      from path.to.module import *
      """)

  def testAssignMember(self):
    self.assert_ok("""\
      import sys
      sys.path = []
      """)

  def testReturnModule(self):
    with self.Infer("""
        import sys

        def f():
          return sys
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        sys: module
        def f() -> module
      """)

  def testMatchModule(self):
    with self.Infer("""
      import sys
      def f():
        if getattr(sys, "foobar"):
          return {sys: sys}.keys()[0]
        else:
          return sys
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        sys: module
        def f() -> module
      """)

  def testSys(self):
    with self.Infer("""
      import sys
      def f():
        return sys.path
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        sys: module
        def f() -> list<str>
      """)

  def testFromSysImport(self):
    with self.Infer("""
      from sys import path
      def f():
        return path
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        path: list<str>
        def f() -> list<str>
      """)

  def testImportSys2(self):
    with self.Infer("""
      import sys
      import bad_import
      def f():
        return sys.stderr
      def g():
        return sys.maxint
      def h():
        return sys.getrecursionlimit()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        bad_import: ?
        sys: module
        def f() -> file
        def g() -> int
        def h() -> int
      """)

  def testStdlib(self):
    with self.Infer("""
      import StringIO
      def f():
        return StringIO.StringIO().isatty()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        StringIO: module
        def f() -> bool
      """)

  # TODO(pludemann): Implement import of .py
  # This test has never worked, except in the sense that it didn't fail.
  # We need to define how import works if there's a .py file; also how it
  # works if there are both a .py file and a .pytd file.
  @unittest.skip("Broken - def g() -> long list of types")
  def testImportPy(self):
    with utils.Tempdir() as d:
      d.create_file("other_file.py", """
        def f():
          return 3.14159
      """)
      d.create_file("main.py", """
        from other_file import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(
          filename=d["main.py"],
          # Note that .pytd is the extension for pythonpath and not .py, so
          # "import" will fail to find other_file.py
          pythonpath=[d.path], pytd_import_ext=".pytd")
      # TODO(kramm): Do more testing here once pludemann@ has implemented logic
      #              for actually using pythonpath. Also below.
      self.assertTypesMatchPytd(ty, """
        def g() -> float
      """)

  def testImportPytd(self):
    with utils.Tempdir() as d:
      d.create_file("other_file.pytd", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from other_file import f
      """)
      ty = self.InferFromFile(
          filename=d["main.py"],
          pythonpath=[d.path], pytd_import_ext=".pytd")
      self.assertTypesMatchPytd(ty, """
        f: function
      """)

  def testImportPytd2(self):
    with utils.Tempdir() as d:
      d.create_file("other_file.pytd", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from other_file import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(
          filename=d["main.py"],
          pythonpath=[d.path], pytd_import_ext=".pytd")
      self.assertTypesMatchPytd(ty, """
        f: function
        def g() -> int
      """)

  def testImportDirectory(self):
    with utils.Tempdir() as d:
      d.create_file("sub/other_file.pytd", "def f() -> int")
      d.create_file("sub/bar/baz.pytd", "def g() -> float")
      d.create_file("main.py", """
        from sub import other_file
        import sub.bar.baz
        from sub.bar.baz import g
        def h():
          return other_file.f()
        def i():
          return g()
        def j():
          return sub.bar.baz.g()
      """)
      ty = self.InferFromFile(
          filename=d["main.py"],
          pythonpath=[d.path], pytd_import_ext=".pytd")
      self.assertTypesMatchPytd(ty, """
        other_file: module
        g: function
        sub: module  # from 'import sub.bar.baz'
        def h() -> int
        def i() -> float
        def j() -> float
      """)

  def testImportInit(self):
    with utils.Tempdir() as d:
      d.create_file("sub/__init__.pytd", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from sub import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"],
                              pythonpath=[d.path], pytd_import_ext=".pytd")
      self.assertTypesMatchPytd(ty, """
        f: function
        def g() -> int
      """)

  def testImportName(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pytd", """
        class A:
          pass
        def f() -> A
      """)
      d.create_file("main.py", """
        from foo import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"],
                              pythonpath=[d.path], pytd_import_ext=".pytd")
      self.assertTypesMatchPytd(ty, """
        f: function
        def g() -> foo.A
    """)

  @unittest.skip("Broken: gives my_foo(x:object)->str")
  def testFileImport1(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pytd",
                    "def foo(x:int) -> str")
      with self.Infer("""\
        import path.to.some.module
        def my_foo(x):
          return path.to.some.module.foo(x)
      """, extra_verbose=True, deep=True,
                      solve_unknowns=True,
                      pythonpath=[d.path], pytd_import_ext=".pytd") as ty:
        self.assertTypesMatchPytd(ty, """
          path: module
          def my_foo(x:int) -> str
        """)

  @unittest.skip("Broken: gives my_foo(x:object)->str")
  def testFileImport2(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pytd",
                    "def foo(x:int) -> str")
      with self.Infer("""\
        from path.to.some import module
        def my_foo(x):
          return module.foo(x)
      """, extra_verbose=True, deep=True,
                      solve_unknowns=True,
                      pythonpath=[d.path], pytd_import_ext=".pytd") as ty:
        self.assertTypesMatchPytd(ty, """
          module: module
          def my_foo(x:int) -> str
        """)


if __name__ == "__main__":
  test_inference.main()
