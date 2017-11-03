"""Tests for load_pytd.py."""

import collections
import os
import textwrap

from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import pytd
from pytype.pytd import serialize_ast
from pytype.pytd.parse import visitors

import unittest


class ImportPathsTest(unittest.TestCase):
  """Tests for load_pytd.py."""

  PYTHON_VERSION = (2, 7)

  def setUp(self):
    self.options = config.Options.create(python_version=self.PYTHON_VERSION)

  def testBuiltinSys(self):
    loader = load_pytd.Loader("base", self.options)
    ast = loader.import_name("sys")
    self.assertTrue(ast.Lookup("sys.exit"))

  def testBasic(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pyi", "def foo(x:int) -> str")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      ast = loader.import_name("path.to.some.module")
      self.assertTrue(ast.Lookup("path.to.some.module.foo"))

  def testPath(self):
    with utils.Tempdir() as d1:
      with utils.Tempdir() as d2:
        d1.create_file("dir1/module1.pyi", "def foo1() -> str")
        d2.create_file("dir2/module2.pyi", "def foo2() -> str")
        self.options.tweak(pythonpath=[d1.path, d2.path])
        loader = load_pytd.Loader("base", self.options)
        module1 = loader.import_name("dir1.module1")
        module2 = loader.import_name("dir2.module2")
        self.assertTrue(module1.Lookup("dir1.module1.foo1"))
        self.assertTrue(module2.Lookup("dir2.module2.foo2"))

  def testInit(self):
    with utils.Tempdir() as d1:
      d1.create_file("baz/__init__.pyi", "x = ... # type: int")
      self.options.tweak(pythonpath=[d1.path])
      loader = load_pytd.Loader("base", self.options)
      self.assertTrue(loader.import_name("baz").Lookup("baz.x"))

  def testBuiltins(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "x = ... # type: int")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      mod = loader.import_name("foo")
      self.assertEqual("__builtin__.int", mod.Lookup("foo.x").type.cls.name)
      self.assertEqual("__builtin__.int", mod.Lookup("foo.x").type.name)

  def testNoInit(self):
    with utils.Tempdir() as d:
      d.create_directory("baz")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      self.assertTrue(loader.import_name("baz"))

  def testNoInitImportsMap(self):
    with utils.Tempdir() as d:
      d.create_directory("baz")
      self.options.imports_map = {}
      os.chdir(d.path)
      loader = load_pytd.Loader("base", self.options)
      self.assertFalse(loader.import_name("baz"))

  def testStdlib(self):
    loader = load_pytd.Loader("base", self.options)
    ast = loader.import_name("StringIO")
    self.assertTrue(ast.Lookup("StringIO.StringIO"))

  def testDeepDependency(self):
    with utils.Tempdir() as d:
      d.create_file("module1.pyi", "def get_bar() -> module2.Bar")
      d.create_file("module2.pyi", "class Bar:\n  pass")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      module1 = loader.import_name("module1")
      f, = module1.Lookup("module1.get_bar").signatures
      self.assertEqual("module2.Bar", f.return_type.cls.name)

  def testCircularDependency(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def get_bar() -> bar.Bar
        class Foo:
          pass
      """)
      d.create_file("bar.pyi", """
        def get_foo() -> foo.Foo
        class Bar:
          pass
      """)
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      foo = loader.import_name("foo")
      bar = loader.import_name("bar")
      f1, = foo.Lookup("foo.get_bar").signatures
      f2, = bar.Lookup("bar.get_foo").signatures
      self.assertEqual("bar.Bar", f1.return_type.cls.name)
      self.assertEqual("foo.Foo", f2.return_type.cls.name)

  def testRelative(self):
    with utils.Tempdir() as d:
      d.create_file("__init__.pyi", "base = ...  # type: ?")
      d.create_file("path/__init__.pyi", "path = ...  # type: ?")
      d.create_file("path/to/__init__.pyi", "to = ...  # type: ?")
      d.create_file("path/to/some/__init__.pyi", "some = ...  # type: ?")
      d.create_file("path/to/some/module.pyi", "")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("path.to.some.module", self.options)
      some = loader.import_relative(1)
      to = loader.import_relative(2)
      path = loader.import_relative(3)
      # Python doesn't allow "...." here, so don't test import_relative(4).
      self.assertTrue(some.Lookup("path.to.some.some"))
      self.assertTrue(to.Lookup("path.to.to"))
      self.assertTrue(path.Lookup("path.path"))

  def testTypeShed(self):
    loader = load_pytd.Loader("base", self.options)
    self.assertTrue(loader.import_name("UserDict"))

  def testResolveAlias(self):
    with utils.Tempdir() as d:
      d.create_file("module1.pyi", """
          from typing import List
          x = List[int]
      """)
      d.create_file("module2.pyi", """
          def f() -> module1.x
      """)
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      module2 = loader.import_name("module2")
      f, = module2.Lookup("module2.f").signatures
      self.assertEqual("List[int]", pytd.Print(f.return_type))

  def testImportMapCongruence(self):
    with utils.Tempdir() as d:
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
      self.options.imports_map = imports_map
      loader = load_pytd.Loader("base", self.options)
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

  def testPackageRelativeImport(self):
    with utils.Tempdir() as d:
      d.create_file("pkg/foo.pyi", "class X: ...")
      d.create_file("pkg/bar.pyi", """
          from .foo import X
          y = ...  # type: X""")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("pkg.bar", self.options)
      bar = loader.import_name("pkg.bar")
      f = bar.Lookup("pkg.bar.y")
      self.assertEqual("pkg.foo.X", f.type.name)


_Module = collections.namedtuple("_", ["module_name", "file_name"])


class PickledPyiLoaderTest(unittest.TestCase):

  PYTHON_VERSION = (2, 7)

  def setUp(self):
    self.options = config.Options.create(python_version=self.PYTHON_VERSION)
    self.loader = load_pytd.Loader(base_module=None, options=self.options)

  def _CreateFiles(self, tempdir):
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

  def _GetPath(self, tempdir, filename):
    return os.path.join(tempdir.path, filename)

  def _LoadAst(self, tempdir, module):
    self.options.tweak(pythonpath=[tempdir.path])
    self.options.tweak(module_name=module.module_name)
    return self.loader.load_file(
        self.options.module_name, self._GetPath(tempdir, module.file_name))

  def _PickleModules(self, tempdir, *modules):
    for module in modules:
      serialize_ast.StoreAst(
          self.loader._modules[module.module_name].ast,
          self._GetPath(tempdir, module.file_name + ".pickled"))

  def _LoadPickledModule(self, tempdir, module):
    pickle_loader = load_pytd.PickledPyiLoader(
        base_module=None, options=self.options, use_pickled_typeshed=False)
    return pickle_loader.load_file(
        module.module_name, self._GetPath(tempdir, module.file_name))

  def testLoadWithSameModuleName(self):
    with utils.Tempdir() as d:
      self._CreateFiles(tempdir=d)
      module1 = _Module(module_name="foo.bar.module1", file_name="module1.pyi")
      module2 = _Module(module_name="module2", file_name="module2.pyi")
      ast = self._LoadAst(tempdir=d, module=module1)
      self._PickleModules(d, module1, module2)
      pickled_ast_filename = self._GetPath(d, module1.file_name + ".pickled")
      result = serialize_ast.StoreAst(ast, pickled_ast_filename)
      self.assertIsNone(result)

      loaded_ast = self._LoadPickledModule(d, module1)
      self.assertTrue(loaded_ast)
      self.assertTrue(loaded_ast is not ast)
      self.assertTrue(ast.ASTeq(loaded_ast))
      loaded_ast.Visit(visitors.VerifyLookup())

  def testStarImport(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "class A(object): ...")
      d.create_file("bar.pyi", "from foo import *")
      foo = _Module(module_name="foo", file_name="foo.pyi")
      bar = _Module(module_name="bar", file_name="bar.pyi")
      self._LoadAst(d, module=bar)
      self._PickleModules(d, foo, bar)
      loaded_ast = self._LoadPickledModule(d, bar)
      loaded_ast.Visit(visitors.VerifyLookup())
      self.assertMultiLineEqual(pytd.Print(loaded_ast), textwrap.dedent("""\
        import foo

        bar.A = foo.A"""))

  def testFunctionAlias(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(): ...
        g = f
      """)
      foo = _Module(module_name="foo", file_name="foo.pyi")
      self._LoadAst(d, module=foo)
      self._PickleModules(d, foo)
      loaded_ast = self._LoadPickledModule(d, foo)
      g = loaded_ast.Lookup("foo.g")
      self.assertEqual(g.type.function, loaded_ast.Lookup("foo.f"))

  def testPackageRelativeImport(self):
    with utils.Tempdir() as d:
      d.create_file("pkg/foo.pyi", "class X: ...")
      d.create_file("pkg/bar.pyi", """
          from .foo import X
          y = ...  # type: X""")
      foo = _Module(module_name="pkg.foo", file_name="pkg/foo.pyi")
      bar = _Module(module_name="pkg.bar", file_name="pkg/bar.pyi")
      self._LoadAst(d, module=bar)
      self._PickleModules(d, foo, bar)
      loaded_ast = self._LoadPickledModule(d, bar)
      loaded_ast.Visit(visitors.VerifyLookup())


if __name__ == "__main__":
  unittest.main()
