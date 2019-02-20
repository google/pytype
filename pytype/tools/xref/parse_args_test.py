"""Tests for parse_args.py."""

from pytype import file_utils
from pytype.tools.xref import parse_args
import unittest


class TestParseArgs(unittest.TestCase):
  """Test parse_args.parse_args."""

  def test_parse_filename(self):
    args, _, _ = parse_args.parse_args(["a.py"])
    self.assertEqual(args.inputs, ["a.py"])

  def test_parse_no_filename(self):
    with self.assertRaises(SystemExit):
      parse_args.parse_args([])

  def test_kythe_args(self):
    _, kythe_args, _ = parse_args.parse_args(
        ["a.py",
         "--kythe_corpus", "foo",
         "--kythe_root", "bar"])
    self.assertEqual(kythe_args.corpus, "foo")
    self.assertEqual(kythe_args.root, "bar")

  def test_imports_info(self):
    # The code reads and validates an import map within pytype's setup, so we
    # need to provide a syntactically valid one as a file.
    with file_utils.Tempdir() as d:
      pyi_file = d.create_file("baz.pyi")
      imports_info = d.create_file("foo", "bar %s" % pyi_file)
      args, _, opts = parse_args.parse_args(
          ["a.py", "--imports_info", imports_info])
      self.assertEqual(args.imports_info, imports_info)
      self.assertEqual(opts.imports_map, {"bar": pyi_file})
      self.assertTrue(opts.use_pickled_files)


if __name__ == "__main__":
  unittest.main()
