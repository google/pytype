from typing import Type, TypeVar

from pytype.pyc import opcodes
from pytype.rewrite import abstract
from pytype.rewrite import vm as vm_lib
from pytype.rewrite.tests import test_utils

import unittest

_T = TypeVar('_T')


def _make_vm(src: str) -> vm_lib.VirtualMachine:
  return vm_lib.VirtualMachine(test_utils.parse(src), {})


def _get(typ: Type[_T], var) -> _T:
  v = var.get_atomic_value()
  assert isinstance(v, typ)
  return v


class VmTest(unittest.TestCase):

  def test_run_module_frame(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, None), opcodes.RETURN_VALUE(0, 0)]
    code = test_utils.FakeOrderedCode([block], [None])
    vm = vm_lib.VirtualMachine(code.Seal(), {})
    self.assertIsNone(vm._module_frame)
    vm._run_module()
    self.assertIsNotNone(vm._module_frame)

  def test_globals(self):
    vm = _make_vm("""
      x = 42
      def f():
        global y
        y = None
        def g():
          global z
          z = x
        g()
      f()
    """)
    vm._run_module()

    def get_const(var):
      return _get(abstract.PythonConstant, var).constant

    x = get_const(vm._module_frame.load_global('x'))
    y = get_const(vm._module_frame.load_global('y'))
    z = get_const(vm._module_frame.load_global('z'))
    self.assertEqual(x, 42)
    self.assertIsNone(y)
    self.assertEqual(z, 42)

  def test_analyze_functions(self):
    # Just make sure this doesn't crash.
    vm = _make_vm("""
      def f():
        def g():
          pass
    """)
    vm.analyze_all_defs()

  def test_infer_stub(self):
    # Just make sure this doesn't crash.
    vm = _make_vm("""
      def f():
        def g():
          pass
    """)
    vm.infer_stub()

  def test_run_function(self):
    vm = _make_vm("""
      x = None

      def f():
        global x
        x = 42

      def g():
        y = x
    """)
    vm._run_module()
    f = _get(abstract.Function, vm._module_frame.final_locals['f'])
    g = _get(abstract.Function, vm._module_frame.final_locals['g'])
    f_frame = vm._run_function(f)
    g_frame = vm._run_function(g)

    self.assertEqual(f_frame.load_global('x').get_atomic_value(),
                     abstract.PythonConstant(42))
    self.assertEqual(g_frame.load_local('y').get_atomic_value(),
                     abstract.PythonConstant(None))


if __name__ == '__main__':
  unittest.main()
