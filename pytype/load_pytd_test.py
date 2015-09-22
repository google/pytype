"""Tests for load_pytd.py."""

import os
import sys
import tempfile
import unittest

from pytype import imports_map_loader
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
      d1.create_file("baz/__init__.pytd", "x: int")
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
      d.create_file("__init__.pytd", "base: ?")
      d.create_file("path/__init__.pytd", "path: ?")
      d.create_file("path/to/__init__.pytd", "to: ?")
      d.create_file("path/to/some/__init__.pytd", "some: ?")
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
      for _, _, files in os.walk(
          os.path.join(pytd_dir, builtins_subdir)):
        # We don't need to know the directory we're in because these are builtin
        # .pytd files and load_pytd.import_name takes care of looking in
        # multiple directories.
        for name in files:
          module_name, ext = os.path.splitext(name)
          if ext == ".pytd":
            # We could do something fancier with try/except, but for
            # now, just print out each module as we load it.
            print >>sys.stderr, "***Loading", module_name
            self.assertTrue(loader.import_name(module_name),
                            msg="Failed loading " + module_name)

  def testFilePaths(self):
    """Test the various permutations of output from FilePaths."""
    # Test both repr and str, in case there's still any test that depends
    # on the precise output form. Note that the output form is similar to
    # the args to _MakeFilePaths.
    for to_str_fn in repr, str:
      self.assertEqual(
          "FilePaths('abc.xyz')",
          to_str_fn(imports_map_loader.FilePaths(path="abc.xyz",
                                                 short_path="abc.xyz")))
      self.assertEqual(
          "FilePaths(short_path='mmm', path='abcdefg')",
          to_str_fn(imports_map_loader.FilePaths(short_path="mmm",
                                                 path="abcdefg")))
      self.assertEqual(
          "FilePaths('prefix/' + 'common' + '.suffix')",
          to_str_fn(imports_map_loader.FilePaths(short_path="common",
                                                 path="prefix/common.suffix")))
      self.assertEqual(
          "FilePaths('prefix/' + 'common' + '')",
          to_str_fn(imports_map_loader.FilePaths(short_path="common",
                                                 path="prefix/common")))
      self.assertEqual(
          "FilePaths('' + 'common' + '.suffix')",
          to_str_fn(imports_map_loader.FilePaths(short_path="common",
                                                 path="common.suffix")))
      # In the following, note the stuttered "path/to/"
      self.assertEqual(
          "FilePaths('BINDIR/bin/path/to/' + 'path/to/src/b.py' + '~~pytype')",
          to_str_fn(imports_map_loader.FilePaths(
              short_path="path/to/src/b.py",
              path="BINDIR/bin/path/to/path/to/src/b.py~~pytype")))
      self.assertEqual(
          "FilePaths('BINDIR/bin/path/to/' + 'path/to/src/b.py' + '~~pytype')",
          to_str_fn(_MakeFilePaths(
              "BINDIR/bin/path/to/",
              "path/to/src/b.py", "~~pytype")))

  @unittest.skip("Needs to be updated")
  def testReadImportsInfo(self):
    """Test the reading an imports_info file into ImportsInfo."""
    # TODO(pludemann): This is slightly out of date and doesn't cover all
    #                  the fields in ImportsInfo; but it does exercise the
    #                  various ways of grouping the input into ImportsInfo.
    with tempfile.NamedTemporaryFile() as fi:
      fi.write("""\
label "path/to/b_lib~~pytype"

src_to_out "path/to/src/b.py" "BINDIR/bin/path/to/path/to/src/b.py~~pytype"

transitive "path/to/src2/d.py" "path/to/src2/d.py"
transitive "path/to/src/__init__.py" "path/to/src/__init__.py"
transitive "path/to/src/c.py" "path/to/src/c.py"
transitive "path/to/src/c2.py" "path/to/src/c2.py"
transitive "path/to/src/c3.py" "BINDIR/bin/path/to/src/c3.py"

python_deps "path/to/d_lib" "path/to/src2/d.py" "path/to/src2/d.py"
python_deps "path/to/c_lib" "path/to/src/__init__.py" "path/to/src/__init__.py" "path/to/src/c.py" "path/to/src/c.py" "path/to/src/c2.py" "path/to/src/c2.py" "path/to/src/c3.py" "BINDIR/bin/path/to/src/c3.py"

pytype_deps "path/to/d_lib~~pytype" "path/to/path/to/src2/d.py~~pytype" "BINDIR/bin/path/to/path/to/src2/d.py~~pytype" "path/to/d_lib~~pytype.imports_info" "BINDIR/bin/path/to/d_lib~~pytype.imports_info"
pytype_deps "path/to/c_lib~~pytype" "path/to/path/to/src/__init__.py~~pytype" "BINDIR/bin/path/to/path/to/src/__init__.py~~pytype" "path/to/path/to/src/c.py~~pytype" "BINDIR/bin/path/to/path/to/src/c.py~~pytype" "path/to/path/to/src/c2.py~~pytype" "BINDIR/bin/path/to/path/to/src/c2.py~~pytype" "path/to/path/to/src/c3.py~~pytype" "BINDIR/bin/path/to/path/to/src/c3.py~~pytype" "path/to/c_lib~~pytype.imports_info" "BINDIR/bin/path/to/c_lib~~pytype.imports_info"

python_dep_files "path/to/src2/d.py" "path/to/src2/d.py"
python_dep_files "path/to/src/__init__.py" "path/to/src/__init__.py"
python_dep_files "path/to/src/c.py" "path/to/src/c.py"
python_dep_files "path/to/src/c2.py" "path/to/src/c2.py"
python_dep_files "path/to/src/c3.py" "BINDIR/bin/path/to/src/c3.py"

pytype_dep_files "path/to/path/to/src2/d.py~~pytype" "BINDIR/bin/path/to/path/to/src2/d.py~~pytype"
pytype_dep_files "path/to/d_lib~~pytype.imports_info" "BINDIR/bin/path/to/d_lib~~pytype.imports_info"
pytype_dep_files "path/to/path/to/src/__init__.py~~pytype" "BINDIR/bin/path/to/path/to/src/__init__.py~~pytype"
pytype_dep_files "path/to/path/to/src/c.py~~pytype" "BINDIR/bin/path/to/path/to/src/c.py~~pytype"
pytype_dep_files "path/to/path/to/src/c2.py~~pytype" "BINDIR/bin/path/to/path/to/src/c2.py~~pytype"
pytype_dep_files "path/to/path/to/src/c3.py~~pytype" "BINDIR/bin/path/to/path/to/src/c3.py~~pytype"
pytype_dep_files "path/to/c_lib~~pytype.imports_info" "BINDIR/bin/path/to/c_lib~~pytype.imports_info"
""")
      fi.seek(0)  # ready for reading
      self.assertEqual(
          load_pytd._read_imports_info(fi.name),
          load_pytd.ImportsInfo(
              label="path/to/b_lib~~pytype",
              src_to_out=[
                  _MakeFilePaths("BINDIR/bin/path/to/", "path/to/src/b.py", "~~pytype")],
              transitive=[
                  _MakeFilePaths("", "path/to/src/__init__.py", ""),
                  _MakeFilePaths("", "path/to/src/c.py", ""),
                  _MakeFilePaths("", "path/to/src/c2.py", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/src/c3.py", ""),
                  _MakeFilePaths("", "path/to/src2/d.py", "")],
              python_deps={
                  "path/to/c_lib": [
                      _MakeFilePaths("", "path/to/src/__init__.py", ""),
                      _MakeFilePaths("", "path/to/src/c.py", ""),
                      _MakeFilePaths("", "path/to/src/c2.py", ""),
                      _MakeFilePaths("BINDIR/bin/", "path/to/src/c3.py", "")],
                  "path/to/d_lib": [
                      _MakeFilePaths("", "path/to/src2/d.py", "")]},
              pytype_deps={
                  "path/to/c_lib~~pytype": [
                      _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/__init__.py~~pytype", ""),
                      _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/c.py~~pytype", ""),
                      _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/c2.py~~pytype", ""),
                      _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/c3.py~~pytype", ""),
                      _MakeFilePaths("BINDIR/bin/", "path/to/c_lib~~pytype.imports_info", "")],
                  "path/to/d_lib~~pytype": [
                      _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src2/d.py~~pytype", ""),
                      _MakeFilePaths("BINDIR/bin/", "path/to/d_lib~~pytype.imports_info", "")]},
              python_dep_files=[
                  _MakeFilePaths("", "path/to/src/__init__.py", ""),
                  _MakeFilePaths("", "path/to/src/c.py", ""),
                  _MakeFilePaths("", "path/to/src/c2.py", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/src/c3.py", ""),
                  _MakeFilePaths("", "path/to/src2/d.py", "")],
              pytype_dep_files=[
                  _MakeFilePaths("BINDIR/bin/", "path/to/c_lib~~pytype.imports_info", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/d_lib~~pytype.imports_info", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/__init__.py~~pytype", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/c.py~~pytype", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/c2.py~~pytype", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src/c3.py~~pytype", ""),
                  _MakeFilePaths("BINDIR/bin/", "path/to/path/to/src2/d.py~~pytype", "")]))


def _MakeFilePaths(prefix, common, suffix):
  return imports_map_loader.FilePaths(path=prefix + common + suffix,
                                      short_path=common)


if __name__ == "__main__":
  unittest.main()
