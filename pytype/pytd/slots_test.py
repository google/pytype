"""Tests for slots.py."""

from pytype.pytd import slots
import unittest


class TestPytd(unittest.TestCase):
  """Test the operator mappings in slots.py."""

  def testReverseNameMapping(self):
    for operator in ("add", "and", "div", "divmod", "floordiv",
                     "lshift", "matmul", "mod", "mul", "or",
                     "pow", "rshift", "sub", "truediv", "xor"):
      normal = "__%s__" % operator
      reverse = "__r%s__" % operator
      self.assertEqual(slots.REVERSE_NAME_MAPPING[normal], reverse)


if __name__ == "__main__":
  unittest.main()
