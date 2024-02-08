from typing import Dict, cast

from pytype.pyc import opcodes
from pytype.rewrite import abstract
from pytype.rewrite import frame as frame_lib
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest


def _make_frame(src: str, name: str = '__main__') -> frame_lib.Frame:
  code = test_utils.parse(src)
  return frame_lib.Frame(name, code, {}, {})


class LocalsAndGlobalsTest(unittest.TestCase):

  def test_store_local_in_module_frame(self):
    frame = _make_frame('', name='__main__')
    frame.step()
    var = variables.Variable.from_value(abstract.PythonConstant(5))
    frame.store_local('x', var)
    stored = frame.load_local('x')
    self.assertEqual(stored, var.with_name('x'))
    self.assertEqual(stored, frame.load_global('x'))

  def test_store_local_in_nonmodule_frame(self):
    frame = _make_frame('', name='f')
    frame.step()
    var = variables.Variable.from_value(abstract.PythonConstant(5))
    frame.store_local('x', var)
    stored = frame.load_local('x')
    self.assertEqual(stored, var.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_global('x')

  def test_store_global_in_module_frame(self):
    frame = _make_frame('', name='__main__')
    frame.step()
    var = variables.Variable.from_value(abstract.PythonConstant(5))
    frame.store_global('x', var)
    stored = frame.load_global('x')
    self.assertEqual(stored, var.with_name('x'))
    self.assertEqual(stored, frame.load_local('x'))

  def test_store_global_in_nonmodule_frame(self):
    frame = _make_frame('', name='f')
    frame.step()
    var = variables.Variable.from_value(abstract.PythonConstant(5))
    frame.store_global('x', var)
    stored = frame.load_global('x')
    self.assertEqual(stored, var.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_local('x')

  def test_overwrite_global_in_module_frame(self):
    code = test_utils.parse('')
    var = variables.Variable.from_value(abstract.PythonConstant(5))
    frame = frame_lib.Frame('__main__', code, {'x': var}, {'x': var})
    frame.step()

    self.assertEqual(frame.load_global('x'), var.with_name('x'))
    self.assertEqual(frame.load_local('x'), var.with_name('x'))

    var2 = variables.Variable.from_value(abstract.PythonConstant(10))
    frame.store_global('x', var2)

    self.assertEqual(frame.load_global('x'), var2.with_name('x'))
    self.assertEqual(frame.load_local('x'), var2.with_name('x'))

  def test_overwrite_global_in_nonmodule_frame(self):
    code = test_utils.parse('')
    var = variables.Variable.from_value(abstract.PythonConstant(5))
    frame = frame_lib.Frame('f', code, {}, {'x': var})
    frame.step()

    self.assertEqual(frame.load_global('x'), var.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_local('x')

    var2 = variables.Variable.from_value(abstract.PythonConstant(10))
    frame.store_global('x', var2)

    self.assertEqual(frame.load_global('x'), var2.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_local('x')


class FrameTest(unittest.TestCase):

  def test_run_no_crash(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, None), opcodes.RETURN_VALUE(1, 0)]
    code = test_utils.FakeOrderedCode([block], [None])
    frame = frame_lib.Frame('test', code.Seal(), {}, {})
    frame.run()

  def test_typing(self):
    frame = _make_frame('')
    assert_type(frame.final_locals,
                Dict[str, variables.Variable[abstract.BaseValue]])

  def test_load_const(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, 42), opcodes.RETURN_VALUE(1, 0)]
    code = test_utils.FakeOrderedCode([block], [42])
    frame = frame_lib.Frame('test', code.Seal(), {}, {})
    frame.step()
    self.assertEqual(len(frame._stack), 1)
    constant = frame._stack.top().get_atomic_value()
    self.assertEqual(constant, abstract.PythonConstant(42))

  def test_store_local(self):
    frame = _make_frame('x = 42')
    frame.run()
    expected_x = variables.Variable.from_value(abstract.PythonConstant(42))
    self.assertEqual(frame.final_locals, {'x': expected_x})

  def test_store_global(self):
    frame = _make_frame("""
      global x
      x = 42
    """)
    frame.run()
    expected_x = variables.Variable.from_value(abstract.PythonConstant(42))
    self.assertEqual(frame.final_locals, {'x': expected_x})

  def test_function(self):
    frame = _make_frame('def f(): pass')
    frame.run()
    self.assertEqual(set(frame.final_locals), {'f'})
    func = frame.final_locals['f'].get_atomic_value()
    self.assertIsInstance(func, abstract.Function)
    self.assertEqual(func.name, 'f')
    self.assertCountEqual(frame.functions, [func])

  def test_copy_globals_from_module_frame(self):
    module_frame = _make_frame("""
      x = 42
      def f():
        pass
    """, name='__main__')
    module_frame.run()
    f = cast(abstract.Function,
             module_frame.final_locals['f'].get_atomic_value())
    f_frame = module_frame._make_child_frame(f)
    self.assertEqual(set(f_frame._initial_globals), {'x', 'f'})

  def test_copy_globals_from_nonmodule_frame(self):
    f_frame = _make_frame("""
      global x
      x = 42
      def g():
        pass
    """, name='f')
    f_frame.run()
    g = cast(abstract.Function,
             f_frame.final_locals['g'].get_atomic_value())
    g_frame = f_frame._make_child_frame(g)
    self.assertEqual(set(g_frame._initial_globals), {'x'})

  def test_copy_globals_from_inner_frame_to_module(self):
    module_frame = _make_frame("""
      def f():
        global x
        x = 42
      f()
    """, name='__main__')
    module_frame.run()
    self.assertEqual(set(module_frame.final_locals), {'f', 'x'})

  def test_copy_globals_from_inner_frame_to_outer(self):
    f_frame = _make_frame("""
      def g():
        global x
        x = 42
      g()
    """, name='f')
    f_frame.run()
    self.assertEqual(set(f_frame.final_locals), {'g', 'x'})
    self.assertEqual(set(f_frame._shadowed_globals), {'x'})


if __name__ == '__main__':
  unittest.main()
