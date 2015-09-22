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
      import bad_import  # doesn't exist
      """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertTypesMatchPytd(ty, """
        bad_import: ?
      """)

  def testFromImportSmoke(self):
    self.assertNoCrash("""\
      from sys import exit
      from path.to.module import bar, baz
      """)

  def testStarImportSmoke(self):
    self.assertNoErrors("""\
      from sys import *
      """)

  def testStarImportUnknownSmoke(self):
    self.assertNoCrash("""\
      from unknown_module import *
      """)

  def testStarImport(self):
    with utils.Tempdir() as d:
      d.create_file("my_module.pytd", """
        def f() -> str
        class A:
          pass
        a: A
      """)
      with self.Infer("""\
      from my_module import *
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          f: function
          A: type
          a: my_module.A
        """)

  def testPathImport(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pytd",
                    "def qqsv() -> str")
      d.create_file("path/to/__init__.pytd", "")
      d.create_file("path/__init__.pytd", "")
      with self.Infer("""\
      import path.to.my_module
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          path: module
          def foo() -> str
        """)

  def testPathImport2(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pytd",
                    "def qqsv() -> str")
      d.create_file("path/to/__init__.pytd", "")
      d.create_file("path/__init__.pytd", "")
      with self.Infer("""\
      import nonexistant_path.to.my_module  # doesn't exist
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, solve_unknowns=True, report_errors=False,
                      pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          nonexistant_path: ?
          def foo() -> ?
        """)

  def testImportAll(self):
    self.assertNoCrash("""\
      from module import *
      from path.to.module import *
      """)

  def testAssignMember(self):
    self.assertNoErrors("""\
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
      import bad_import  # doesn't exist
      def f():
        return sys.stderr
      def g():
        return sys.maxint
      def h():
        return sys.getrecursionlimit()
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
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
          pythonpath=[d.path])
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
          pythonpath=[d.path])
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
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        f: function
        def g() -> int
      """)

  def testImportDirectory(self):
    with utils.Tempdir() as d:
      d.create_file("sub/other_file.pytd", "def f() -> int")
      d.create_file("sub/bar/baz.pytd", "def g() -> float")
      d.create_file("sub/__init__.pytd", "")
      d.create_file("sub/bar/__init__.pytd", "")
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
          pythonpath=[d.path])
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
                              pythonpath=[d.path])
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
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        f: function
        def g() -> foo.A
    """)

  def testDeepDependency(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pytd", "x: bar.Bar")
      d.create_file("bar.pytd", """
          class Bar:
            def bar(self) -> int
      """)
      d.create_file("main.py", """
        from foo import x
        def f():
          return x.bar()
      """)
      ty = self.InferFromFile(filename=d["main.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x: bar.Bar
        def f() -> int
    """)

  def testRelativeName(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pytd", """x: int""")
      d.create_file("foo/bar.py", """
        import baz
        x = baz.x
      """)
      d.create_file("foo/__init__.pytd", "")
      ty = self.InferFromFile(filename=d["foo/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz: module
        x: int
    """)

  def testRelativeImport(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pytd", """x: int""")
      d.create_file("foo/bar.py", """
        from . import baz
        def f():
          return baz.x
      """)
      d.create_file("foo/__init__.pytd", "")
      ty = self.InferFromFile(filename=d["foo/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz: module
        def f() -> int
    """)

  def testDotPackage(self):
    # This tests up one level: note that the test file (foo.py)
    # is tested in the context of the up-level director "up1".
    with utils.Tempdir() as d:
      d.create_file("up1/foo.py", """
        from .bar import x
      """)
      d.create_file("up1/bar.pytd", """x: int""")
      d.create_file("up1/__init__.pytd", "")
      d.create_file("__init__.pytd", "")
      ty = self.InferFromFile(filename=d["up1/foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x: int
    """)

  def testDotDotPackage(self):
    # Similar to testDotPackage, except two levels
    with utils.Tempdir() as d:
      d.create_file("up2/baz/foo.py", """
        from ..bar import x
      """)
      d.create_file("up2/bar.pytd", """x: int""")
      d.create_file("__init__.pytd", "")
      d.create_file("up2/__init__.pytd", "")
      d.create_file("up2/baz/__init__.pytd", "")
      ty = self.InferFromFile(filename=d["up2/baz/foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x: int
      """)

  @unittest.skip("Only works if the isdir test is enabled in load_pytd")
  def testDotPackageNoInit(self):
    with utils.Tempdir() as d:
      d.create_file("foo.py", """
        from .bar import x
      """)
      d.create_file("bar.pytd", """x: int""")
      ty = self.InferFromFile(filename=d["foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x: int
      """)

  @unittest.skip("Only works if the isdir test is enabled in load_pytd")
  def testDotDotPackagNoInit(self):
    with utils.Tempdir() as d:
      d.create_file("baz/foo.py", """
        from ..bar import x
      """)
      d.create_file("bar.pytd", """x: int""")
      ty = self.InferFromFile(filename=d["baz/foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x: int
      """)

  def testDotDot(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pytd", """x: int""")
      d.create_file("foo/deep/bar.py", """
        from .. import baz
        def f():
          return baz.x
      """)
      d.create_file("foo/__init__.pytd", "")
      d.create_file("foo/deep/__init__.pytd", "")
      ty = self.InferFromFile(filename=d["foo/deep/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz: module
        def f() -> int
    """)

  def testFileImport1(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pytd",
                    "def foo(x:int) -> str")
      d.create_file("path/to/some/__init__.pytd", "")
      d.create_file("path/to/__init__.pytd", "")
      d.create_file("path/__init__.pytd", "")
      with self.Infer("""\
        import path.to.some.module
        def my_foo(x):
          return path.to.some.module.foo(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          path: module
          def my_foo(x:bool or int) -> str
        """)

  def testFileImport2(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pytd",
                    "def foo(x:int) -> str")
      d.create_file("path/to/some/__init__.pytd", "")
      d.create_file("path/to/__init__.pytd", "")
      d.create_file("path/__init__.pytd", "")
      with self.Infer("""\
        from path.to.some import module
        def my_foo(x):
          return module.foo(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          module: module
          def my_foo(x:bool or int) -> str
        """)

  def testSolveForImported(self):
    with self.Infer("""\
      import StringIO
      def my_foo(x):
        return x.read()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        StringIO: module
        def my_foo(x:file or StringIO.StringIO) -> str or bytes
      """)

  def testImportBuiltins(self):
    with self.Infer("""\
      import __builtin__ as builtins

      def f():
        return builtins.int()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        builtins: module

        def f() -> __builtin__.int
      """)

  def testImportedMethodAsClassAttribute(self):
    with self.Infer("""
      import os
      class Foo(object):
        killpg = os.killpg
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        os: module
        class Foo:
          killpg: function
      """)

  def testMatchAgainstImported(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pytd", """
        class Foo:
          pass
        class Bar:
          def f1(self, x: Foo) -> Baz
        class Baz:
          pass
      """)
      with self.Infer("""\
        import foo
        def f(x, y):
          return x.f1(y)
        def g(x):
          return x.f1(foo.Foo())
        class FooSub(foo.Foo):
          pass
        def h(x):
          return x.f1(FooSub())
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          foo: module
          def f(x:foo.Bar, y:foo.Foo) -> foo.Baz
          def g(x:foo.Bar) -> foo.Baz
          def h(x:foo.Bar) -> foo.Baz

          class FooSub(foo.Foo):
            pass
        """)

  def testImportedConstants(self):
    with utils.Tempdir() as d:
      d.create_file("module.pytd", """
        x: int
        class Foo:
          x: float
      """)
      with self.Infer("""\
        import module
        def f():
          return module.x
        def g():
          return module.Foo().x
        def h():
          return module.Foo.x
      """, deep=True, solve_unknowns=False, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          module: module
          def f() -> int
          def g() -> float
          def h() -> float
        """)

  def testCircular(self):
    with utils.Tempdir() as d:
      d.create_file("x.pytd", """
          class X:
            pass
          y: y.Y
          z: z.Z
      """)
      d.create_file("y.pytd", """
          class Y:
            pass
          x: x.X
      """)
      d.create_file("z.pytd", """
          class Z:
            pass
          x: x.X
      """)
      with self.Infer("""\
        import x
        xx = x.X()
        yy = x.y
        zz = x.z
      """, deep=True, solve_unknowns=False, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          x: module
          xx: x.X
          yy: y.Y
          zz: z.Z
        """)


if __name__ == "__main__":
  test_inference.main()
