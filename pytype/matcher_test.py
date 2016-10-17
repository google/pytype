"""Tests for matcher.py."""


from pytype import abstract
from pytype import matcher
from pytype.pytd import cfg

import unittest


class FakeVM(object):

  def __init__(self):
    self.program = cfg.Program()


class MatcherTest(unittest.TestCase):
  """Test matcher.AbstractMatcher."""

  def setUp(self):
    self.matcher = matcher.AbstractMatcher()
    self.vm = FakeVM()
    self.root_cfg_node = self.vm.program.NewCFGNode("root")

  def _match_var(self, left, right):
    var = self.vm.program.NewVariable("foo")
    left_binding = var.AddBinding(left)
    return self.matcher.match_var_against_type(
        var, right, {}, self.root_cfg_node, {var: left_binding})

  def _match_value(self, left, right):
    var = self.vm.program.NewVariable("foo")
    left_binding = var.AddBinding(left)
    return self.matcher.match_value_against_type(
        left_binding, right, {}, self.root_cfg_node, {var: left_binding})

  def testBasic(self):
    result = self._match_var(abstract.Empty(self.vm), abstract.Nothing(self.vm))
    self.assertEquals(result, {})

  def testType(self):
    left = abstract.InterpreterClass("dummy", [], {}, self.vm)
    right = abstract.InterpreterClass("type", [], {}, self.vm)
    type_parameters = {"T": abstract.TypeParameter("T", self.vm)}
    other_type = abstract.ParameterizedClass(right, type_parameters, self.vm)
    other_type.module = "__builtin__"
    result = self._match_value(left, other_type)
    instance_binding, = result["T"].bindings
    cls_binding, = instance_binding.data.cls.bindings
    self.assertEquals(cls_binding.data, left)


if __name__ == "__main__":
  unittest.main()
