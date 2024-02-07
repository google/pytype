import sys
import textwrap

from pytype.blocks import blocks
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.rewrite import abstract
from pytype.rewrite import frame as frame_lib
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils

import unittest


def _parse(src: str) -> blocks.OrderedCode:
  code = pyc.compile_src(
      src=textwrap.dedent(src),
      python_version=sys.version_info[:2],
      python_exe=None,
      filename='<inline>',
      mode='exec',
  )
  ordered_code, unused_block_graph = blocks.process_code(code)
  return ordered_code


class FrameTest(unittest.TestCase):

  def test_run_no_crash(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, None), opcodes.RETURN_VALUE(1, 0)]
    code = test_utils.FakeOrderedCode([block], [None])
    frame = frame_lib.Frame(code.Seal(), {}, {})
    frame.run()

  def test_load_const(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, 42), opcodes.RETURN_VALUE(1, 0)]
    code = test_utils.FakeOrderedCode([block], [42])
    frame = frame_lib.Frame(code.Seal(), {}, {})
    frame.step()
    self.assertEqual(len(frame._stack), 1)
    constant = frame._stack.top().get_atomic_value()
    self.assertEqual(constant, abstract.PythonConstant(42))

  def test_store_local(self):
    code = _parse('x = 42')
    frame = frame_lib.Frame(code, {}, {})
    frame.run()
    self.assertEqual(set(frame.final_locals), {'x'})
    self.assertEqual(frame.final_locals['x'].get_atomic_value(),
                     abstract.PythonConstant(42))


class StackTest(unittest.TestCase):

  def test_push(self):
    s = frame_lib._DataStack()
    var = variables.Variable.from_value(5)
    s.push(var)
    self.assertEqual(s._stack, [var])

  def test_pop(self):
    s = frame_lib._DataStack()
    var = variables.Variable.from_value(5)
    s.push(var)
    popped = s.pop()
    self.assertEqual(popped, var)
    self.assertFalse(s._stack)

  def test_top(self):
    s = frame_lib._DataStack()
    var = variables.Variable.from_value(5)
    s.push(var)
    top = s.top()
    self.assertEqual(top, var)
    self.assertEqual(s._stack, [var])

  def test_bool(self):
    s = frame_lib._DataStack()
    self.assertFalse(s)
    s.push(variables.Variable.from_value(5))
    self.assertTrue(s)

  def test_len(self):
    s = frame_lib._DataStack()
    self.assertEqual(len(s), 0)  # pylint: disable=g-generic-assert
    s.push(variables.Variable.from_value(5))
    self.assertEqual(len(s), 1)


if __name__ == '__main__':
  unittest.main()
