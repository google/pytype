"""Tests for pickle_utils.py."""

from pytype.imports import pickle_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class TestPickle(test_base.UnitTest):
  """Test loading and saving pickled pytds."""

  def test_load_pickle_from_file(self):
    d1 = {1, 2j, "3"}
    with test_utils.Tempdir() as d:
      filename = d.create_file("foo.pickle")
      pickle_utils.SavePickle(d1, filename)
      d2 = pickle_utils.LoadPickle(filename)
    self.assertEqual(d1, d2)

  def test_load_pickle_from_compressed_file(self):
    d1 = {1, 2j, "3"}
    with test_utils.Tempdir() as d:
      filename = d.create_file("foo.pickle.gz")
      pickle_utils.SavePickle(d1, filename, compress=True)
      d2 = pickle_utils.LoadPickle(filename, compress=True)
    self.assertEqual(d1, d2)


if __name__ == "__main__":
  test_base.main()
