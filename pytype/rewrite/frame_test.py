from pytype.pyc import opcodes
from pytype.rewrite import frame as frame_lib
from pytype.rewrite.tests import test_utils

import unittest


class FrameTest(unittest.TestCase):

  def test_run_no_crash(self):
    code = test_utils.FakeOrderedCode([[opcodes.LOAD_CONST(0, 0, None, None),
                                        opcodes.RETURN_VALUE(1, 0)]])
    frame = frame_lib.Frame(code.Seal(), {}, {})
    frame.run()

  def test_load_const(self):
    code = test_utils.FakeOrderedCode([[opcodes.LOAD_CONST(0, 0, None, 42),
                                        opcodes.RETURN_VALUE(1, 0)]])
    frame = frame_lib.Frame(code.Seal(), {}, {})
    frame.step()
    self.assertEqual(len(frame._stack), 1)
    self.assertEqual(frame._stack[0].get_atomic_value(), 42)


if __name__ == '__main__':
  unittest.main()
