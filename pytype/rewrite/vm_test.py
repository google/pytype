from pytype.pyc import opcodes
from pytype.rewrite import vm as vm_lib
from pytype.rewrite.tests import test_utils

import unittest


class VmTest(unittest.TestCase):

  def test_run_module_frame(self):
    code = test_utils.FakeOrderedCode([[
        opcodes.LOAD_CONST(0, 0, None, None),
        opcodes.RETURN_VALUE(0, 0),
    ]])
    vm = vm_lib.VirtualMachine(code.Seal(), {})
    self.assertIsNone(vm._module_frame)
    vm.run()
    self.assertIsNotNone(vm._module_frame)

  def test_vm_consumed(self):
    code = test_utils.FakeOrderedCode([[
        opcodes.LOAD_CONST(0, 0, None, None),
        opcodes.RETURN_VALUE(0, 0),
    ]])
    vm = vm_lib.VirtualMachine(code.Seal(), {})
    vm.run()
    with self.assertRaises(vm_lib.VmConsumedError):
      vm.run()


if __name__ == '__main__':
  unittest.main()
