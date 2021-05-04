"""Tests for typeshed.py."""

import os

from pytype import file_utils
from pytype.pytd import builtins
from pytype.pytd import typeshed
from pytype.pytd.parse import parser_test_base
from pytype.tests import test_base


class TestTypeshedLoading(parser_test_base.ParserTest):
  """Test the code for loading files from typeshed."""

  def setUp(self):
    super().setUp()
    self.ts = typeshed.Typeshed()

  def test_get_typeshed_file(self):
    filename, data = self.ts.get_module_file(
        "stdlib", "errno", self.python_version)
    self.assertEqual("errno.pyi", os.path.basename(filename))
    self.assertIn("errorcode", data)

  def test_get_typeshed_dir(self):
    filename, data = self.ts.get_module_file(
        "stdlib", "logging", self.python_version)
    self.assertEqual("__init__.pyi", os.path.basename(filename))
    self.assertIn("LogRecord", data)

  def test_parse_type_definition(self):
    filename, ast = typeshed.parse_type_definition(
        "stdlib", "_random", self.python_version)
    self.assertEqual(os.path.basename(filename), "_random.pyi")
    self.assertIn("_random.Random", [cls.name for cls in ast.classes])

  def test_get_typeshed_missing(self):
    if not self.ts.missing:
      return  # nothing to test
    self.assertIn(os.path.join("stdlib", "pytypecanary"), self.ts.missing)
    _, data = self.ts.get_module_file(
        "stdlib", "pytypecanary", self.python_version)
    self.assertEqual(data, builtins.DEFAULT_SRC)

  def test_get_google_only_module_names(self):
    if not self.ts.missing:
      return  # nothing to test
    modules = self.ts.get_all_module_names(self.python_version)
    self.assertIn("pytypecanary", modules)

  def test_get_all_module_names_2(self):
    modules = self.ts.get_all_module_names((2, 7))
    self.assertIn("collections", modules)
    self.assertIn("csv", modules)
    self.assertIn("ctypes", modules)
    self.assertIn("xml.etree.ElementTree", modules)
    self.assertIn("six.moves", modules)

  def test_get_all_module_names_3(self):
    modules = self.ts.get_all_module_names((3, 6))
    self.assertIn("asyncio", modules)
    self.assertIn("collections", modules)
    self.assertIn("configparser", modules)

  def test_get_pytd_paths(self):
    # Set TYPESHED_HOME to pytype's internal typeshed copy.
    old_env = os.environ.copy()
    os.environ["TYPESHED_HOME"] = self.ts.root
    try:
      # Check that get_pytd_paths() works with a typeshed installation that
      # reads from TYPESHED_HOME.

      paths = {p.rsplit("pytype/", 1)[-1]
               for p in self.ts.get_pytd_paths(self.python_version)}
      self.assertSetEqual(paths, {"stubs/builtins/3", "stubs/stdlib/3"})
    finally:
      os.environ = old_env

  def test_read_blacklist(self):
    for filename in self.ts.read_blacklist():
      self.assertTrue(filename.startswith("stdlib") or
                      filename.startswith("stubs"))

  def test_blacklisted_modules(self):
    for module_name in self.ts.blacklisted_modules([2, 7]):
      self.assertNotIn("/", module_name)
    for module_name in self.ts.blacklisted_modules([3, 6]):
      self.assertNotIn("/", module_name)

  def test_carriage_return(self):
    # _env_home is used in preference to _root, so make sure it's unset.
    self.ts._env_home = None
    self.ts._stdlib_versions["foo"] = ((3, 8), None, False)
    with file_utils.Tempdir() as d:
      d.create_file("stdlib/foo.pyi", b"x: int\r\n")
      self.ts._root = d.path
      _, src = self.ts.get_module_file("stdlib", "foo", (3, 8))
    self.assertEqual(src, "x: int\n")

  def test_carriage_return_custom_root(self):
    self.ts._stdlib_versions["foo"] = ((3, 8), None, False)
    with file_utils.Tempdir() as d:
      d.create_file("stdlib/foo.pyi", b"x: int\r\n")
      self.ts._env_home = d.path
      _, src = self.ts.get_module_file("stdlib", "foo", (3, 8))
    self.assertEqual(src, "x: int\n")


class TestTypeshedParsing(test_base.TargetPython27FeatureTest):
  """Tests a handful of typeshed modules.

  The list was generated using
      ls ../typeshed/stdlib/2/ | sort -R | sed s/.pyi$// | head -16
  """

  def setUp(self):
    super().setUp()
    self.ConfigureOptions(module_name="base")

  def test_quopri(self):
    self.assertTrue(self.loader.import_name("quopri"))

  def test_rfc822(self):
    self.assertTrue(self.loader.import_name("rfc822"))

  def test_email(self):
    self.assertTrue(self.loader.import_name("email"))

  def test_robotparser(self):
    self.assertTrue(self.loader.import_name("robotparser"))

  def test_md5(self):
    self.assertTrue(self.loader.import_name("md5"))

  def test_uuid(self):
    self.assertTrue(self.loader.import_name("uuid"))

  def test_decimal(self):
    self.assertTrue(self.loader.import_name("decimal"))

  def test_select(self):
    self.assertTrue(self.loader.import_name("select"))

  def test__ast(self):
    self.assertTrue(self.loader.import_name("_ast"))

  def test_importlib(self):
    self.assertTrue(self.loader.import_name("importlib"))

  def test_SocketServer(self):
    self.assertTrue(self.loader.import_name("SocketServer"))

  def test_thread(self):
    self.assertTrue(self.loader.import_name("thread"))

  def test_runpy(self):
    self.assertTrue(self.loader.import_name("runpy"))

  def test_hotshot(self):
    self.assertTrue(self.loader.import_name("_hotshot"))

  def test_imp(self):
    self.assertTrue(self.loader.import_name("imp"))


test_base.main(globals(), __name__ == "__main__")
