"""Tests for abstract.py."""

import unittest


from pytype import abstract
from pytype import config
from pytype import vm
from pytype.pytd import cfg

import unittest


class DictTest(unittest.TestCase):

  def setUp(self):
    self._vm = vm.VirtualMachine(None, config.Options([""]))
    self._program = cfg.Program()
    self._node = self._program.NewCFGNode("test_node")
    self._d = abstract.Dict("test_dict", self._vm)
    self._var = self._program.NewVariable("test_var")
    self._var.AddBinding(abstract.Unknown(self._vm))

  def test_compatible_with__when_empty(self):
    self.assertIs(False, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  @unittest.skip("setitem() does not update the parameters")
  def test_compatible_with__after_setitem(self):
    # Once a slot is added, dict is ambiguous.
    self._d.setitem(self._node, self._var, self._var)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_set_str_item(self):
    # set_str_item() will make the dict ambiguous.
    self._d.set_str_item(self._node, "key", self._var)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  @unittest.skip("update() does not update the parameters")
  def test_compatible_with__after_update(self):
    # Updating an empty dict also makes it ambiguous.
    self._d.update(self._node, abstract.Unknown(self._vm))
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))


if __name__ == "__main__":
  unittest.main()
