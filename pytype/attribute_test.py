"""Tests for attribute.py."""

from pytype import abstract
from pytype import abstract_utils
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype import vm
from pytype.tests import test_base

import unittest


def _get_origins(binding):
  """Gets all the bindings in the given binding's origins."""
  bindings = set()
  for origin in binding.origins:
    for source_set in origin.source_sets:
      bindings |= source_set
  return bindings


class ValselfTest(test_base.UnitTest):
  """Tests for get_attribute's `valself` parameter."""

  def setUp(self):
    super().setUp()
    options = config.Options.create(python_version=self.python_version)
    self.vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))
    self.node = self.vm.root_cfg_node
    self.attribute_handler = self.vm.attribute_handler

  def test_instance_no_valself(self):
    instance = abstract.Instance(self.vm.convert.int_type, self.vm)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, instance, "real")
    attr_binding, = attr_var.bindings
    self.assertEqual(attr_binding.data.cls, self.vm.convert.int_type)
    # Since `valself` was not passed to get_attribute, a binding to
    # `instance` is not among the attribute's origins.
    self.assertNotIn(instance, [o.data for o in _get_origins(attr_binding)])

  def test_instance_with_valself(self):
    instance = abstract.Instance(self.vm.convert.int_type, self.vm)
    valself = instance.to_binding(self.node)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, instance, "real", valself)
    attr_binding, = attr_var.bindings
    self.assertEqual(attr_binding.data.cls, self.vm.convert.int_type)
    # Since `valself` was passed to get_attribute, it is added to the
    # attribute's origins.
    self.assertIn(valself, _get_origins(attr_binding))

  def test_class_no_valself(self):
    meta_members = {"x": self.vm.convert.none.to_variable(self.node)}
    meta = abstract.InterpreterClass("M", [], meta_members, None, self.vm)
    cls = abstract.InterpreterClass("X", [], {}, meta, self.vm)
    _, attr_var = self.attribute_handler.get_attribute(self.node, cls, "x")
    # Since `valself` was not passed to get_attribute, we do not look at the
    # metaclass, so M.x is not returned.
    self.assertIsNone(attr_var)

  def test_class_with_instance_valself(self):
    meta_members = {"x": self.vm.convert.none.to_variable(self.node)}
    meta = abstract.InterpreterClass("M", [], meta_members, None, self.vm)
    cls = abstract.InterpreterClass("X", [], {}, meta, self.vm)
    valself = abstract.Instance(cls, self.vm).to_binding(self.node)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, cls, "x", valself)
    # Since `valself` is an instance of X, we do not look at the metaclass, so
    # M.x is not returned.
    self.assertIsNone(attr_var)

  def test_class_with_class_valself(self):
    meta_members = {"x": self.vm.convert.none.to_variable(self.node)}
    meta = abstract.InterpreterClass("M", [], meta_members, None, self.vm)
    cls = abstract.InterpreterClass("X", [], {}, meta, self.vm)
    valself = cls.to_binding(self.node)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, cls, "x", valself)
    # Since `valself` is X itself, we look at the metaclass and return M.x.
    self.assertEqual(attr_var.data, [self.vm.convert.none])

  def test_getitem_no_valself(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self.vm)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, cls, "__getitem__")
    attr, = attr_var.data
    # Since we looked up __getitem__ on a class without passing in `valself`,
    # the class is treated as an annotation.
    self.assertIs(attr.func.__func__, abstract.AnnotationClass.getitem_slot)

  def test_getitem_with_instance_valself(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self.vm)
    valself = abstract.Instance(cls, self.vm).to_binding(self.node)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, cls, "__getitem__", valself)
    # Since we passed in `valself` for this lookup of __getitem__ on a class,
    # it is treated as a normal lookup; X.__getitem__ does not exist.
    self.assertIsNone(attr_var)

  def test_getitem_with_class_valself(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self.vm)
    valself = cls.to_binding(self.node)
    _, attr_var = self.attribute_handler.get_attribute(
        self.node, cls, "__getitem__", valself)
    # Since we passed in `valself` for this lookup of __getitem__ on a class,
    # it is treated as a normal lookup; X.__getitem__ does not exist.
    self.assertIsNone(attr_var)


class AttributeTest(test_base.UnitTest):

  def setUp(self):
    super().setUp()
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
