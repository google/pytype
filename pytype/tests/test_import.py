"""Tests for import."""


from pytype import utils
from pytype.tests import test_inference


class ImportTest(test_inference.InferenceTest):
  """Tests for import."""

  def testBasicImport(self):
    self.assert_ok("""\
      import sys
      """)

  def testPathImport(self):
    self.assert_ok("""\
      import path.to.some.module
      """)

  def testFromImport(self):
    self.assert_ok("""\
      from sys import exit
      from path.to.module import bar, baz
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
        f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("f"), self.module)

  def testMatchModule(self):
    with self.Infer("""
      import sys
      def f():
        if getattr(sys, "foobar"):
          return {sys: sys}.keys()[0]
        else:
          return sys
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("f"), self.module)

  def testSys(self):
    with self.Infer("""
      import sys
      def f():
        return sys.path
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("f"), self.str_list)

  def testFromSysImport(self):
    with self.Infer("""
      from sys import path
      def f():
        return path
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("f"), self.str_list)

  def testStdlib(self):
    with self.Infer("""
      import StringIO
      def f():
        return StringIO.StringIO().isatty()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  # TODO(pludemann): Implement import of .py
  # This test has never worked, except in the sense that it didn't fail.
  # We need to define how import works if there's a .py file; also how it
  # works if there are both a .py file and a .pytd file.
  def testImportPy(self):
    with utils.Tempdir() as d:
      d.create_file("other_file.py", """
        def f():
          pass
      """)
      d.create_file("main.py", """
        from other_file import f
      """)
      ty = self.InferFromFile(
          filename=d["main.py"],
          # Note that .pytd is the extension for pythonpath and not .py, so
          # "import" will fail to find other_file.py
          pythonpath=[d.path], pytd_import_ext=".pytd")
      # TODO(kramm): Do more testing here once pludemann@ has implemented logic
      #              for actually using pythonpath. Also below.
      self.assertTrue(ty.Lookup("f"))

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
      self.assertTrue(ty.Lookup("f"))

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

if __name__ == "__main__":
  test_inference.main()
