"""Tests for load_pytd.py."""

import os
import sys
import unittest

from pytype import load_pytd
from pytype import utils

import unittest


class ImportPathsTest(unittest.TestCase):
  """Tests for load_pytd.py."""

  PYTHON_VERSION = (2, 7)

  def testBuiltinSys(self):
    loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION)
    ast = loader.import_name("sys")
    self.assertTrue(ast.Lookup("sys.exit"))

  def testBasic(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pytd", "def foo(x:int) -> str")
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path])
      ast = loader.import_name("path.to.some.module")
      self.assertTrue(ast.Lookup("path.to.some.module.foo"))

  def testCustomExtension(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.dat", "def foo() -> str")
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path],
                                find_pytd_import_ext=".dat"
                               )
      ast = loader.import_name("path.to.some.module")
      self.assertTrue(ast.Lookup("path.to.some.module.foo"))

  def testStripPrefix(self):
    with utils.Tempdir() as d:
      d.create_file("path/to/some/module.pytd", "def foo() -> str")
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path],
                                import_drop_prefixes=("extra.long",
                                                      "even.longer")
                               )
      self.assertTrue(loader.import_name("extra.long.path.to.some.module"))
      self.assertTrue(loader.import_name("even.longer.path.to.some.module"))

  def testPath(self):
    with utils.Tempdir() as d1:
      with utils.Tempdir() as d2:
        d1.create_file("dir1/module1.pytd", "def foo1() -> str")
        d2.create_file("dir2/module2.pytd", "def foo2() -> str")
        loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                  pythonpath=[d1.path, d2.path])
        module1 = loader.import_name("dir1.module1")
        module2 = loader.import_name("dir2.module2")
        self.assertTrue(module1.Lookup("dir1.module1.foo1"))
        self.assertTrue(module2.Lookup("dir2.module2.foo2"))

  def testInit(self):
    with utils.Tempdir() as d1:
      d1.create_file("baz/__init__.pytd", "x = ... # type: int")
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d1.path])
      self.assertTrue(loader.import_name("baz").Lookup("baz.x"))

  @unittest.skip("automatic creation of __init__ only works with imports_map")
  def testNoInit(self):
    with utils.Tempdir() as d:
      d.create_directory("baz")
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path])
      self.assertTrue(loader.import_name("baz"))

  def testStdlib(self):
    loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION)
    ast = loader.import_name("StringIO")
    self.assertTrue(ast.Lookup("StringIO.StringIO"))

  def testDeepDependency(self):
    with utils.Tempdir() as d:
      d.create_file("module1.pytd", "def get_bar() -> module2.Bar")
      d.create_file("module2.pytd", "class Bar:\n  pass")
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path])
      module1 = loader.import_name("module1")
      f, = module1.Lookup("module1.get_bar").signatures
      self.assertEquals("module2.Bar", f.return_type.cls.name)

  def testCircularDependency(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pytd", """
        def get_bar() -> bar.Bar
        class Foo:
          pass
      """)
      d.create_file("bar.pytd", """
        def get_foo() -> foo.Foo
        class Bar:
          pass
      """)
      loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path])
      foo = loader.import_name("foo")
      bar = loader.import_name("bar")
      f1, = foo.Lookup("foo.get_bar").signatures
      f2, = bar.Lookup("bar.get_foo").signatures
      self.assertEquals("bar.Bar", f1.return_type.cls.name)
      self.assertEquals("foo.Foo", f2.return_type.cls.name)

  def testRelative(self):
    with utils.Tempdir() as d:
      d.create_file("__init__.pytd", "base = ...  # type: ?")
      d.create_file("path/__init__.pytd", "path = ...  # type: ?")
      d.create_file("path/to/__init__.pytd", "to = ...  # type: ?")
      d.create_file("path/to/some/__init__.pytd", "some = ...  # type: ?")
      d.create_file("path/to/some/module.pytd", "")
      loader = load_pytd.Loader("path.to.some.module",
                                python_version=self.PYTHON_VERSION,
                                pythonpath=[d.path])
      some = loader.import_relative(1)
      to = loader.import_relative(2)
      path = loader.import_relative(3)
      # Python doesn't allow "...." here, so don't test import_relative(4).
      self.assertTrue(some.Lookup("path.to.some.some"))
      self.assertTrue(to.Lookup("path.to.to"))
      self.assertTrue(path.Lookup("path.path"))

  def testSmokePyTD(self):
    """Smoke test to ensure all *.pytd files load properly."""
    loader = load_pytd.Loader("base", python_version=self.PYTHON_VERSION)
    pytd_dir = os.path.join(os.path.dirname(load_pytd.__file__), "pytd")
    for builtins_subdir in ("builtins", "stdlib"):
      subdir_path = os.path.join(pytd_dir, builtins_subdir)
      for dirpath, _, files in os.walk(subdir_path):
        # We don't need to know the directory we're in because these are builtin
        # .pytd files and load_pytd.import_name takes care of looking in
        # multiple directories. But because there can be subdirectories, we need
        # to construct an appropriate module name.
        rel_dirpath = os.path.relpath(dirpath, start=subdir_path)
        if rel_dirpath in [".", ""]:
          module_prefix = ""
        else:
          module_prefix = rel_dirpath.replace(os.sep, ".") + "."
        for name in files:
          module_name, ext = os.path.splitext(module_prefix + name)
          if ext == ".pytd":
            # We could do something fancier with try/except, but for
            # now, just print out each module as we load it.
            print >>sys.stderr, "***Loading", module_name
            self.assertTrue(loader.import_name(module_name),
                            msg="Failed loading " + module_name)


if __name__ == "__main__":
  unittest.main()
