"""Test errors.py."""

from pytype import errors

import unittest


class ErrorsTest(unittest.TestCase):

  def test_has_error(self):
    errorlog = errors.ErrorLog()
    self.assertFalse(errorlog.has_error())
    # A warning is part of the error log, but isn't severe.
    errorlog.warn(None, "A warning")
    self.assertEquals(1, len(errorlog))
    self.assertFalse(errorlog.has_error())
    # An error is severe.
    errorlog.error(None, "An error")
    self.assertEquals(2, len(errorlog))
    self.assertTrue(errorlog.has_error())


if __name__ == "__main__":
  unittest.main()
