"""Tests for module_utils.py."""

import os

from pytype import file_utils
from pytype import module_utils

import unittest


class ModuleUtilsTest(unittest.TestCase):
  """Test module utilities."""

  def test_get_absolute_name(self):
    test_cases = [
        ("x.y", "a.b", "x.y.a.b"),
        ("", "a.b", "a.b"),
        ("x.y", ".a.b", "x.y.a.b"),
        ("x.y", "..a.b", "x.a.b"),
        ("x.y", "...a.b", None),
    ]
    for prefix, name, expected in test_cases:
      self.assertEqual(module_utils.get_absolute_name(prefix, name), expected)

  def test_path_to_module_name(self):
    self.assertIsNone(module_utils.path_to_module_name("../foo.py"))
    self.assertEqual("x.y.z", module_utils.path_to_module_name("x/y/z.pyi"))
    self.assertEqual("x.y.z", module_utils.path_to_module_name("x/y/z.pytd"))
    self.assertEqual("x.y.z",
                     module_utils.path_to_module_name("x/y/z/__init__.pyi"))


# Because TestInferModule expands a lot of paths:
expand = file_utils.expand_path


class TestInferModule(unittest.TestCase):
  """Test module_utils.infer_module."""

  def assert_module_equal(self, module, path, target, name, kind="Local"):
    self.assertEqual(module.path.rstrip(os.sep), path.rstrip(os.sep))
    self.assertEqual(module.target, target)
    self.assertEqual(module.name, name)
    self.assertEqual(module.kind, kind)

  def test_simple_name(self):
    mod = module_utils.infer_module(expand("foo/bar.py"), [expand("foo")])
    self.assert_module_equal(mod, expand("foo"), "bar.py", "bar")

  def test_name_in_package(self):
    mod = module_utils.infer_module(expand("foo/bar/baz.py"), [expand("foo")])
    self.assert_module_equal(mod, expand("foo"), "bar/baz.py", "bar.baz")

  def test_multiple_paths(self):
    pythonpath = [expand("foo"), expand("bar/baz"), expand("bar")]
    mod = module_utils.infer_module(expand("bar/baz/qux.py"), pythonpath)
    self.assert_module_equal(mod, expand("bar/baz"), "qux.py", "qux")
    mod = module_utils.infer_module(expand("bar/qux.py"), pythonpath)
    self.assert_module_equal(mod, expand("bar"), "qux.py", "qux")

  def test_not_found(self):
    mod = module_utils.infer_module(expand("bar/baz.py"), ["foo"])
    expected_target = expand("bar/baz.py")
    expected_name, _ = os.path.splitext(expected_target.replace(os.sep, "."))
    self.assert_module_equal(mod, "", expected_target, expected_name)


if __name__ == "__main__":
  unittest.main()
