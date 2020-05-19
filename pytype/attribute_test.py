"""Tests for attribute.py."""

from pytype import abstract
from pytype import abstract_utils
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype import vm
from pytype.tests import test_base

import unittest


class AttributeTest(test_base.UnitTest):

  def setUp(self):
    super(AttributeTest, self).setUp()
    options = config.Options.create(python_version=self.python_version)
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))

  def test_type_parameter_instance(self):
    t = abstract.TypeParameter(abstract_utils.T, self._vm)
    t_instance = abstract.TypeParameterInstance(
        t, self._vm.convert.primitive_class_instances[str], self._vm)
    node, var = self._vm.attribute_handler.get_attribute(
        self._vm.root_cfg_node, t_instance, "upper")
    self.assertIs(node, self._vm.root_cfg_node)
    attr, = var.data
    self.assertIsInstance(attr, abstract.PyTDFunction)

  def test_type_parameter_instance_bad_attribute(self):
    t = abstract.TypeParameter(abstract_utils.T, self._vm)
    t_instance = abstract.TypeParameterInstance(
        t, self._vm.convert.primitive_class_instances[str], self._vm)
    node, var = self._vm.attribute_handler.get_attribute(
        self._vm.root_cfg_node, t_instance, "rumpelstiltskin")
    self.assertIs(node, self._vm.root_cfg_node)
    self.assertIsNone(var)

  def test_empty_type_parameter_instance(self):
    t = abstract.TypeParameter(
        abstract_utils.T, self._vm, bound=self._vm.convert.int_type)
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    node, var = self._vm.attribute_handler.get_attribute(
        self._vm.root_cfg_node, t_instance, "real")
    self.assertIs(node, self._vm.root_cfg_node)
    attr, = var.data
    self.assertIs(attr, self._vm.convert.primitive_class_instances[int])

  def test_type_parameter_instance_set_attribute(self):
    t = abstract.TypeParameter(abstract_utils.T, self._vm)
    t_instance = abstract.TypeParameterInstance(
        t, self._vm.convert.primitive_class_instances[str], self._vm)
    node = self._vm.attribute_handler.set_attribute(
        self._vm.root_cfg_node, t_instance, "rumpelstiltskin",
        self._vm.new_unsolvable(self._vm.root_cfg_node))
    self.assertIs(node, self._vm.root_cfg_node)
    self.assertEqual(
        str(self._vm.errorlog).strip(),
        "Can't assign attribute 'rumpelstiltskin' on str [not-writable]")

  def test_union_set_attribute(self):
    list_instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    cls = abstract.InterpreterClass(
        "obj", [], {}, None, self._vm)
    cls_instance = abstract.Instance(cls, self._vm)
    union = abstract.Union([cls_instance, list_instance], self._vm)
    node = self._vm.attribute_handler.set_attribute(
        self._vm.root_cfg_node, union, "rumpelstiltskin",
        self._vm.convert.none_type.to_variable(self._vm.root_cfg_node))
    self.assertEqual(cls_instance.members["rumpelstiltskin"].data.pop(),
                     self._vm.convert.none_type)
    self.assertIs(node, self._vm.root_cfg_node)
    error, = self._vm.errorlog.unique_sorted_errors()
    self.assertEqual(error.name, "not-writable")

if __name__ == "__main__":
  unittest.main()
