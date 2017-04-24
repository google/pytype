"""Tests for magic.py."""


from pytype.pyc import magic
import unittest


class TestMagic(unittest.TestCase):
  """Tests for the functions in magic.py."""

  def test_to_version(self):
    self.assertEquals(magic.magic_word_to_version('\x03\xf3'), (2, 7))
    self.assertEquals(magic.magic_word_to_version('\xee\x0c'), (3, 4))
    self.assertEquals(magic.magic_word_to_version('\x17\x0d'), (3, 5))
    self.assertEquals(magic.magic_word_to_version('\x33\x0d'), (3, 6))

if __name__ == '__main__':
  unittest.main()
