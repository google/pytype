"""Tests for magic.py."""

from pytype.pyc import magic
import unittest


class TestMagic(unittest.TestCase):
  """Tests for the functions in magic.py."""

  def test_to_version(self):
    self.assertEqual(magic.magic_word_to_version(b'\x03\xf3'), (2, 7))
    self.assertEqual(magic.magic_word_to_version(b'\xee\x0c'), (3, 4))
    self.assertEqual(magic.magic_word_to_version(b'\x17\x0d'), (3, 5))
    self.assertEqual(magic.magic_word_to_version(b'\x33\x0d'), (3, 6))
    self.assertEqual(magic.magic_word_to_version(b'\x42\x0d'), (3, 7))


if __name__ == '__main__':
  unittest.main()
