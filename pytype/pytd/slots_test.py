"""Tests for slots.py."""

import unittest

from pytype.pytd import slots


class TestPytd(unittest.TestCase):
  """Test the operator mappings in slots.py."""

  def testReverseSlotMapping(self):
    slots.ReverseSlotMapping().get("__radd__")  # smoke test

if __name__ == "__main__":
  unittest.main()
