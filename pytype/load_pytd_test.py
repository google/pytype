"""Tests for load_pytd.py."""

import collections
import io
import os
import textwrap

from pytype import file_utils
from pytype import load_pytd
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import serialize_ast
from pytype.pytd import visitors
from pytype.tests import test_base

import unittest


class ImportPathsTest(test_base.UnitTest):
  """Tests for load_pytd.py."""

  def test_filepath_to_module(self):
    # (filename, pythonpath, expected)
    test_cases = [
        ("foo/bar/baz.py", [""], "foo.bar.baz"),
        ("foo/bar/baz.py", ["foo"], "bar.baz"),
        ("foo/bar/baz.py", ["fo"], "foo.bar.baz"),
        ("foo/bar/baz.py", ["foo/"], "bar.baz"),
        ("foo/bar/baz.py", ["foo", "bar"], "bar.baz"),
        ("foo/bar/baz.py", ["foo/bar", "foo"], "baz"),
        ("foo/bar/baz.py", ["foo", "foo/bar"], "bar.baz"),
        ("./foo/bar.py", [""], "foo.bar"),
        ("./foo.py", [""], "foo"),
        ("../foo.py", [""], None),
        ("../foo.py", ["."], None),
        ("foo/bar/../baz.py", [""], "foo.baz"),
        ("../foo.py", [".."], "foo"),
        ("../../foo.py", ["../.."], "foo"),
        ("../../foo.py", [".."], None)
    ]
    for filename, pythonpath, expected in test_cases:
      module = load_pytd.get_module_name(filename, pythonpath)
      self.assertEqual(module, expected)

  def test_builtin_sys(self):
    loader = load_pytd.Loader("base", self.python_version)
    ast = loader.import_name("sys")
    self.assertTrue(ast.Lookup("sys.exit"))

  def test_basic(self):
    with file_utils.Tempdir() as d:
      d.create_file("path/to/some/module.pyi", "def foo(x:int) -> str: ...")
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d.path])
      ast = loader.import_name("path.to.some.module")
      self.assertTrue(ast.Lookup("path.to.some.module.foo"))

  def test_path(self):
    with file_utils.Tempdir() as d1:
      with file_utils.Tempdir() as d2:
        d1.create_file("dir1/module1.pyi", "def foo1() -> str: ...")
        d2.create_file("dir2/module2.pyi", "def foo2() -> str: ...")
        loader = load_pytd.Loader(
            "base", self.python_version, pythonpath=[d1.path, d2.path])
        module1 = loader.import_name("dir1.module1")
        module2 = loader.import_name("dir2.module2")
        self.assertTrue(module1.Lookup("dir1.module1.foo1"))
        self.assertTrue(module2.Lookup("dir2.module2.foo2"))

  def test_init(self):
    with file_utils.Tempdir() as d1:
      d1.create_file("baz/__init__.pyi", "x = ... # type: int")
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d1.path])
      self.assertTrue(loader.import_name("baz").Lookup("baz.x"))

  def test_builtins(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", "x = ... # type: int")
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d.path])
      mod = loader.import_name("foo")
      self.assertEqual("__builtin__.int", mod.Lookup("foo.x").type.cls.name)
      self.assertEqual("__builtin__.int", mod.Lookup("foo.x").type.name)

  def test_no_init(self):
    with file_utils.Tempdir() as d:
      d.create_directory("baz")
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d.path])
      self.assertTrue(loader.import_name("baz"))

  def test_no_init_imports_map(self):
    with file_utils.Tempdir() as d:
      d.create_directory("baz")
      os.chdir(d.path)
      loader = load_pytd.Loader(
          "base", self.python_version, imports_map={}, pythonpath=[""])
      self.assertFalse(loader.import_name("baz"))

  def test_stdlib(self):
    loader = load_pytd.Loader("base", self.python_version)
    ast = loader.import_name("io")
    self.assertTrue(ast.Lookup("io.StringIO"))

  def test_deep_dependency(self):
    with file_utils.Tempdir() as d:
      d.create_file("module1.pyi", "def get_bar() -> module2.Bar: ...")
      d.create_file("module2.pyi", "class Bar:\n  pass")
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d.path])
      module1 = loader.import_name("module1")
      f, = module1.Lookup("module1.get_bar").signatures
      self.assertEqual("module2.Bar", f.return_type.cls.name)

  def test_circular_dependency(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def get_bar() -> bar.Bar: ...
        class Foo:
          pass
      """)
      d.create_file("bar.pyi", """
        def get_foo() -> foo.Foo: ...
        class Bar:
          pass
      """)
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d.path])
      foo = loader.import_name("foo")
      bar = loader.import_name("bar")
      f1, = foo.Lookup("foo.get_bar").signatures
      f2, = bar.Lookup("bar.get_foo").signatures
      self.assertEqual("bar.Bar", f1.return_type.cls.name)
      self.assertEqual("foo.Foo", f2.return_type.cls.name)

  def test_relative(self):
    with file_utils.Tempdir() as d:
      d.create_file("__init__.pyi", "base = ...  # type: str")
      d.create_file("path/__init__.pyi", "path = ...  # type: str")
      d.create_file("path/to/__init__.pyi", "to = ...  # type: str")
      d.create_file("path/to/some/__init__.pyi", "some = ...  # type: str")
      d.create_file("path/to/some/module.pyi", "")
      loader = load_pytd.Loader("path.to.some.module",
                                self.python_version,
                                pythonpath=[d.path])
      some = loader.import_relative(1)
      to = loader.import_relative(2)
      path = loader.import_relative(3)
      # Python doesn't allow "...." here, so don't test import_relative(4).
      self.assertTrue(some.Lookup("path.to.some.some"))
      self.assertTrue(to.Lookup("path.to.to"))
      self.assertTrue(path.Lookup("path.path"))

  def test_typeshed(self):
    loader = load_pytd.Loader("base", self.python_version)
    self.assertTrue(loader.import_name("urllib.request"))

  def test_resolve_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("module1.pyi", """
          from typing import List
          x = List[int]
      """)
      d.create_file("module2.pyi", """
          def f() -> module1.x: ...
      """)
      loader = load_pytd.Loader(
          "base", self.python_version, pythonpath=[d.path])
      module2 = loader.import_name("module2")
      f, = module2.Lookup("module2.f").signatures
      self.assertEqual("List[int]", pytd_utils.Print(f.return_type))

  def test_import_map_congruence(self):
    with file_utils.Tempdir() as d:
      foo_path = d.create_file("foo.pyi", "class X: ...")
      bar_path = d.create_file("bar.pyi", "X = ...  # type: another.foo.X")
      # Map the same pyi file under two module paths.
      imports_map = {
          "foo": foo_path,
          "another/foo": foo_path,
          "bar": bar_path,
          "empty1": "/dev/null",
          "empty2": "/dev/null",
      }
      # We cannot use tweak(imports_info=...) because that doesn't trigger
      # post-processing and we need an imports_map for the loader.
      loader = load_pytd.Loader(
          "base", self.python_version, imports_map=imports_map, pythonpath=[""])
      normal = loader.import_name("foo")
      self.assertEqual("foo", normal.name)
      loader.import_name("bar")  # check that we can resolve against another.foo
      another = loader.import_name("another.foo")
      # We do *not* treat foo.X and another.foo.X the same, because Python
      # doesn't, either:
      self.assertIsNot(normal, another)
      self.assertTrue([c.name.startswith("foo")
                       for c in normal.classes])
      self.assertTrue([c.name.startswith("another.foo")
                       for c in another.classes])
      # Make sure that multiple modules using /dev/null are not treated as
      # congruent.
      empty1 = loader.import_name("empty1")
      empty2 = loader.import_name("empty2")
      self.assertIsNot(empty1, empty2)
      self.assertEqual("empty1", empty1.name)
      self.assertEqual("empty2", empty2.name)

  def test_package_relative_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("pkg/foo.pyi", "class X: ...")
      d.create_file("pkg/bar.pyi", """
          from .foo import X
          y = ...  # type: X""")
      loader = load_pytd.Loader(
          "pkg.bar", self.python_version, pythonpath=[d.path])
      bar = loader.import_name("pkg.bar")
      f = bar.Lookup("pkg.bar.y")
      self.assertEqual("pkg.foo.X", f.type.name)

  def test_directory_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("pkg/sub/__init__.pyi", """
          from .foo import *
          from .bar import *""")
      d.create_file("pkg/sub/foo.pyi", """
          class X: pass""")
      d.create_file("pkg/sub/bar.pyi", """
          from .foo import X
          y = ...  # type: X""")
      loader = load_pytd.Loader("pkg", self.python_version, pythonpath=[d.path])
      ast = loader.import_name("pkg.sub")
      self.assertTrue(ast.Lookup("pkg.sub.X"))

  def test_diamond_import(self):
    """Should not fail on importing a module via two paths."""
    with file_utils.Tempdir() as d:
      d.create_file("pkg/sub/__init__.pyi", """
          from .foo import *
          from .bar import *""")
      d.create_file("pkg/sub/foo.pyi", """
          from .baz import X""")
      d.create_file("pkg/sub/bar.pyi", """
          from .baz import X""")
      d.create_file("pkg/sub/baz.pyi", """
          class X: ...""")
      loader = load_pytd.Loader("pkg", self.python_version, pythonpath=[d.path])
      ast = loader.import_name("pkg.sub")
      self.assertTrue(ast.Lookup("pkg.sub.X"))

  def test_get_resolved_modules(self):
    with file_utils.Tempdir() as d:
      filename = d.create_file("dir/module.pyi", "def foo() -> str: ...")
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      ast = loader.import_name("dir.module")
      modules = loader.get_resolved_modules()
      self.assertEqual(set(modules), {"__builtin__", "typing", "dir.module"})
      module = modules["dir.module"]
      self.assertEqual(module.module_name, "dir.module")
      self.assertEqual(module.filename, filename)
      self.assertEqual(module.ast, ast)

  def test_circular_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("os2/__init__.pyi", """
        from . import path as path
        _PathType = path._PathType
        def utime(path: _PathType) -> None: ...
        class stat_result(object): ...
      """)
      d.create_file("os2/path.pyi", """
        import os2
        _PathType = bytes
        def samestat(stat1: os2.stat_result) -> bool: ...
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      ast = loader.import_name("os2.path")
      self.assertEqual(ast.Lookup("os2.path._PathType").type.name,
                       "__builtin__.bytes")

  def test_circular_import_with_external_type(self):
    with file_utils.Tempdir() as d:
      d.create_file("os2/__init__.pyi", """
        from posix2 import stat_result as stat_result
        from . import path as path
        _PathType = path._PathType
        def utime(path: _PathType) -> None: ...
      """)
      d.create_file("os2/path.pyi", """
        import os2
        _PathType = bytes
        def samestate(stat1: os2.stat_result) -> bool: ...
      """)
      d.create_file("posix2.pyi", "class stat_result: ...")
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      # Make sure all three modules were resolved properly.
      loader.import_name("os2")
      loader.import_name("os2.path")
      loader.import_name("posix2")

  def test_union_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("test.pyi", """
        from typing import Union as _UnionT
        x: _UnionT[int, str]
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      ast = loader.import_name("test")
      x = ast.Lookup("test.x")
      self.assertIsInstance(x.type, pytd.UnionType)

  def test_optional_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("test.pyi", """
        from typing import Optional as _OptionalT
        x: _OptionalT[int]
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      ast = loader.import_name("test")
      x = ast.Lookup("test.x")
      self.assertIsInstance(x.type, pytd.UnionType)

  def test_intersection_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("test.pyi", """
        from typing import Intersection as _IntersectionT
        x: _IntersectionT[int, str]
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      ast = loader.import_name("test")
      x = ast.Lookup("test.x")
      self.assertIsInstance(x.type, pytd.IntersectionType)

  def test_python2_builtins(self):
    # Test that we read python2 builtins from builtin.pytd if we pass a python2
    # version to the loader.
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
          from UserDict import UserDict
          class A(UserDict): ...""")
      loader = load_pytd.Loader("base",
                                python_version=(2, 7),
                                pythonpath=[d.path])
      a = loader.import_name("a")
      cls = a.Lookup("a.A")
      self.assertEqual("UserDict.UserDict", pytd_utils.Print(cls.parents[0]))

  def test_open_function(self):
    def mock_open(*unused_args, **unused_kwargs):
      return io.StringIO("x: int")
    loader = load_pytd.Loader(
        "base", self.python_version, open_function=mock_open)
    a = loader.load_file("a", "a.pyi")
    self.assertEqual("int", pytd_utils.Print(a.Lookup("a.x").type))

  def test_submodule_reexport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar.pyi", "")
      d.create_file("foo/__init__.pyi", """
        from . import bar as bar
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      foo = loader.import_name("foo")
      self.assertEqual(pytd_utils.Print(foo), "import foo.bar")

  def test_submodule_rename(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar.pyi", "")
      d.create_file("foo/__init__.pyi", """
        from . import bar as baz
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      foo = loader.import_name("foo")
      self.assertEqual(pytd_utils.Print(foo), "import foo.bar as foo.baz")

  def test_typing_reexport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List as List
      """)
      d.create_file("bar.pyi", """
        from foo import *
        def f() -> List[int]: ...
      """)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      foo = loader.import_name("foo")
      bar = loader.import_name("bar")
      self.assertEqual(pytd_utils.Print(foo), "foo.List = list")
      self.assertEqual(pytd_utils.Print(bar), textwrap.dedent("""
        from typing import List

        bar.List = list

        def bar.f() -> List[int]: ...
      """).strip())


class ImportTypeMacroTest(test_base.UnitTest):

  def _import(self, a_pyi, b_pyi):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", a_pyi)
      d.create_file("b.pyi", b_pyi)
      loader = load_pytd.Loader(None, self.python_version, pythonpath=[d.path])
      return loader.import_name("b")

  def test_container(self):
    ast = self._import("""
      from typing import List, TypeVar
      T = TypeVar('T')
      Alias = List[T]
    """, """
      import a
      Strings = a.Alias[str]
    """)
    self.assertEqual(
        pytd_utils.Print(ast.Lookup("b.Strings").type), "List[str]")

  def test_union(self):
    ast = self._import("""
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      Alias = Union[T, List[T]]
    """, """
      import a
      Strings = a.Alias[str]
    """)
    self.assertEqual(pytd_utils.Print(ast.Lookup("b.Strings").type),
                     "Union[str, List[str]]")

  def test_bad_parameterization(self):
    with self.assertRaisesRegex(
        load_pytd.BadDependencyError,
        r"Union\[T, List\[T\]\] expected 1 parameters, got 2"):
      self._import("""
        from typing import List, TypeVar, Union
        T = TypeVar('T')
        Alias = Union[T, List[T]]
      """, """
        import a
        Strings = a.Alias[str, str]
      """)

  def test_no_parameters(self):
    ast = self._import("""
      from typing import List, TypeVar
      T = TypeVar('T')
      Alias = List[T]
    """, """
      import a
      def f(x: a.Alias): ...
    """)
    self.assertEqual(
        pytd_utils.Print(ast.Lookup("b.f").signatures[0].params[0].type),
        "List[Any]")


_Module = collections.namedtuple("_", ["module_name", "file_name"])


class PickledPyiLoaderTest(test_base.UnitTest):

  def _create_files(self, tempdir):
    src = """
        import module2
        from typing import List

        constant = True

        x = List[int]
        b = List[int]

        class SomeClass(object):
          def __init__(self, a: module2.ObjectMod2):
            pass

        def ModuleFunction():
          pass
    """
    tempdir.create_file("module1.pyi", src)
    tempdir.create_file("module2.pyi", """
        class ObjectMod2(object):
          def __init__(self):
            pass
    """)

  def _get_path(self, tempdir, filename):
    return os.path.join(tempdir.path, filename)

  def _load_ast(self, tempdir, module):
    loader = load_pytd.Loader(
        base_module=module.module_name, python_version=self.python_version,
        pythonpath=[tempdir.path])
    return loader, loader.load_file(
        module.module_name, self._get_path(tempdir, module.file_name))

  def _pickle_modules(self, loader, tempdir, *modules):
    for module in modules:
      serialize_ast.StoreAst(
          loader._modules[module.module_name].ast,
          self._get_path(tempdir, module.file_name + ".pickled"))

  def _load_pickled_module(self, tempdir, module):
    pickle_loader = load_pytd.PickledPyiLoader(
        base_module=None, python_version=self.python_version,
        pythonpath=[tempdir.path])
    return pickle_loader.load_file(
        module.module_name, self._get_path(tempdir, module.file_name))

  def test_load_with_same_module_name(self):
    with file_utils.Tempdir() as d:
      self._create_files(tempdir=d)
      module1 = _Module(module_name="foo.bar.module1", file_name="module1.pyi")
      module2 = _Module(module_name="module2", file_name="module2.pyi")
      loader, ast = self._load_ast(tempdir=d, module=module1)
      self._pickle_modules(loader, d, module1, module2)
      pickled_ast_filename = self._get_path(d, module1.file_name + ".pickled")
      result = serialize_ast.StoreAst(ast, pickled_ast_filename)
      self.assertIsNone(result)

      loaded_ast = self._load_pickled_module(d, module1)
      self.assertTrue(loaded_ast)
      self.assertIsNot(loaded_ast, ast)
      self.assertTrue(pytd_utils.ASTeq(ast, loaded_ast))
      loaded_ast.Visit(visitors.VerifyLookup())

  def test_star_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", "class A(object): ...")
      d.create_file("bar.pyi", "from foo import *")
      foo = _Module(module_name="foo", file_name="foo.pyi")
      bar = _Module(module_name="bar", file_name="bar.pyi")
      loader, _ = self._load_ast(d, module=bar)
      self._pickle_modules(loader, d, foo, bar)
      loaded_ast = self._load_pickled_module(d, bar)
      loaded_ast.Visit(visitors.VerifyLookup())
      self.assertMultiLineEqual(pytd_utils.Print(loaded_ast),
                                textwrap.dedent("""
        import foo

        bar.A = foo.A""").lstrip())

  def test_function_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(): ...
        g = f
      """)
      foo = _Module(module_name="foo", file_name="foo.pyi")
      loader, _ = self._load_ast(d, module=foo)
      self._pickle_modules(loader, d, foo)
      loaded_ast = self._load_pickled_module(d, foo)
      g = loaded_ast.Lookup("foo.g")
      self.assertEqual(g.type.function, loaded_ast.Lookup("foo.f"))

  def test_package_relative_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("pkg/foo.pyi", "class X: ...")
      d.create_file("pkg/bar.pyi", """
          from .foo import X
          y = ...  # type: X""")
      foo = _Module(module_name="pkg.foo", file_name="pkg/foo.pyi")
      bar = _Module(module_name="pkg.bar", file_name="pkg/bar.pyi")
      loader, _ = self._load_ast(d, module=bar)
      self._pickle_modules(loader, d, foo, bar)
      loaded_ast = self._load_pickled_module(d, bar)
      loaded_ast.Visit(visitors.VerifyLookup())

  def test_pickled_builtins(self):
    with file_utils.Tempdir() as d:
      filename = d.create_file("builtins.pickle")
      foo_path = d.create_file("foo.pickle", """
        import datetime
        tz = ...  # type: datetime.tzinfo
      """)
      # save builtins
      load_pytd.Loader("base", self.python_version).save_to_pickle(filename)
      # load builtins
      loader = load_pytd.PickledPyiLoader.load_from_pickle(
          filename, "base",
          python_version=self.python_version,
          imports_map={"foo": foo_path},
          pythonpath=[""])
      # test import
      self.assertTrue(loader.import_name("sys"))
      self.assertTrue(loader.import_name("__future__"))
      self.assertTrue(loader.import_name("datetime"))
      self.assertTrue(loader.import_name("foo"))
      self.assertTrue(loader.import_name("ctypes"))


if __name__ == "__main__":
  unittest.main()
