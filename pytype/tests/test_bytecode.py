"""Tests for blocks.py."""


from pytype import blocks
from pytype.tests import test_inference
import unittest


class BytecodeTest(test_inference.InferenceTest):
  """Tests for process_code in blocks.py and VM integration."""

  def test_simple(self):
    # Disassembled from:
    # | return None
    code = self.make_code([
        0x64, 1, 0,  # 0 LOAD_CONST, arg=0 (None)
        0x53,  # 3 RETURN_VALUE
    ], name="simple")
    code = blocks.process_code(code)
    self.assertIsInstance(code, blocks.OrderedCode)


if __name__ == "__main__":
  unittest.main()
