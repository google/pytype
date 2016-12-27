"""Tests for import."""

import unittest


from pytype import imports_map_loader
from pytype import utils
from pytype.tests import test_inference


class ImportTest(test_inference.InferenceTest):
  """Tests for import."""

  def testBasicImport(self):
    ty = self.Infer("""\
      import sys
      """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
       sys = ...  # type: module
    """)

  def testBasicImport2(self):
    ty = self.Infer("""\
      import bad_import  # doesn't exist
      """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      bad_import = ...  # type: ?
    """)

  def testFromImportSmoke(self):
    self.assertNoCrash("""\
      from sys import exit
      from path.to.module import bar, baz
      """)

  def testLongFrom(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pyi",
                    "def foo() -> str")
      ty = self.Infer("""\
      from path.to import my_module
      def foo():
        return my_module.foo()
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        my_module = ...  # type: module
        def foo() -> str
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
      d.create_file("my_module.pyi", """
        def f() -> str
        class A(object):
          pass
        a = ...  # type: A
      """)
      ty = self.Infer("""\
      from my_module import *
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        A = ...  # type: Type[my_module.A]
        a = ...  # type: my_module.A
        def f() -> str
      """)

  def testStarImportAny(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      ty = self.Infer("""
        from a import *
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        def __getattr__(name) -> Any
      """)

  def testBadStarImport(self):
    ty, errors = self.InferAndCheck("""
      from nonsense import *
      from other_nonsense import *
      x = foo.bar()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def __getattr__(name) -> Any
      x = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(2, "import-error", r"nonsense"),
                                   (3, "import-error", r"other_nonsense")])

  def testPathImport(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pyi",
                    "def qqsv() -> str")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
      import path.to.my_module
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        path = ...  # type: module
        def foo() -> str
      """)

  def testPathImport2(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/my_module.pyi",
                    "def qqsv() -> str")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
      import nonexistant_path.to.my_module  # doesn't exist
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, solve_unknowns=True, report_errors=False,
                      pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        nonexistant_path = ...  # type: ?
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
    ty = self.Infer("""
        import sys

        def f():
          return sys
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def f() -> module
    """)

  def testMatchModule(self):
    ty = self.Infer("""
      import sys
      def f():
        if getattr(sys, "foobar"):
          return {sys: sys}.keys()[0]
        else:
          return sys
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def f() -> module
    """)

  def testSys(self):
    ty = self.Infer("""
      import sys
      def f():
        return sys.path
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def f() -> List[str, ...]
    """)

  def testFromSysImport(self):
    ty = self.Infer("""
      from sys import path
      def f():
        return path
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      path = ...  # type: List[str, ...]
      def f() -> List[str, ...]
    """)

  def testImportSys2(self):
    ty = self.Infer("""
      import sys
      import bad_import  # doesn't exist
      def f():
        return sys.stderr
      def g():
        return sys.maxint
      def h():
        return sys.getrecursionlimit()
    """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      bad_import = ...  # type: ?
      sys = ...  # type: module
      def f() -> file
      def g() -> int
      def h() -> int
    """)

  def testStdlib(self):
    ty = self.Infer("""
      import StringIO
      def f():
        return StringIO.StringIO().isatty()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      StringIO = ...  # type: module
      def f() -> bool
    """)

  def testImportPytd(self):
    with utils.Tempdir() as d:
      d.create_file("other_file.pyi", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from other_file import f
      """)
      ty = self.InferFromFile(
          filename=d["main.py"],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int
      """)

  def testImportPytd2(self):
    with utils.Tempdir() as d:
      d.create_file("other_file.pyi", """
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
        def f() -> int
        def g() -> int
      """)

  def testImportDirectory(self):
    with utils.Tempdir() as d:
      d.create_file("sub/other_file.pyi", "def f() -> int")
      d.create_file("sub/bar/baz.pyi", "def g() -> float")
      d.create_file("sub/__init__.pyi", "")
      d.create_file("sub/bar/__init__.pyi", "")
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
        other_file = ...  # type: module
        sub = ...  # type: module  # from 'import sub.bar.baz'
        def g() -> float
        def h() -> int
        def i() -> float
        def j() -> float
      """)

  def testImportInit(self):
    with utils.Tempdir() as d:
      d.create_file("sub/__init__.pyi", """
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
        def f() -> int
        def g() -> int
      """)

  def testImportName(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
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
        def f() -> foo.A
        def g() -> foo.A
    """)

  def testDeepDependency(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "x = ...  # type: bar.Bar")
      d.create_file("bar.pyi", """
          class Bar(object):
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
        x = ...  # type: bar.Bar
        def f() -> int
    """)

  def testRelativeName(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      d.create_file("foo/bar.py", """
        import baz
        x = baz.x
      """)
      d.create_file("foo/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["foo/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        x = ...  # type: int
    """)

  def testRelativeImport(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      d.create_file("foo/bar.py", """
        from . import baz
        def f():
          return baz.x
      """)
      d.create_file("foo/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["foo/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        def f() -> int
    """)

  def testModuleName(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      bar = """
        import baz
        x = baz.x
      """
      d.create_file("foo/bar.py", bar)
      ty = self.Infer(bar,
                      module_name="foo.bar",
                      pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        x = ...  # type: int
    """)

  def testDotPackage(self):
    # This tests up one level: note that the test file (foo.py)
    # is tested in the context of the up-level director "up1".
    with utils.Tempdir() as d:
      d.create_file("up1/foo.py", """
        from .bar import x
      """)
      d.create_file("up1/bar.pyi", """x = ...  # type: int""")
      d.create_file("up1/__init__.pyi", "")
      d.create_file("__init__.pyi", "")
      ty = self.InferFromFile(filename=d["up1/foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
    """)

  def testDotDotPackage(self):
    # Similar to testDotPackage, except two levels
    with utils.Tempdir() as d:
      d.create_file("up2/baz/foo.py", """
        from ..bar import x
      """)
      d.create_file("up2/bar.pyi", """x = ...  # type: int""")
      d.create_file("__init__.pyi", "")
      d.create_file("up2/__init__.pyi", "")
      d.create_file("up2/baz/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["up2/baz/foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def testDotPackageNoInit(self):
    with utils.Tempdir() as d:
      d.create_file("foo.py", """
        from .bar import x
      """)
      d.create_file("bar.pyi", """x = ...  # type: int""")
      ty = self.InferFromFile(filename=d["foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def testDotDotPackagNoInit(self):
    with utils.Tempdir() as d:
      d.create_file("baz/foo.py", """
        from ..bar import x
      """)
      d.create_file("bar.pyi", """x = ...  # type: int""")
      ty = self.InferFromFile(filename=d["baz/foo.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def testDotDot(self):
    with utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      d.create_file("foo/deep/bar.py", """
        from .. import baz
        def f():
          return baz.x
      """)
      d.create_file("foo/__init__.pyi", "")
      d.create_file("foo/deep/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["foo/deep/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        def f() -> int
    """)

  def testFileImport1(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pyi",
                    "def foo(x:int) -> str")
      d.create_file("path/to/some/__init__.pyi", "")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
        import path.to.some.module
        def my_foo(x):
          return path.to.some.module.foo(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        path = ...  # type: module
        def my_foo(x:int) -> str
      """)

  def testFileImport2(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pyi",
                    "def foo(x:int) -> str")
      d.create_file("path/to/some/__init__.pyi", "")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
        from path.to.some import module
        def my_foo(x):
          return module.foo(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        module = ...  # type: __builtin__.module
        def my_foo(x:int) -> str
      """)

  @unittest.skip("flaky")
  def testSolveForImported(self):
    ty = self.Infer("""\
      import StringIO
      def my_foo(x):
        return x.read()
    """, deep=True, solve_unknowns=True)
    # TODO(kramm): Instead of typing.IO[object] we should have typing.IO[AnyStr]
    # (or typing.IO[str or unicode]). The return type should be str or unicode.
    # Also, the optimizer should be smart enough to collapse the Union into just
    # typing.IO[AnyStr].
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      StringIO = ...  # type: module
      def my_foo(x:StringIO.StringIO[object] or typing.IO[object] or
                   typing.BinaryIO or typing.TextIO) -> Any
    """)

  def testImportBuiltins(self):
    ty = self.Infer("""\
      import __builtin__ as builtins

      def f():
        return builtins.int()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      builtins = ...  # type: module

      def f() -> int
    """)

  def testImportedMethodAsClassAttribute(self):
    ty = self.Infer("""
      import os
      class Foo(object):
        killpg = os.killpg
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      os = ...  # type: module
      class Foo(object):
        def killpg(pgid: int, sig: int) -> None
    """)

  def testMatchAgainstImported(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          pass
        class Bar(object):
          def f1(self, x: Foo) -> Baz
        class Baz(object):
          pass
      """)
      ty = self.Infer("""\
        import foo
        def f(x, y):
          return x.f1(y)
        def g(x):
          return x.f1(foo.Foo())
        class FooSub(foo.Foo):
          pass
        def h(x):
          return x.f1(FooSub())
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f(x:foo.Bar, y:foo.Foo) -> foo.Baz
        def g(x:foo.Bar) -> foo.Baz
        def h(x:foo.Bar) -> foo.Baz

        class FooSub(foo.Foo):
          pass
      """)

  def testImportedConstants(self):
    with utils.Tempdir() as d:
      d.create_file("module.pyi", """
        x = ...  # type: int
        class Foo(object):
          x = ...  # type: float
      """)
      ty = self.Infer("""\
        import module
        def f():
          return module.x
        def g():
          return module.Foo().x
        def h():
          return module.Foo.x
      """, deep=True, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        module = ...  # type: __builtin__.module
        def f() -> int
        def g() -> float
        def h() -> float
      """)

  def testCircular(self):
    with utils.Tempdir() as d:
      d.create_file("x.pyi", """
          class X(object):
            pass
          y = ...  # type: y.Y
          z = ...  # type: z.Z
      """)
      d.create_file("y.pyi", """
          class Y(object):
            pass
          x = ...  # type: x.X
      """)
      d.create_file("z.pyi", """
          class Z(object):
            pass
          x = ...  # type: x.X
      """)
      ty = self.Infer("""\
        import x
        xx = x.X()
        yy = x.y
        zz = x.z
      """, deep=True, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: module
        xx = ...  # type: x.X
        yy = ...  # type: y.Y
        zz = ...  # type: z.Z
      """)

  def testModuleAttributes(self):
    ty = self.Infer("""\
      import os
      f = os.__file__
      n = os.__name__
      d = os.__doc__
      p = os.__package__
      """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
       os = ...  # type: module
       f = ...  # type: str
       n = ...  # type: str
       d = ...  # type: str or unicode
       p = ...  # type: Optional[str]
    """)

  def testReimport(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
          from collections import OrderedDict as MyOrderedDict
      """)
      ty = self.Infer("""\
        import foo
        d = foo.MyOrderedDict()
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        d = ...  # type: collections.OrderedDict[nothing, nothing]
      """)

  def testImportFunction(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
          from math import pow as mypow
      """)
      ty = self.Infer("""\
        import foo
        d = foo.mypow
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def d(x: Union[float, int]) -> float
      """)

  def testImportConstant(self):
    with utils.Tempdir() as d:
      d.create_file("mymath.pyi", """
          from math import pi as half_tau
      """)
      ty = self.Infer("""\
        import mymath
        from mymath import half_tau as x
        y = mymath.half_tau
      """, deep=False, solve_unknowns=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mymath = ...  # type: module
        x = ...  # type: float
        y = ...  # type: float
      """)

  def testImportMap(self):
    with utils.Tempdir() as d:
      foo_filename = d.create_file("foo.pyi", """
          bar = ...  # type: int
      """)
      imports_map_filename = d.create_file("imports_map.txt", """
          foo %s
      """ % foo_filename)
      imports_map = imports_map_loader.build_imports_map(
          imports_map_filename)
      ty = self.Infer("""\
        from foo import bar
      """, deep=False, solve_unknowns=False, imports_map=imports_map,
                      pythonpath=[""])
      self.assertTypesMatchPytd(ty, """
        bar = ...  # type: int
      """)

  def testImportResolveOnDummy(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
          from typing import Any
          def __getattr__(name) -> Any: ...
      """)
      d.create_file("b.pyi", """
          from a import Foo
          def f(x: Foo) -> Foo: ...
      """)
      ty = self.Infer("""\
        import b
        foo = b.Foo()
        bar = b.f(foo)
      """, deep=False, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        b = ...  # type: module
        foo = ...  # type: Any
        bar = ...  # type: Any
      """)

  def testTwoLevel(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        +++ /&* unparseable *&/ +++
      """)
      d.create_file("b.pyi", """
        import a
        class B(a.A):
          pass
      """)
      _, errors = self.InferAndCheck("""\
        import b
        x = b.B()
      """, pythonpath=[d.path])
    self.assertErrorLogContains(errors, "a.pyi")

  def testRelativePriority(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", "x = ...  # type: int")
      d.create_file("b/a.pyi", "x = ...  # type: complex")
      ty = self.Infer("""\
        import a
        x = a.x
      """, pythonpath=[d.path], module_name="b.main")
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: complex
      """)

  def testRedefinedBuiltin(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        object = ...  # type: Any
        def f(x) -> Any
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f("")
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        x = ...  # type: Any
      """)

  def testRedefinedBuiltin2(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class object:
          def foo(self) -> None: ...
        def f(x: object) -> object
        def f(x) -> object  # same as above (abbreviated form)
      """)
      ty, errors = self.InferAndCheck("""\
        import foo
        x = foo.f(foo.object())
        y = foo.f(foo.object())
        foo.f(object())  # error
        foo.f(object())  # error
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: foo.object
        y = ...  # type: foo.object
      """)
      self.assertErrorLogIs(errors, [
          (4, "wrong-arg-types"),
          (5, "wrong-arg-types")
      ])

  def testNoFailOnBadSymbolLookup(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: FooBar) -> FooBar
      """)
      self.assertNoCrash("""\
        import foo
      """, pythonpath=[d.path])

  @unittest.skip("instantiating 'type' should use 'Type[Any]', not 'Any'")
  def testImportTypeFactory(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def factory() -> type
      """)
      ty = self.Infer("""\
        import a
        A = a.factory()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        A = ...  # type: type
      """)


if __name__ == "__main__":
  test_inference.main()
