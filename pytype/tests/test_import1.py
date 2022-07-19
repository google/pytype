"""Tests for import."""

from pytype import file_utils
from pytype import imports_map_loader
from pytype.pytd import pytd_utils
from pytype.tests import test_base


DEFAULT_PYI = """
from typing import Any
def __getattr__(name) -> Any: ...
"""


class ImportTest(test_base.BaseTest):
  """Tests for import."""

  def test_basic_import(self):
    ty = self.Infer("""
      import sys
      """)
    self.assertTypesMatchPytd(ty, """
       import sys
    """)

  def test_basic_import2(self):
    ty = self.Infer("""
      import bad_import  # doesn't exist
      """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      bad_import = ...  # type: Any
    """)

  def test_from_import_smoke(self):
    self.assertNoCrash(self.Check, """
      from sys import exit
      from path.to.module import bar, baz
      """)

  def test_long_from(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("path/to/my_module.pyi"),
          "def foo() -> str: ...")
      ty = self.Infer("""
      from path.to import my_module
      def foo():
        return my_module.foo()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from path.to import my_module
        def foo() -> str: ...
      """)

  def test_star_import_smoke(self):
    self.Check("""
      from sys import *
      """)

  def test_star_import_unknown_smoke(self):
    self.assertNoCrash(self.Check, """
      from unknown_module import *
      """)

  def test_star_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("my_module.pyi", """
        def f() -> str: ...
        class A:
          pass
        a = ...  # type: A
      """)
      ty = self.Infer("""
      from my_module import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        A = ...  # type: Type[my_module.A]
        a = ...  # type: my_module.A
        def f() -> str: ...
      """)

  def test_star_import_any(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", DEFAULT_PYI)
      ty = self.Infer("""
        from a import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        def __getattr__(name) -> Any: ...
      """)

  def test_star_import_in_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class X: ...
      """)
      d.create_file("b.pyi", """
        from a import *
        class Y(X): ...
      """)
      ty = self.Infer("""
      from b import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        import b
        from typing import Type
        X = ...  # type: Type[a.X]
        Y = ...  # type: Type[b.Y]
      """)

  def test_bad_star_import(self):
    ty, _ = self.InferWithErrors("""
      from nonsense import *  # import-error
      from other_nonsense import *  # import-error
      x = foo.bar()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def __getattr__(name) -> Any: ...
      x = ...  # type: Any
    """)

  def test_path_import(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("path/to/my_module.pyi"),
          "def qqsv() -> str: ...")
      d.create_file(file_utils.replace_separator("path/to/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("path/__init__.pyi"), "")
      ty = self.Infer("""
      import path.to.my_module
      def foo():
        return path.to.my_module.qqsv()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import path
        def foo() -> str: ...
      """)

  def test_path_import2(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("path/to/my_module.pyi"),
          "def qqsv() -> str: ...")
      d.create_file(file_utils.replace_separator("path/to/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("path/__init__.pyi"), "")
      ty = self.Infer("""
      import nonexistant_path.to.my_module  # doesn't exist
      def foo():
        return path.to.my_module.qqsv()
      """, deep=True, report_errors=False,
                      pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        nonexistant_path = ...  # type: Any
        def foo() -> Any: ...
      """)

  def test_import_all(self):
    self.assertNoCrash(self.Check, """
      from module import *
      from path.to.module import *
      """)

  def test_assign_member(self):
    self.Check("""
      import sys
      sys.path = []
      """)

  def test_return_module(self):
    ty = self.Infer("""
        import sys

        def f():
          return sys
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      def f() -> module: ...
    """)

  def test_match_module(self):
    ty = self.Infer("""
      import sys
      def f():
        if getattr(sys, "foobar"):
          return list({sys: sys}.keys())[0]
        else:
          return sys
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      def f() -> module: ...
    """)

  def test_sys(self):
    ty = self.Infer("""
      import sys
      def f():
        return sys.path
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import sys
      def f() -> List[str, ...]: ...
    """)

  def test_from_sys_import(self):
    ty = self.Infer("""
      from sys import path
      def f():
        return path
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      path = ...  # type: List[str, ...]
      def f() -> List[str, ...]: ...
    """)

  def test_stdlib(self):
    ty = self.Infer("""
      import datetime
      def f():
        return datetime.timedelta().total_seconds()
    """)
    self.assertTypesMatchPytd(ty, """
      import datetime
      def f() -> float: ...
    """)

  def test_import_pytd(self):
    with file_utils.Tempdir() as d:
      d.create_file("other_file.pyi", """
        def f() -> int: ...
      """)
      d.create_file("main.py", """
        from other_file import f
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int: ...
      """)

  def test_import_pytd2(self):
    with file_utils.Tempdir() as d:
      d.create_file("other_file.pyi", """
        def f() -> int: ...
      """)
      d.create_file("main.py", """
        from other_file import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int: ...
        def g() -> int: ...
      """)

  def test_import_directory(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("sub/other_file.pyi"),
          "def f() -> int: ...")
      d.create_file(
          file_utils.replace_separator("sub/bar/baz.pyi"),
          "def g() -> float: ...")
      d.create_file(file_utils.replace_separator("sub/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("sub/bar/__init__.pyi"), "")
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
        import sub  # from 'import sub.bar.baz'
        from sub import other_file
        def g() -> float: ...
        def h() -> int: ...
        def i() -> float: ...
        def j() -> float: ...
      """)

  def test_import_init(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("sub/__init__.pyi"), """
        def f() -> int: ...
      """)
      d.create_file("main.py", """
        from sub import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> int: ...
        def g() -> int: ...
      """)

  def test_import_name(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A:
          pass
        def f() -> A: ...
      """)
      d.create_file("main.py", """
        from foo import f
        def g():
          return f()
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        def f() -> foo.A: ...
        def g() -> foo.A: ...
    """)

  def test_deep_dependency(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", "x = ...  # type: bar.Bar")
      d.create_file("bar.pyi", """
          class Bar:
            def bar(self) -> int: ...
      """)
      d.create_file("main.py", """
        from foo import x
        def f():
          return x.bar()
      """)
      ty = self.InferFromFile(filename=d["main.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: bar.Bar
        def f() -> int: ...
    """)

  def test_relative_import(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/baz.pyi"),
          """x = ...  # type: int""")
      d.create_file(
          file_utils.replace_separator("foo/bar.py"), """
        from . import baz
        def f():
          return baz.x
      """)
      d.create_file(file_utils.replace_separator("foo/__init__.pyi"), "")
      ty = self.InferFromFile(
          filename=d[file_utils.replace_separator("foo/bar.py")],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from foo import baz
        def f() -> int: ...
    """)

  def test_dot_package(self):
    # This tests up one level: note that the test file (foo.py)
    # is tested in the context of the up-level director "up1".
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("up1/foo.py"), """
        from .bar import x
      """)
      d.create_file(
          file_utils.replace_separator("up1/bar.pyi"),
          """x = ...  # type: int""")
      d.create_file(file_utils.replace_separator("up1/__init__.pyi"), "")
      d.create_file("__init__.pyi", "")
      ty = self.InferFromFile(
          filename=d[file_utils.replace_separator("up1/foo.py")],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
    """)

  def test_dot_dot_package(self):
    # Similar to testDotPackage, except two levels
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("up2/baz/foo.py"), """
        from ..bar import x
      """)
      d.create_file(
          file_utils.replace_separator("up2/bar.pyi"),
          """x = ...  # type: int""")
      d.create_file("__init__.pyi", "")
      d.create_file(file_utils.replace_separator("up2/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("up2/baz/__init__.pyi"), "")
      ty = self.InferFromFile(
          filename=d[file_utils.replace_separator("up2/baz/foo.py")],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def test_dot_package_no_init(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.py", """
        from .bar import x
      """)
      d.create_file("bar.pyi", """x = ...  # type: int""")
      ty = self.InferFromFile(filename=d["foo.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def test_dot_dot_packag_no_init(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("baz/foo.py"), """
        from ..bar import x
      """)
      d.create_file("bar.pyi", """x = ...  # type: int""")
      ty = self.InferFromFile(
          filename=d[file_utils.replace_separator("baz/foo.py")],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        x = ...  # type: int
      """)

  def test_dot_dot(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/baz.pyi"),
          """x = ...  # type: int""")
      d.create_file(
          file_utils.replace_separator("foo/deep/bar.py"), """
        from .. import baz
        def f():
          return baz.x
      """)
      d.create_file(file_utils.replace_separator("foo/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("foo/deep/__init__.pyi"), "")
      ty = self.InferFromFile(
          filename=d[file_utils.replace_separator("foo/deep/bar.py")],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from foo import baz
        def f() -> int: ...
    """)

  def test_dot_dot_package_in_pyi(self):
    # Similar to testDotDotPackage, except for a pyi file.
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("up2/baz/foo.pyi"), """
        from ..bar import X
      """)
      d.create_file(file_utils.replace_separator("up2/bar.pyi"), "class X: ...")
      d.create_file("top.py", """
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

  def test_dot_dot_in_pyi(self):
    # Similar to testDotDot except in a pyi file.
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/baz.pyi"), "x: int")
      d.create_file(
          file_utils.replace_separator("foo/deep/bar.py"), """
        from .. import baz
        a = baz.x
      """)
      ty = self.InferFromFile(
          filename=d[file_utils.replace_separator("foo/deep/bar.py")],
          pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from foo import baz
        a: int
      """)

  def test_too_many_dots_in_package_in_pyi(self):
    # Trying to go up more directories than the package path contains
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("up/foo.pyi"), "from ..bar import X")
      d.create_file(file_utils.replace_separator("up/bar.pyi"), "class X: ...")
      _, err = self.InferWithErrors(
          "from up.foo import X  # pyi-error[e]", pythonpath=[d.path])
      self.assertErrorRegexes(
          err, {"e": r"Cannot resolve relative import \.\.bar"})

  def test_from_dot_in_pyi(self):
    # from . import module
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/a.pyi"), "class X: ...")
      d.create_file(
          file_utils.replace_separator("foo/b.pyi"), """
        from . import a
        Y = a.X""")
      d.create_file("top.py", """
        import foo.b
        x = foo.b.Y() """)
      ty = self.InferFromFile(filename=d["top.py"], pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo
        x = ...  # type: foo.a.X
      """)

  def test_unused_from_dot_in_pyi(self):
    # A `from . import module` that does not subsequently use the module should
    # not raise an unreplaced NamedType error.
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/a.pyi"), "class X: ...")
      d.create_file(
          file_utils.replace_separator("foo/b.pyi"), "from . import a")
      self.Check("import foo.b", pythonpath=[d.path])

  def test_file_import1(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("path/to/some/module.pyi"),
          "def foo(x:int) -> str: ...")
      d.create_file(
          file_utils.replace_separator("path/to/some/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("path/to/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("path/__init__.pyi"), "")
      ty = self.Infer("""
        import path.to.some.module
        def my_foo(x):
          return path.to.some.module.foo(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import path
        def my_foo(x) -> str: ...
      """)

  def test_file_import2(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("path/to/some/module.pyi"),
          "def foo(x:int) -> str: ...")
      d.create_file(
          file_utils.replace_separator("path/to/some/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("path/to/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("path/__init__.pyi"), "")
      ty = self.Infer("""
        from path.to.some import module
        def my_foo(x):
          return module.foo(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from path.to.some import module
        def my_foo(x) -> str: ...
      """)

  @test_base.skip("flaky")
  def test_solve_for_imported(self):
    ty = self.Infer("""
      import StringIO
      def my_foo(x):
        return x.read()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union
      StringIO = ...  # type: module
      def my_foo(x: Union[StringIO.StringIO[object], typing.IO[object],
                          typing.BinaryIO, typing.TextIO]) -> Any
    """)

  def test_import_builtins(self):
    ty = self.Infer("""
      import builtins as __builtin__

      def f():
        return __builtin__.int()
    """)
    self.assertTypesMatchPytd(ty, """
      import builtins as __builtin__

      def f() -> int: ...
    """)

  def test_imported_method_as_class_attribute(self):
    ty = self.Infer("""
      import os
      class Foo:
        kill = os.kill
    """)
    self.assertTypesMatchPytd(
        ty, """
      import os
      class Foo:
        def kill(__pid: int, __signal: int) -> None: ...
    """)

  def test_match_against_imported(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo:
          pass
        class Bar:
          def f1(self, x: Foo) -> Baz: ...
        class Baz:
          pass
      """)
      ty = self.Infer("""
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
        import foo
        def f(x, y) -> Any: ...
        def g(x) -> Any: ...
        def h(x) -> Any: ...

        class FooSub(foo.Foo):
          pass
      """)

  def test_imported_constants(self):
    with file_utils.Tempdir() as d:
      d.create_file("module.pyi", """
        x = ...  # type: int
        class Foo:
          x = ...  # type: float
      """)
      ty = self.Infer("""
        import module
        def f():
          return module.x
        def g():
          return module.Foo().x
        def h():
          return module.Foo.x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import module
        def f() -> int: ...
        def g() -> float: ...
        def h() -> float: ...
      """)

  def test_circular(self):
    with file_utils.Tempdir() as d:
      d.create_file("x.pyi", """
          class X:
            pass
          y = ...  # type: y.Y
          z = ...  # type: z.Z
      """)
      d.create_file("y.pyi", """
          class Y:
            pass
          x = ...  # type: x.X
      """)
      d.create_file("z.pyi", """
          class Z:
            pass
          x = ...  # type: x.X
      """)
      ty = self.Infer("""
        import x
        xx = x.X()
        yy = x.y
        zz = x.z
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import x
        xx = ...  # type: x.X
        yy = ...  # type: y.Y
        zz = ...  # type: z.Z
      """)

  def test_reimport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
          from collections import OrderedDict as MyOrderedDict
      """)
      ty = self.Infer("""
        import foo
        d = foo.MyOrderedDict()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        d = ...  # type: collections.OrderedDict[nothing, nothing]
      """)

  def test_import_function(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import SupportsFloat
        def pow(__x: SupportsFloat, __y: SupportsFloat) -> float: ...
      """)
      d.create_file("bar.pyi", """
          from foo import pow as mypow
      """)
      ty = self.Infer("""
        import bar
        d = bar.mypow
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import SupportsFloat
        import bar
        def d(__x: SupportsFloat, __y: SupportsFloat) -> float: ...
      """)

  def test_import_constant(self):
    with file_utils.Tempdir() as d:
      d.create_file("mymath.pyi", """
          from math import pi as half_tau
      """)
      ty = self.Infer("""
        import mymath
        from mymath import half_tau as x
        y = mymath.half_tau
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import mymath
        x = ...  # type: float
        y = ...  # type: float
      """)

  def test_import_map(self):
    with file_utils.Tempdir() as d:
      foo_filename = d.create_file("foo.pyi", """
          bar = ...  # type: int
      """)
      imports_map_filename = d.create_file("imports_map.txt", """
          foo %s
      """ % foo_filename)
      imports_map = imports_map_loader.build_imports_map(
          imports_map_filename)
      ty = self.Infer("""
        from foo import bar
      """, deep=False, imports_map=imports_map,
                      pythonpath=[""])
      self.assertTypesMatchPytd(ty, """
        bar = ...  # type: int
      """)

  def test_import_resolve_on_dummy(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", DEFAULT_PYI)
      d.create_file("b.pyi", """
          from a import Foo
          def f(x: Foo) -> Foo: ...
      """)
      ty = self.Infer("""
        import b
        foo = b.Foo()
        bar = b.f(foo)
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import b
        from typing import Any
        foo = ...  # type: Any
        bar = ...  # type: Any
      """)

  def test_two_level(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        +++ /&* unparsable *&/ +++
      """)
      d.create_file("b.pyi", """
        import a
        class B(a.A):
          pass
      """)
      _, errors = self.InferWithErrors("""
        import b  # pyi-error[e]
        x = b.B()
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e": r"a\.pyi"})

  def test_subdir_and_module_with_same_name_as_package(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("pkg/__init__.pyi"), """
          from pkg.pkg.pkg import *
          from pkg.bar import *""")
      d.create_file(
          file_utils.replace_separator("pkg/pkg/pkg.pyi"), """
          class X: pass""")
      d.create_file(
          file_utils.replace_separator("pkg/bar.pyi"), """
          class Y: pass""")
      ty = self.Infer("""
        import pkg
        a = pkg.X()
        b = pkg.Y()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import pkg
        a = ...  # type: pkg.pkg.pkg.X
        b = ...  # type: pkg.bar.Y
      """)

  def test_redefined_builtin(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        object = ...  # type: Any
        def f(x) -> Any: ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.f("")
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import foo
        x = ...  # type: Any
      """)

  def test_redefined_builtin2(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class object:
          def foo(self) -> None: ...
        def f(x: object) -> object: ...
      """)
      ty, _ = self.InferWithErrors("""
        import foo
        x = foo.f(foo.object())
        y = foo.f(foo.object())
        foo.f(object())  # wrong-arg-types
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        x = ...  # type: foo.object
        y = ...  # type: foo.object
      """)

  def test_no_fail_on_bad_symbol_lookup(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: FooBar) -> FooBar: ...
      """)
      self.assertNoCrash(self.Check, """
        import foo
      """, pythonpath=[d.path])

  @test_base.skip("instantiating 'type' should use 'Type[Any]', not 'Any'")
  def test_import_type_factory(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def factory() -> type: ...
      """)
      ty = self.Infer("""
        import a
        A = a.factory()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        A = ...  # type: type
      """)

  def test_get_bad_submodule_as_attribute(self):
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("foo/bar.pyi"), "nonsense")
      self.assertNoCrash(self.Check, """
        import foo
        x = foo.bar
      """, pythonpath=[d.path])

  def test_ignored_import(self):
    ty = self.Infer("""
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

  def test_attribute_on_module(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        foo = ...  # type: int
      """)
      _, errors = self.InferWithErrors("""
        from a import foo, bar  # import-error[e1]
        import a
        a.baz  # module-attr[e2]
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e1": r"bar", "e2": r"baz"})

  def test_from_import(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/b.pyi"), """
        from foo import c
        class bar(c.X): ...
      """)
      d.create_file(
          file_utils.replace_separator("foo/c.pyi"), """
        class X: ...
      """)
      self.Check("""
        from foo import b
        class Foo(b.bar):
          pass
      """, pythonpath=[d.path])

  def test_submodule_lookup(self):
    # Tests a common Blaze pattern: when mod/__init__.py and mod/submod.py are
    # in the same target, they are analyzed twice, and we should not use the
    # first-pass __init__.pyi to look up types for the second pass, as the
    # former contains a 'submod: Any' entry that masks the actual submodule.

    # The "%s" is used to silence the import error from the first pass.
    init_py = """
      from mod import submod%s
      X = submod.X
    """
    submod_py = """
      class X:
        pass
    """
    init_pyi_1, _ = self.InferWithErrors(
        init_py % "  # import-error", module_name="mod.__init__")
    submod_pyi_1, _ = self.InferWithErrors(submod_py, module_name="mod.submod")
    with file_utils.Tempdir() as d:
      init_path = d.create_file(
          file_utils.replace_separator("mod/__init__.pyi"),
          pytd_utils.Print(init_pyi_1))
      submod_path = d.create_file(
          file_utils.replace_separator("mod/submod.pyi"),
          pytd_utils.Print(submod_pyi_1))
      imports_info = d.create_file(
          "imports_info", f"""
        {file_utils.replace_separator('mod/__init__')} {init_path}
        {file_utils.replace_separator('mod/submod')} {submod_path}
      """)
      imports_map = imports_map_loader.build_imports_map(imports_info)
      init_pyi = self.Infer(
          init_py % "", imports_map=imports_map, module_name="mod.__init__")
    self.assertTypesMatchPytd(init_pyi, """
      from mod import submod
      from typing import Type
      X: Type[mod.submod.X]
    """)

  def test_circular_dep(self):
    # This test imitates how analyze_project handles circular dependencies.
    # See https://github.com/google/pytype/issues/760. In the test, the circular
    # dep is between a module's __init__.py and a submodule to make it harder
    # for pytype to distinguish this case from test_submodule_lookup.

    # "%s" is used to silence import errors from the first-pass analysis.
    submod_py = """
      from mod import Y%s
      class X:
        pass
    """
    init_py = """
      import typing
      if typing.TYPE_CHECKING:
        from mod.submod import X%s
      class Y:
        def __init__(self, x):
          # type: ('X') -> None
          pass
    """
    submod_pyi_1, _ = self.InferWithErrors(
        submod_py % "  # import-error", module_name="mod.submod")
    init_pyi_1, _ = self.InferWithErrors(
        init_py % "  # import-error", module_name="mod.__init__")
    with file_utils.Tempdir() as d:
      submod_path = d.create_file(
          file_utils.replace_separator("mod/submod.pyi"),
          pytd_utils.Print(submod_pyi_1))
      init_path = d.create_file(
          file_utils.replace_separator("mod/__init__.pyi"),
          pytd_utils.Print(init_pyi_1))
      imports_info = d.create_file(
          "imports_info", f"""
        {file_utils.replace_separator('mod/submod')} {submod_path}
        {file_utils.replace_separator('mod/__init__')} {init_path}
      """)
      imports_map = imports_map_loader.build_imports_map(imports_info)
      submod_pyi = self.Infer(submod_py % "", imports_map=imports_map,
                              module_name="mod.submod")
      with open(submod_path, "w") as f:
        f.write(pytd_utils.Print(submod_pyi))
      init_pyi = self.Infer(init_py % "", imports_map=imports_map,
                            module_name="mod.__init__")
    self.assertTypesMatchPytd(init_pyi, """
      import mod.submod
      import typing
      from typing import Type
      X: Type[mod.submod.X]
      class Y:
        def __init__(self, x: X) -> None: ...
    """)

  def test_mutual_imports(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("pkg/a.pyi"), """
        from typing import TypeVar, Generic, List
        from .b import Foo
        T = TypeVar('T')
        class Bar(Foo, List[T], Generic[T]): ...
        class Baz(List[T], Generic[T]): ...
      """)
      d.create_file(
          file_utils.replace_separator("pkg/b.pyi"), """
        from typing import TypeVar, Generic
        from .a import Baz
        T = TypeVar('T')
        class Foo(): ...
        class Quux(Baz[T], Generic[T]): ...
      """)
      ty = self.Infer("""from pkg.a import *""", pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import pkg.a
        import pkg.b
        from typing import Type, TypeVar
        Bar = ...  # type: Type[pkg.a.Bar]
        Baz = ...  # type: Type[pkg.a.Baz]
        Foo = ...  # type: Type[pkg.b.Foo]
        T = TypeVar('T')
      """)

  def test_module_reexports_and_aliases(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("pkg/a.pyi"), """
        from pkg import b as c
        from pkg.b import e as f
        import pkg.d as x
        import pkg.g  # should not cause unused import errors
      """)
      d.create_file(
          file_utils.replace_separator("pkg/b.pyi"), """
        class X: ...
        class e: ...
      """)
      d.create_file(
          file_utils.replace_separator("pkg/d.pyi"), """
        class Y: ...
      """)
      d.create_file(
          file_utils.replace_separator("pkg/g.pyi"), """
        class Z: ...
      """)
      ty = self.Infer("""
        import pkg.a
        s = pkg.a.c.X()
        t = pkg.a.f()
        u = pkg.a.x
        v = u.Y()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import pkg
        from pkg import d as u
        s = ...  # type: pkg.b.X
        t = ...  # type: pkg.b.e
        v = ...  # type: u.Y
      """)

  def test_import_package_as_alias(self):
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

  def test_import_package_alias_name_conflict(self):
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
        import b
        x: str
        y: int
      """)

  def test_import_package_alias_name_conflict2(self):
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
        import c
        x: str
        y: int
      """)

  def test_import_package_alias_name_conflict3(self):
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
        import c
        x: str
        y: int
      """)

  def test_module_class_conflict(self):
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/bar.pyi"), DEFAULT_PYI)
      ty = self.Infer("""
        from foo import bar
        class foo:
          def __new__(cls):
            return object.__new__(cls)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from foo import bar
        from typing import Type, TypeVar
        _Tfoo = TypeVar("_Tfoo", bound=foo)
        class foo:
          def __new__(cls: Type[_Tfoo]) -> _Tfoo: ...
      """)

  def test_class_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/bar.pyi"), DEFAULT_PYI)
      ty = self.Infer("""
        from foo import bar
        class foo:
          pass
        baz = foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from foo import bar
        from typing import Type
        class foo: ...
        baz: Type[foo]
      """)

  def test_relative_star_import(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/bar.pyi"), "from .baz.qux import *")
      d.create_file(
          file_utils.replace_separator("foo/baz/qux.pyi"),
          "v = ...  # type: int")
      ty = self.Infer("""
        from foo.bar import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        v = ...  # type: int
      """)

  def test_relative_star_import2(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/bar/baz.pyi"),
          "from ..bar.qux import *")
      d.create_file(
          file_utils.replace_separator("foo/bar/qux.pyi"),
          "v = ...  # type: int")
      ty = self.Infer("""
        from foo.bar.baz import *
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        v = ...  # type: int
      """)

  def test_unimported_submodule_failure(self):
    """Fail when accessing a submodule we haven't imported."""
    self.options.tweak(strict_import=True)
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("sub/bar/baz.pyi"), "class A: ...")
      d.create_file(
          file_utils.replace_separator("sub/bar/quux.pyi"), "class B: ...")
      d.create_file(file_utils.replace_separator("sub/__init__.pyi"), "")
      d.create_file(file_utils.replace_separator("sub/bar/__init__.pyi"), "")
      _, errors = self.InferWithErrors("""
        import sub.bar.baz
        x = sub.bar.baz.A()
        y = sub.bar.quux.B()  # module-attr[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"quux.*sub\.bar"})

  def test_submodule_attribute_error(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("package/__init__.pyi"),
          "submodule: module")
      d.create_file(file_utils.replace_separator("package/submodule.pyi"), "")
      self.CheckWithErrors("""
        from package import submodule
        submodule.asd  # module-attr
      """, pythonpath=[d.path])

  def test_init_only_submodule(self):
    """Test a submodule without its own stub file."""
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("package/__init__.pyi"),
          "submodule: module")
      self.Check("""
        from package import submodule
        submodule.asd
      """, pythonpath=[d.path])

  def test_import_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file(file_utils.replace_separator("foo/__init__.pyi"), "")
      d.create_file(
          file_utils.replace_separator("foo/bar.pyi"), """
        from foo import baz as qux
        X = qux.X
      """)
      d.create_file(file_utils.replace_separator("foo/baz.pyi"), "X = str")
      self.Check("from foo import bar", pythonpath=[d.path])

  def test_subpackage(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/__init__.pyi"),
          "from .bar import baz as baz")
      d.create_file(file_utils.replace_separator("foo/bar/baz.pyi"), "v: str")
      ty = self.Infer("""
        import foo
        v = foo.baz.v
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        v: str
      """)

  def test_attr_and_module(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          file_utils.replace_separator("foo/__init__.pyi"), "class X: ...")
      d.create_file(file_utils.replace_separator("foo/bar.pyi"), "v: str")
      d.create_file("other.pyi", """
        from foo import X as X
        from foo import bar as bar
      """)
      ty = self.Infer("""
        import other
        X = other.X
        v = other.bar.v
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo
        import other
        X: Type[foo.X]
        v: str
      """)

  def test_submodule_imports_info(self):
    # Tests that the presence of a submodule in imports_info doesn't prevent
    # pytype from finding attributes in a module's __init__ file.
    with file_utils.Tempdir() as d:
      empty = d.create_file("empty.pyi")
      imports_info = d.create_file(
          "imports_info",
          f"email/_header_value_parser {empty}")
      imports_map = imports_map_loader.build_imports_map(imports_info)
      self.Check("""
        from email import message_from_bytes
      """, imports_map=imports_map)

  def test_directory_module_clash(self):
    with file_utils.Tempdir() as d:
      foo = d.create_file("foo.pyi", "x: int")
      foo_bar = d.create_file(
          file_utils.replace_separator("foo/bar.pyi"), "y: str")
      imports_info = d.create_file(
          "imports_info", f"""
        foo {foo}
        {file_utils.replace_separator('foo/bar')} {foo_bar}
      """)
      imports_map = imports_map_loader.build_imports_map(imports_info)
      # When both foo.py and a foo/ package exist, the latter shadows the
      # former, so `import foo` gets you the (empty) foo/__init__.py.
      self.CheckWithErrors("""
        import foo
        x = foo.x  # module-attr
      """, imports_map=imports_map)

  def test_missing_submodule(self):
    with file_utils.Tempdir() as d:
      foo = d.create_file(
          file_utils.replace_separator("foo/__init__.pyi"),
          "import bar.baz as baz")
      foo_bar = d.create_file(
          file_utils.replace_separator("foo/bar.pyi"), "y: str")
      imports_info = d.create_file(
          file_utils.replace_separator("imports_info"), f"""
        foo {foo}
        {file_utils.replace_separator('foo/bar')} {foo_bar}
      """)
      imports_map = imports_map_loader.build_imports_map(imports_info)
      self.CheckWithErrors("""
        from foo import baz  # import-error
      """, imports_map=imports_map)


if __name__ == "__main__":
  test_base.main()
