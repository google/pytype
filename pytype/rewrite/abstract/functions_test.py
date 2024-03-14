from typing import Sequence

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import functions
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest


class FakeFrame:

  def __init__(self):
    self.child_frames = []
    self.final_locals = {}

  def make_child_frame(self, func, initial_locals):
    self.child_frames.append((func, initial_locals))
    return self

  def run(self):
    pass

  def get_return_value(self):
    return base.ANY


def _get_const(src: str):
  module_code = test_utils.parse(src)
  return module_code.consts[0]


class SignatureTest(unittest.TestCase):

  def test_from_code(self):
    func_code = _get_const("""
      def f(x, /, *args, y, **kwargs):
        pass
    """)
    signature = functions.Signature.from_code('f', func_code)
    self.assertEqual(repr(signature), 'def f(x, /, *args, y, **kwargs)')

  def test_map_args(self):
    signature = functions.Signature('f', ('x', 'y'))
    x = base.PythonConstant('x').to_variable()
    y = base.PythonConstant('y').to_variable()
    args = signature.map_args(functions.Args([x, y]))
    self.assertEqual(args, {'x': x, 'y': y})

  def test_fake_args(self):
    signature = functions.Signature('f', ('x', 'y'))
    args = signature.make_fake_args()
    self.assertEqual(set(args), {'x', 'y'})


class InterpreterFunctionTest(unittest.TestCase):

  def test_init(self):
    func_code = _get_const("""
      def f(x, /, *args, y, **kwargs):
        pass
    """)
    f = functions.InterpreterFunction(
        name='f', code=func_code, enclosing_scope=(),
        parent_frame=FakeFrame())
    self.assertEqual(len(f.signatures), 1)
    self.assertEqual(repr(f.signatures[0]), 'def f(x, /, *args, y, **kwargs)')

  def test_map_args(self):
    func_code = _get_const('def f(x): ...')
    f = functions.InterpreterFunction(
        name='f', code=func_code, enclosing_scope=(), parent_frame=FakeFrame())
    x = base.PythonConstant(0).to_variable()
    mapped_args = f.map_args(functions.Args(posargs=(x,)))
    self.assertEqual(mapped_args.signature, f.signatures[0])
    self.assertEqual(mapped_args.argdict, {'x': x})

  def test_call_with_mapped_args(self):
    f = functions.InterpreterFunction(
        name='f', code=_get_const('def f(x): ...'), enclosing_scope=(),
        parent_frame=FakeFrame())
    x = base.PythonConstant(0).to_variable()
    mapped_args = functions.MappedArgs(f.signatures[0], {'x': x})
    frame = f.call_with_mapped_args(mapped_args)
    assert_type(frame, FakeFrame)
    self.assertIsInstance(frame, FakeFrame)

  def test_call(self):
    f = functions.InterpreterFunction(
        name='f', code=_get_const('def f(): ...'), enclosing_scope=(),
        parent_frame=FakeFrame())
    frame = f.call(functions.Args())
    assert_type(frame, FakeFrame)
    self.assertIsInstance(frame, FakeFrame)

  def test_analyze(self):
    f = functions.InterpreterFunction(
        name='f', code=_get_const('def f(): ...'), enclosing_scope=(),
        parent_frame=FakeFrame())
    frames = f.analyze()
    assert_type(frames, Sequence[FakeFrame])
    self.assertEqual(len(frames), 1)
    self.assertIsInstance(frames[0], FakeFrame)


class BoundFunctionTest(unittest.TestCase):

  def test_call(self):
    f = functions.InterpreterFunction(
        name='f', code=_get_const('def f(self): ...'), enclosing_scope=(),
        parent_frame=FakeFrame())
    callself = base.PythonConstant(42)
    bound_f = f.bind_to(callself)
    frame = bound_f.call(functions.Args())
    assert_type(frame, FakeFrame)
    argdict = frame.child_frames[0][1]
    self.assertEqual(argdict, {'self': callself.to_variable()})

  def test_analyze(self):
    f = functions.InterpreterFunction(
        name='f', code=_get_const('def f(self): ...'), enclosing_scope=(),
        parent_frame=FakeFrame())
    callself = base.PythonConstant(42)
    bound_f = f.bind_to(callself)
    frames = bound_f.analyze()
    assert_type(frames, Sequence[FakeFrame])
    self.assertEqual(len(frames), 1)
    argdict = frames[0].child_frames[0][1]
    self.assertEqual(argdict, {'self': callself.to_variable()})


if __name__ == '__main__':
  unittest.main()
