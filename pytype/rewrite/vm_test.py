from typing import cast

from pytype.pyc import opcodes
from pytype.rewrite import abstract
from pytype.rewrite import vm as vm_lib
from pytype.rewrite.tests import test_utils

import unittest


def _make_vm(src: str) -> vm_lib.VirtualMachine:
  return vm_lib.VirtualMachine(test_utils.parse(src), {})


class VmTest(unittest.TestCase):

  def test_run_module_frame(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, None), opcodes.RETURN_VALUE(0, 0)]
    code = test_utils.FakeOrderedCode([block], [None])
    vm = vm_lib.VirtualMachine(code.Seal(), {})
    module_frame = vm._run()
    self.assertIsNotNone(module_frame)

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
    module_frame = vm._run()

    def get_const(var):
      return cast(abstract.PythonConstant, var.get_atomic_value()).constant

    x = get_const(module_frame.load_global('x'))
    y = get_const(module_frame.load_global('y'))
    z = get_const(module_frame.load_global('z'))
    self.assertEqual(x, 42)
    self.assertIsNone(y)
    self.assertEqual(z, 42)


if __name__ == '__main__':
  unittest.main()
