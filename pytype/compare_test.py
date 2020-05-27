"""Tests for compare.py."""

from pytype import abstract
from pytype import abstract_utils
from pytype import compare
from pytype import config
from pytype import errors
from pytype import function
from pytype import load_pytd
from pytype import vm
from pytype.pytd import pytd
from pytype.pytd import slots
from pytype.tests import test_base

import unittest


class CompareTestBase(test_base.UnitTest):

  def setUp(self):
    super(CompareTestBase, self).setUp()
    options = config.Options.create(python_version=self.python_version)
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))
    self._program = self._vm.program
    self._node = self._vm.root_cfg_node.ConnectNew("test_node")


class InstanceTest(CompareTestBase):

  def test_compatible_with_non_container(self):
    # Compatible with either True or False.
    i = abstract.Instance(self._vm.convert.object_type, self._vm)
    self.assertIs(True, compare.compatible_with(i, True))
    self.assertIs(True, compare.compatible_with(i, False))

  def test_compatible_with_list(self):
    i = abstract.List([], self._vm)
    # Empty list is not compatible with True.
    self.assertIs(False, compare.compatible_with(i, True))
    self.assertIs(True, compare.compatible_with(i, False))
    # Once a type parameter is set, list is compatible with True and False.
    i.merge_instance_type_parameter(
        self._node, abstract_utils.T,
        self._vm.convert.object_type.to_variable(self._vm.root_cfg_node))
    self.assertIs(True, compare.compatible_with(i, True))
    self.assertIs(True, compare.compatible_with(i, False))

  def test_compatible_with_set(self):
    i = abstract.Instance(self._vm.convert.set_type, self._vm)
    # Empty list is not compatible with True.
    self.assertIs(False, compare.compatible_with(i, True))
    self.assertIs(True, compare.compatible_with(i, False))
    # Once a type parameter is set, list is compatible with True and False.
    i.merge_instance_type_parameter(
        self._node, abstract_utils.T,
        self._vm.convert.object_type.to_variable(self._vm.root_cfg_node))
    self.assertIs(True, compare.compatible_with(i, True))
    self.assertIs(True, compare.compatible_with(i, False))

  def test_compatible_with_none(self):
    # This test is specifically for abstract.Instance, so we don't use
    # self._vm.convert.none, which is an AbstractOrConcreteValue.
    i = abstract.Instance(self._vm.convert.none_type, self._vm)
    self.assertIs(False, compare.compatible_with(i, True))
    self.assertIs(True, compare.compatible_with(i, False))

  def test_compare_frozensets(self):
    """Test that two frozensets can be compared for equality."""
    fset = self._vm.convert.frozenset_type
    i = abstract.Instance(fset, self._vm)
    j = abstract.Instance(fset, self._vm)
    self.assertIs(None, compare.cmp_rel(self._vm, slots.EQ, i, j))


class TupleTest(CompareTestBase):

  def setUp(self):
    super(TupleTest, self).setUp()
    self._var = self._program.NewVariable()
    self._var.AddBinding(abstract.Unknown(self._vm), [], self._node)

  def test_compatible_with__not_empty(self):
    t = abstract.Tuple((self._var,), self._vm)
    self.assertIs(True, compare.compatible_with(t, True))
    self.assertIs(False, compare.compatible_with(t, False))

  def test_compatible_with__empty(self):
    t = abstract.Tuple((), self._vm)
    self.assertIs(False, compare.compatible_with(t, True))
    self.assertIs(True, compare.compatible_with(t, False))

  def test_getitem__concrete_index(self):
    t = abstract.Tuple((self._var,), self._vm)
    index = self._vm.convert.constant_to_var(0)
    node, var = t.cls.getitem_slot(self._node, index)
    self.assertIs(node, self._node)
    self.assertIs(abstract_utils.get_atomic_value(var),
                  abstract_utils.get_atomic_value(self._var))

  def test_getitem__abstract_index(self):
    t = abstract.Tuple((self._var,), self._vm)
    index = self._vm.convert.build_int(self._node)
    node, var = t.cls.getitem_slot(self._node, index)
    self.assertIs(node, self._node)
    self.assertIs(abstract_utils.get_atomic_value(var),
                  abstract_utils.get_atomic_value(self._var))


class DictTest(CompareTestBase):

  def setUp(self):
    super(DictTest, self).setUp()
    self._d = abstract.Dict(self._vm)
    self._var = self._program.NewVariable()
    self._var.AddBinding(abstract.Unknown(self._vm), [], self._node)

  def test_compatible_with__when_empty(self):
    self.assertIs(False, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))

  def test_compatible_with__after_setitem(self):
    # Once a slot is added, dict is ambiguous.
    self._d.setitem_slot(self._node, self._var, self._var)
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))

  def test_compatible_with__after_set_str_item(self):
    self._d.set_str_item(self._node, "key", self._var)
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(False, compare.compatible_with(self._d, False))

  def test_compatible_with__after_unknown_update(self):
    # Updating an empty dict with an unknown value makes the former ambiguous.
    self._d.update(self._node, abstract.Unknown(self._vm))
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))

  def test_compatible_with__after_empty_update(self):
    empty_dict = abstract.Dict(self._vm)
    self._d.update(self._node, empty_dict)
    self.assertIs(False, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))

  def test_compatible_with__after_unambiguous_update(self):
    unambiguous_dict = abstract.Dict(self._vm)
    unambiguous_dict.set_str_item(
        self._node, "a", self._vm.new_unsolvable(self._node))
    self._d.update(self._node, unambiguous_dict)
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(False, compare.compatible_with(self._d, False))

  def test_compatible_with__after_ambiguous_update(self):
    ambiguous_dict = abstract.Dict(self._vm)
    ambiguous_dict.merge_instance_type_parameter(
        self._node, abstract_utils.K, self._vm.new_unsolvable(self._node))
    ambiguous_dict.could_contain_anything = True
    self._d.update(self._node, ambiguous_dict)
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))

  def test_compatible_with__after_concrete_update(self):
    self._d.update(self._node, {})
    self.assertIs(False, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self._d.update(self._node, {"a": self._vm.new_unsolvable(self._node)})
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(False, compare.compatible_with(self._d, False))

  def test_pop(self):
    self._d.set_str_item(self._node, "a", self._var)
    node, ret = self._d.pop_slot(
        self._node, self._vm.convert.build_string(self._node, "a"))
    self.assertIs(False, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self.assertIs(node, self._node)
    self.assertIs(ret, self._var)

  def test_pop_with_default(self):
    self._d.set_str_item(self._node, "a", self._var)
    node, ret = self._d.pop_slot(
        self._node, self._vm.convert.build_string(self._node, "a"),
        self._vm.convert.none.to_variable(self._node))  # default is ignored
    self.assertIs(False, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self.assertIs(node, self._node)
    self.assertIs(ret, self._var)

  def test_bad_pop(self):
    self._d.set_str_item(self._node, "a", self._var)
    self.assertRaises(function.DictKeyMissing, self._d.pop_slot, self._node,
                      self._vm.convert.build_string(self._node, "b"))
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(False, compare.compatible_with(self._d, False))

  def test_bad_pop_with_default(self):
    val = self._vm.convert.primitive_class_instances[int]
    self._d.set_str_item(self._node, "a", val.to_variable(self._node))
    node, ret = self._d.pop_slot(
        self._node, self._vm.convert.build_string(self._node, "b"),
        self._vm.convert.none.to_variable(self._node))
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(False, compare.compatible_with(self._d, False))
    self.assertIs(node, self._node)
    self.assertListEqual(ret.data, [self._vm.convert.none])

  def test_ambiguous_pop(self):
    val = self._vm.convert.primitive_class_instances[int]
    self._d.set_str_item(self._node, "a", val.to_variable(self._node))
    ambiguous_key = self._vm.convert.primitive_class_instances[str]
    node, ret = self._d.pop_slot(
        self._node, ambiguous_key.to_variable(self._node))
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self.assertIs(node, self._node)
    self.assertListEqual(ret.data, [val])

  def test_ambiguous_pop_with_default(self):
    val = self._vm.convert.primitive_class_instances[int]
    self._d.set_str_item(self._node, "a", val.to_variable(self._node))
    ambiguous_key = self._vm.convert.primitive_class_instances[str]
    default_var = self._vm.convert.none.to_variable(self._node)
    node, ret = self._d.pop_slot(
        self._node, ambiguous_key.to_variable(self._node), default_var)
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self.assertIs(node, self._node)
    self.assertSetEqual(set(ret.data), {val, self._vm.convert.none})

  def test_ambiguous_dict_after_pop(self):
    ambiguous_key = self._vm.convert.primitive_class_instances[str]
    val = self._vm.convert.primitive_class_instances[int]
    node, _ = self._d.setitem_slot(
        self._node, ambiguous_key.to_variable(self._node),
        val.to_variable(self._node))
    _, ret = self._d.pop_slot(node, self._vm.convert.build_string(node, "a"))
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self.assertListEqual(ret.data, [val])

  def test_ambiguous_dict_after_pop_with_default(self):
    ambiguous_key = self._vm.convert.primitive_class_instances[str]
    val = self._vm.convert.primitive_class_instances[int]
    node, _ = self._d.setitem_slot(
        self._node, ambiguous_key.to_variable(self._node),
        val.to_variable(self._node))
    _, ret = self._d.pop_slot(node, self._vm.convert.build_string(node, "a"),
                              self._vm.convert.none.to_variable(node))
    self.assertIs(True, compare.compatible_with(self._d, True))
    self.assertIs(True, compare.compatible_with(self._d, False))
    self.assertSetEqual(set(ret.data), {val, self._vm.convert.none})


class FunctionTest(CompareTestBase):

  def test_compatible_with(self):
    pytd_sig = pytd.Signature((), None, None, pytd.AnythingType(), (), ())
    sig = function.PyTDSignature("f", pytd_sig, self._vm)
    f = abstract.PyTDFunction("f", (sig,), pytd.METHOD, self._vm)
    self.assertIs(True, compare.compatible_with(f, True))
    self.assertIs(False, compare.compatible_with(f, False))


class ClassTest(CompareTestBase):

  def test_compatible_with(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    self.assertIs(True, compare.compatible_with(cls, True))
    self.assertIs(False, compare.compatible_with(cls, False))


if __name__ == "__main__":
  unittest.main()
