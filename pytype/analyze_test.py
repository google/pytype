"""Tests for analyze.py."""


from pytype import analyze
from pytype import config

import unittest


class AnalyzeTest(unittest.TestCase):
  """Tests for analyze.py."""

  def testFilepathToModule(self):
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
      options = config.Options.create(pythonpath=pythonpath)
      module = analyze.get_module_name(filename, options)
      self.assertEqual(module, expected)


if __name__ == "__main__":
  unittest.main()
