"""Tests for slots.py."""

import unittest
from pytype.pytd import slots


class TestPytd(unittest.TestCase):
  """Test the operator mappings in slots.py."""

  def testBinaryOperatorMapping(self):
    slots.BinaryOperatorMapping().get("ADD")  # smoke test

  def testCompareFunctionMapping(self):
    indexes = slots.CompareFunctionMapping().keys()
    # Assert that we have the six basic comparison ops (<, <=, ==, !=, >, >=).
    for i in range(6):
      self.assertIn(i, indexes)


if __name__ == "__main__":
  unittest.main()
