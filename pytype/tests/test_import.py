"""Tests for import."""


from pytype import file_utils
from pytype import imports_map_loader
from pytype.tests import test_base


class ImportTest(test_base.TargetIndependentTest):
  """Tests for import."""

  def testBasicImport(self):
    ty = self.Infer("""\
      import sys
      """)
    self.assertTypesMatchPytd(ty, """
       sys = ...  # type: module
    """)

  def testBasicImport2(self):
    ty = self.Infer("""\
      import bad_import  # doesn't exist
      """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      bad_import = ...  # type: ?
    """)

  def testFromImportSmoke(self):
    self.assertNoCrash(self.Check, """\
      from sys import exit
      from path.to.module import bar, baz
      """)

  def testLongFrom(self):
    with file_utils.Tempdir() as d:
      d.create_file("path/to/my_module.pyi",
                    "def foo() -> str")
      ty = self.Infer("""\
      from path.to import my_module
      def foo():
        return my_module.foo()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        my_module = ...  # type: module
        def foo() -> str
      """)

  def testStarImportSmoke(self):
    self.Check("""\
      from sys import *
      """)

  def testStarImportUnknownSmoke(self):
    self.assertNoCrash(self.Check, """\
      from unknown_module import *
      """)

  def testStarImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("my_module.pyi", """
        def f() -> str
        class A(object):
          pass
        a = ...  # type: A
      """)
      ty = self.Infer("""\
      from my_module import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        A = ...  # type: Type[my_module.A]
        a = ...  # type: my_module.A
        def f() -> str
      """)

  def testStarImportAny(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      ty = self.Infer("""
        from a import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        def __getattr__(name) -> Any
      """)

  def testStarImportInPyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class X: ...
      """)
      d.create_file("b.pyi", """
        from a import *
        class Y(X): ...
      """)
      ty = self.Infer("""\
      from b import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        import b
        from typing import Type
        X = ...  # type: Type[a.X]
        Y = ...  # type: Type[b.Y]
      """)

  def testBadStarImport(self):
    ty, errors = self.InferWithErrors("""
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
    with file_utils.Tempdir() as d:
      d.create_file("path/to/my_module.pyi",
                    "def qqsv() -> str")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
      import path.to.my_module
      def foo():
        return path.to.my_module.qqsv()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        path = ...  # type: module
        def foo() -> str
      """)

  def testPathImport2(self):
    with file_utils.Tempdir() as d:
      d.create_file("path/to/my_module.pyi",
                    "def qqsv() -> str")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
      import nonexistant_path.to.my_module  # doesn't exist
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, report_errors=False,
                      pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        nonexistant_path = ...  # type: ?
        def foo() -> ?
      """)

  def testImportAll(self):
    self.assertNoCrash(self.Check, """\
      from module import *
      from path.to.module import *
      """)

  def testAssignMember(self):
    self.Check("""\
      import sys
      sys.path = []
      """)

  def testReturnModule(self):
    ty = self.Infer("""
        import sys

        def f():
          return sys
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def f() -> module
    """)

  def testMatchModule(self):
    ty = self.Infer("""
      import sys
      def f():
        if getattr(sys, "foobar"):
          return list({sys: sys}.keys())[0]
        else:
          return sys
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def f() -> module
    """)

  def testSys(self):
    ty = self.Infer("""
      import sys
      def f():
        return sys.path
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      sys = ...  # type: module
      def f() -> List[str, ...]
    """)

  def testFromSysImport(self):
    ty = self.Infer("""
      from sys import path
      def f():
        return path
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      path = ...  # type: List[str, ...]
      def f() -> List[str, ...]
    """)

  def testStdlib(self):
    ty = self.Infer("""
      import datetime
      def f():
        return datetime.timedelta().total_seconds()
    """)
    self.assertTypesMatchPytd(ty, """
      datetime = ...  # type: module
      def f() -> float
    """)

  def testImportPytd(self):
    with file_utils.Tempdir() as d:
      d.create_file("other_file.pyi", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from other_file import f
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int
      """)

  def testImportPytd2(self):
    with file_utils.Tempdir() as d:
      d.create_file("other_file.pyi", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from other_file import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int
        def g() -> int
      """)

  def testImportDirectory(self):
    with file_utils.Tempdir() as d:
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
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        other_file = ...  # type: module
        sub = ...  # type: module  # from 'import sub.bar.baz'
        def g() -> float
        def h() -> int
        def i() -> float
        def j() -> float
      """)

  def testImportInit(self):
    with file_utils.Tempdir() as d:
      d.create_file("sub/__init__.pyi", """
        def f() -> int
      """)
      d.create_file("main.py", """
        from sub import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int
        def g() -> int
      """)

  def testImportName(self):
    with file_utils.Tempdir() as d:
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
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> foo.A
        def g() -> foo.A
    """)

  def testDeepDependency(self):
    with file_utils.Tempdir() as d:
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
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: bar.Bar
        def f() -> int
    """)

  def testRelativeImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", """x = ...  # type: int""")
      d.create_file("foo/bar.py", """
        from . import baz
        def f():
          return baz.x
      """)
      d.create_file("foo/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["foo/bar.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        baz = ...  # type: module
        def f() -> int
    """)

  def testDotPackage(self):
    # This tests up one level: note that the test file (foo.py)
    # is tested in the context of the up-level director "up1".
    with file_utils.Tempdir() as d:
      d.create_file("up1/foo.py", """
        from .bar import x
      """)
      d.create_file("up1/bar.pyi", """x = ...  # type: int""")
      d.create_file("up1/__init__.pyi", "")
      d.create_file("__init__.pyi", "")
      ty = self.InferFromFile(filename=d["up1/foo.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
    """)

  def testDotDotPackage(self):
    # Similar to testDotPackage, except two levels
    with file_utils.Tempdir() as d:
      d.create_file("up2/baz/foo.py", """
        from ..bar import x
      """)
      d.create_file("up2/bar.pyi", """x = ...  # type: int""")
      d.create_file("__init__.pyi", "")
      d.create_file("up2/__init__.pyi", "")
      d.create_file("up2/baz/__init__.pyi", "")
      ty = self.InferFromFile(filename=d["up2/baz/foo.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def testDotPackageNoInit(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.py", """
        from .bar import x
      """)
      d.create_file("bar.pyi", """x = ...  # type: int""")
      ty = self.InferFromFile(filename=d["foo.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def testDotDotPackagNoInit(self):
    with file_utils.Tempdir() as d:
      d.create_file("baz/foo.py", """
        from ..bar import x
      """)
      d.create_file("bar.pyi", """x = ...  # type: int""")
      ty = self.InferFromFile(filename=d["baz/foo.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def testDotDot(self):
    with file_utils.Tempdir() as d:
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

  def testDotDotPackageInPyi(self):
    # Similar to testDotDotPackage, except for a pyi file.
    with file_utils.Tempdir() as d:
      d.create_file("up2/baz/foo.pyi", """
        from ..bar import X
      """)
      d.create_file("up2/bar.pyi", "class X: ...")
      d.create_file("top.py", """\
                    from up2.baz.foo import X
                    x = X()
                    """)
      ty = self.InferFromFile(filename=d["top.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import up2.bar
        X = ...  # type: Type[up2.bar.X]
        x = ...  # type: up2.bar.X
      """)

  def testDotDotInPyi(self):
    # Similar to testDotDot except in a pyi file.
    with file_utils.Tempdir() as d:
      d.create_file("foo/baz.pyi", "x: int")
      d.create_file("foo/deep/bar.py", """\
        from .. import baz
        a = baz.x
      """)
      ty = self.InferFromFile(filename=d["foo/deep/bar.py"],
                              pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """\
        baz = ...  # type: module
        a: int
      """)

  def testTooManyDotsInPackageInPyi(self):
    # Trying to go up more directories than the package path contains
    with file_utils.Tempdir() as d:
      d.create_file("up/foo.pyi", "from ..bar import X")
      d.create_file("up/bar.pyi", "class X: ...")
      _, err = self.InferWithErrors(
          "from up.foo import X", pythonpath=[d.path])
      self.assertErrorLogIs(
          err, [(1, "pyi-error", "Cannot resolve relative import ..bar")])

  def testFromDotInPyi(self):
    # from . import module
    with file_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", "class X: ...")
      d.create_file("foo/b.pyi", """\
        from . import a
        Y = a.X""")
      d.create_file("top.py", """\
        import foo.b
        x = foo.b.Y() """)
      ty = self.InferFromFile(filename=d["top.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo.a
        foo = ...  # type: module
        x = ...  # type: foo.a.X
      """)

  def testUnusedFromDotInPyi(self):
    # A `from . import module` that does not subsequently use the module should
    # not raise an unreplaced NamedType error.
    with file_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", "class X: ...")
      d.create_file("foo/b.pyi", "from . import a")
      self.Check("import foo.b", pythonpath=[d.path])

  def testFileImport1(self):
    with file_utils.Tempdir() as d:
      d.create_file("path/to/some/module.pyi",
                    "def foo(x:int) -> str")
      d.create_file("path/to/some/__init__.pyi", "")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
        import path.to.some.module
        def my_foo(x):
          return path.to.some.module.foo(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        path = ...  # type: module
        def my_foo(x) -> str
      """)

  def testFileImport2(self):
    with file_utils.Tempdir() as d:
      d.create_file("path/to/some/module.pyi",
                    "def foo(x:int) -> str")
      d.create_file("path/to/some/__init__.pyi", "")
      d.create_file("path/to/__init__.pyi", "")
      d.create_file("path/__init__.pyi", "")
      ty = self.Infer("""\
        from path.to.some import module
        def my_foo(x):
          return module.foo(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        module = ...  # type: __builtin__.module
        def my_foo(x) -> str
      """)

  @test_base.skip("flaky")
  def testSolveForImported(self):
    ty = self.Infer("""\
      import StringIO
      def my_foo(x):
        return x.read()
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      builtins = ...  # type: module

      def f() -> int
    """)

  def testImportedMethodAsClassAttribute(self):
    ty = self.Infer("""
      import os
      class Foo(object):
        killpg = os.killpg
    """)
    self.assertTypesMatchPytd(ty, """
      os = ...  # type: module
      class Foo(object):
        def killpg(pgid: int, sig: int) -> None
    """)

  def testMatchAgainstImported(self):
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x, y) -> Any
        def g(x) -> Any
        def h(x) -> Any

        class FooSub(foo.Foo):
          pass
      """)

  def testImportedConstants(self):
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        module = ...  # type: __builtin__.module
        def f() -> int
        def g() -> float
        def h() -> float
      """)

  def testCircular(self):
    with file_utils.Tempdir() as d:
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: module
        xx = ...  # type: x.X
        yy = ...  # type: y.Y
        zz = ...  # type: z.Z
      """)

  def testReimport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
          from collections import OrderedDict as MyOrderedDict
      """)
      ty = self.Infer("""\
        import foo
        d = foo.MyOrderedDict()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        d = ...  # type: collections.OrderedDict[nothing, nothing]
      """)

  def testImportFunction(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
          from math import pow as mypow
      """)
      ty = self.Infer("""\
        import foo
        d = foo.mypow
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        from typing import SupportsFloat
        foo = ...  # type: module
        def d(x: SupportsFloat, y: SupportsFloat) -> float
      """)

  def testImportConstant(self):
    with file_utils.Tempdir() as d:
      d.create_file("mymath.pyi", """
          from math import pi as half_tau
      """)
      ty = self.Infer("""\
        import mymath
        from mymath import half_tau as x
        y = mymath.half_tau
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        mymath = ...  # type: module
        x = ...  # type: float
        y = ...  # type: float
      """)

  def testImportMap(self):
    with file_utils.Tempdir() as d:
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
      """, deep=False, imports_map=imports_map,
                      pythonpath=[""])
      self.assertTypesMatchPytd(ty, """
        bar = ...  # type: int
      """)

  def testImportResolveOnDummy(self):
    with file_utils.Tempdir() as d:
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
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        b = ...  # type: module
        foo = ...  # type: Any
        bar = ...  # type: Any
      """)

  def testTwoLevel(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        +++ /&* unparseable *&/ +++
      """)
      d.create_file("b.pyi", """
        import a
        class B(a.A):
          pass
      """)
      _, errors = self.InferWithErrors("""\
        import b
        x = b.B()
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [(1, "pyi-error", r"a\.pyi")])

  def testSubdirAndModuleWithSameNameAsPackage(self):
    with file_utils.Tempdir() as d:
      d.create_file("pkg/__init__.pyi", """
          from pkg.pkg.pkg import *
          from pkg.bar import *""")
      d.create_file("pkg/pkg/pkg.pyi", """
          class X: pass""")
      d.create_file("pkg/bar.pyi", """
          class Y: pass""")
      ty = self.Infer("""
        import pkg
        a = pkg.X()
        b = pkg.Y()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: pkg.pkg.pkg.X
        b = ...  # type: pkg.bar.Y
        pkg = ...  # type: module
      """)

  def testRedefinedBuiltin(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        object = ...  # type: Any
        def f(x) -> Any
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f("")
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        x = ...  # type: Any
      """)

  def testRedefinedBuiltin2(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class object:
          def foo(self) -> None: ...
        def f(x: object) -> object
      """)
      ty, errors = self.InferWithErrors("""\
        import foo
        x = foo.f(foo.object())
        y = foo.f(foo.object())
        foo.f(object())  # error
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: foo.object
        y = ...  # type: foo.object
      """)
      self.assertErrorLogIs(errors, [
          (4, "wrong-arg-types"),
      ])

  def testNoFailOnBadSymbolLookup(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: FooBar) -> FooBar
      """)
      self.assertNoCrash(self.Check, """\
        import foo
      """, pythonpath=[d.path])

  @test_base.skip("instantiating 'type' should use 'Type[Any]', not 'Any'")
  def testImportTypeFactory(self):
    with file_utils.Tempdir() as d:
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

  def testGetBadSubmoduleAsAttribute(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/__init__.pyi", "")
      d.create_file("foo/bar.pyi", "nonsense")
      self.assertNoCrash(self.Check, """
        import foo
        x = foo.bar
      """, pythonpath=[d.path])

  def testIgnoredImport(self):
    ty = self.Infer("""\
      import sys  # type: ignore
      import foobar  # type: ignore
      from os import path  # type: ignore
      a = sys.rumplestiltskin
      b = sys.stderr
      c = foobar.rumplestiltskin
      d = path.curdir
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      sys = ...  # type: Any
      foobar = ...  # type: Any
      path = ...  # type: Any
      a = ...  # type: Any
      b = ...  # type: Any
      c = ...  # type: Any
      d = ...  # type: Any
    """)

  def testAttributeOnModule(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        foo = ...  # type: int
      """)
      _, errors = self.InferWithErrors("""\
        from a import foo, bar
        import a
        a.baz
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [
        (1, "import-error", r"bar"),
        (3, "module-attr", r"baz"),
    ])

  def testFromImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/b.pyi", """
        from foo import c
        class bar(c.X): ...
      """)
      d.create_file("foo/c.pyi", """
        class X(object): ...
      """)
      self.Check("""\
        from foo import b
        class Foo(b.bar):
          pass
      """, pythonpath=[d.path])

  def testImportMapFilter(self):
    with file_utils.Tempdir() as d:
      imp_path = ".".join(d.path[1:].split("/"))
      init_body = """\
        from {0}.foo import bar
        from {0}.foo import baz
        Qux = bar.Quack
        """.format(imp_path)
      init_fn = d.create_file("foo/__init__.py", init_body)
      initpyi_fn = d.create_file("foo/__init__.pyi~", """\
        from typing import Any
        bar = ...  # type: Any
        baz = ...  # type: Any
        Qux = ...  # type: Any
        """)
      bar_fn = d.create_file("foo/bar.py", "class Quack(object): pass")
      barpyi_fn = d.create_file("foo/bar.pyi", "class Quack(object): pass")
      imports_fn = d.create_file("imports_info", """\
        {0} {1}
        {2} {3}
        """.format(init_fn[1:-3], initpyi_fn, bar_fn[1:-3], barpyi_fn))
      imports_map = imports_map_loader.build_imports_map(imports_fn, init_fn)
      ty = self.Infer("""\
        from {0}.foo import bar
        Adz = bar.Quack
        """.format(imp_path),
                      deep=False, imports_map=imports_map, pythonpath=[""])
      self.assertTypesMatchPytd(ty, """\
        from typing import Any, Type
        bar = ...  # type: module
        Adz = ...  # type: Type[{0}.foo.bar.Quack]
        """.format(imp_path))

  def testMutualImports(self):
    with file_utils.Tempdir() as d:
      d.create_file("pkg/a.pyi", """
        from typing import TypeVar, Generic, List
        from .b import Foo
        T = TypeVar('T')
        class Bar(Foo, List[T], Generic[T]): ...
        class Baz(List[T], Generic[T]): ...
      """)
      d.create_file("pkg/b.pyi", """
        from typing import TypeVar, Generic
        from .a import Baz
        T = TypeVar('T')
        class Foo(): ...
        class Quux(Baz[T], Generic[T]): ...
      """)
      ty = self.Infer("""from pkg.a import *""", pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """\
        import pkg.a
        import pkg.b
        from typing import Type, TypeVar
        Bar = ...  # type: Type[pkg.a.Bar]
        Baz = ...  # type: Type[pkg.a.Baz]
        Foo = ...  # type: Type[pkg.b.Foo]
        T = TypeVar('T')
      """)

  def testModuleReexportsAndAliases(self):
    with file_utils.Tempdir() as d:
      d.create_file("pkg/a.pyi", """
        from pkg import b as c
        from pkg.b import e as f
        import pkg.d as x
        import pkg.g  # should not cause unused import errors
      """)
      d.create_file("pkg/b.pyi", """
        class X: ...
        class e: ...
      """)
      d.create_file("pkg/d.pyi", """
        class Y: ...
      """)
      d.create_file("pkg/g.pyi", """
        class Z: ...
      """)
      ty = self.Infer("""\
        import pkg.a
        s = pkg.a.c.X()
        t = pkg.a.f()
        u = pkg.a.x
        v = u.Y()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """\
        import pkg.b
        import pkg.d
        import pkg.g
        pkg = ...  # type: module
        s = ...  # type: pkg.b.X
        t = ...  # type: pkg.b.e
        u = ...  # type: module
        v = ...  # type: pkg.d.Y
      """)

  def testImportPackageAsAlias(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", "class A: ...")
      d.create_file("b.pyi", """
        import a as _a
        f: _a.A
      """)
      self.Check("""
        import b
        c = b.f
      """, pythonpath=[d.path])

  def testImportPackageAliasNameConflict(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", "A: str")
      d.create_file("b.pyi", """
        import a as _a
        class a:
          A: int
        x = _a.A
        y = a.A
      """)
      ty = self.Infer("""
        import b
        x = b.x
        y = b.y
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        b: module
        x: str
        y: int
      """)

  def testImportPackageAliasNameConflict2(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", "A: str")
      d.create_file("b.pyi", "A: int")
      d.create_file("c.pyi", """
        import a as _a
        import b as a
        x = _a.A
        y = a.A
      """)
      ty = self.Infer("""
        import c
        x = c.x
        y = c.y
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        c: module
        x: str
        y: int
      """)

  def testImportPackageAliasNameConflict3(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", "A: str")
      d.create_file("b.pyi", "A: int")
      d.create_file("c.pyi", """
        import b as a
        import a as _a
        x = _a.A
        y = a.A
      """)
      ty = self.Infer("""
        import c
        x = c.x
        y = c.y
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        c: module
        x: str
        y: int
      """)

  def testModuleClassConflict(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar.pyi", "def __getattr__(name) -> ?")
      ty = self.Infer("""
        from foo import bar
        class foo(object):
          def __new__(cls):
            return object.__new__(cls)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type, TypeVar
        bar = ...  # type: module
        _Tfoo = TypeVar("_Tfoo", bound=foo)
        class foo(object):
          def __new__(cls: Type[_Tfoo]) -> _Tfoo
      """)

  def testClassAlias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar.pyi", "def __getattr__(name) -> ?")
      ty = self.Infer("""
        from foo import bar
        class foo(object):
          pass
        baz = foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        bar = ...  # type: module
        class foo(object): ...
        baz = foo
      """)

  def testRelativeStarImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar.pyi", "from .baz.qux import *")
      d.create_file("foo/baz/qux.pyi", "v = ...  # type: int")
      ty = self.Infer("""
        from foo.bar import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        v = ...  # type: int
      """)

  def testRelativeStarImport2(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar/baz.pyi", "from ..bar.qux import *")
      d.create_file("foo/bar/qux.pyi", "v = ...  # type: int")
      ty = self.Infer("""
        from foo.bar.baz import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        v = ...  # type: int
      """)

  def testUnimportedSubmoduleFailure(self):
    """Fail when accessing a submodule we haven't imported."""
    with file_utils.Tempdir() as d:
      d.create_file("sub/bar/baz.pyi", "class A: ...")
      d.create_file("sub/bar/quux.pyi", "class B: ...")
      d.create_file("sub/__init__.pyi", "")
      d.create_file("sub/bar/__init__.pyi", "")
      _, errors = self.InferWithErrors("""\
        import sub.bar.baz
        x = sub.bar.baz.A()
        y = sub.bar.quux.B()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "module-attr", r"quux.*sub\.bar")])


test_base.main(globals(), __name__ == "__main__")
