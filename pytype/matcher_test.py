"""Tests for matcher.py."""


from pytype import abstract
from pytype import config
from pytype import errors
from pytype import vm

import unittest


class MatcherTest(unittest.TestCase):
  """Test matcher.AbstractMatcher."""

  def setUp(self):
    self.vm = vm.VirtualMachine(errors.ErrorLog(), config.Options([""]))
    self.type_type = abstract.get_atomic_value(self.vm.convert.type_type)

  def _make_class(self, name):
    return abstract.InterpreterClass(name, [], {}, None, self.vm)

  def _match_var(self, left, right):
    var = self.vm.program.NewVariable()
    left_binding = var.AddBinding(left)
    return self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {var: left_binding})

  def testBasic(self):
    result = self._match_var(abstract.Empty(self.vm), abstract.Nothing(self.vm))
    self.assertEquals(result, {})

  def testType(self):
    left = self._make_class("dummy")
    type_parameters = {abstract.T: abstract.TypeParameter(abstract.T, self.vm)}
    other_type = abstract.ParameterizedClass(
        self.type_type, type_parameters, self.vm)
    result = self._match_var(left, other_type)
    instance_binding, = result[abstract.T].bindings
    cls_binding, = instance_binding.data.cls.bindings
    self.assertEquals(cls_binding.data, left)

  def testUnion(self):
    left_option1 = self._make_class("o1")
    left_option2 = self._make_class("o2")
    left = abstract.Union([left_option1, left_option2], self.vm)
    result = self._match_var(left, self.type_type)
    self.assertEquals(result, {})

  def testMetaclass(self):
    left = self._make_class("left")
    meta1 = self._make_class("m1")
    meta2 = self._make_class("m2")
    left.cls = self.vm.program.NewVariable(
        [meta1, meta2], [], self.vm.root_cfg_node)
    result1 = self._match_var(left, meta1)
    result2 = self._match_var(left, meta2)
    self.assertEquals(result1, {})
    self.assertEquals(result2, {})

  def testEmptyAgainstClass(self):
    var = self.vm.program.NewVariable()
    right = self._make_class("bar")
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEquals(result, {})

  def testEmptyAgainstNothing(self):
    var = self.vm.program.NewVariable()
    right = abstract.Nothing(self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEquals(result, {})

  def testEmptyAgainstTypeParameter(self):
    var = self.vm.program.NewVariable()
    right = abstract.TypeParameter("T", self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertItemsEqual(result, ["T"])
    self.assertFalse(result["T"].bindings)

  def testEmptyAgainstUnsolvable(self):
    var = self.vm.program.NewVariable()
    right = abstract.Empty(self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEquals(result, {})

  def testClassAgainstTypeUnion(self):
    left = self._make_class("foo")
    union = abstract.Union((left,), self.vm)
    right = abstract.ParameterizedClass(self.type_type, {"T": union}, self.vm)
    result = self._match_var(left, right)
    self.assertEquals(result, {})


if __name__ == "__main__":
  unittest.main()
