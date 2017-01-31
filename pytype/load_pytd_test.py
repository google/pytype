"""Tests for load_pytd.py."""

import unittest

from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import pytd

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
      self.assertEquals("__builtin__.int", mod.Lookup("foo.x").type.cls.name)
      self.assertEquals("__builtin__.int", mod.Lookup("foo.x").type.name)

  @unittest.skip("automatic creation of __init__ only works with imports_map")
  def testNoInit(self):
    with utils.Tempdir() as d:
      d.create_directory("baz")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      self.assertTrue(loader.import_name("baz"))

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
      self.assertEquals("module2.Bar", f.return_type.cls.name)

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
      self.assertEquals("bar.Bar", f1.return_type.cls.name)
      self.assertEquals("foo.Foo", f2.return_type.cls.name)

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
      self.assertEquals("List[int]", pytd.Print(f.return_type))

  def testImportMapCongruence(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "X = ...  # type: int")
      foo_path = d.path + "/foo.pyi"
      # Map the same pyi file under two module paths.
      imports_map = {
          "foo": foo_path,
          "another/foo": foo_path,
          "empty1": "/dev/null",
          "empty2": "/dev/null",
      }
      # We cannot use tweak(imports_info=...) because that doesn't trigger
      # post-processing and we need an imports_map for the loader.
      self.options.imports_map = imports_map
      loader = load_pytd.Loader("base", self.options)
      normal = loader.import_name("foo")
      self.assertEquals("foo", normal.name)
      another = loader.import_name("another.foo")
      self.assertIs(normal, another)
      # Make sure that multiple modules using /dev/null are not treated as
      # congruent.
      empty1 = loader.import_name("empty1")
      empty2 = loader.import_name("empty2")
      self.assertIsNot(empty1, empty2)
      self.assertEquals("empty1", empty1.name)
      self.assertEquals("empty2", empty2.name)


if __name__ == "__main__":
  unittest.main()
