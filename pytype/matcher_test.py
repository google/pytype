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

  def _match(self, left, right):
    var = self.vm.program.NewVariable("foo")
    left_binding = var.AddBinding(left)
    return self.matcher.match_var_against_type(
        var, right, {}, self.root_cfg_node, {
            var: left_binding})

  def testBasic(self):
    result = self._match(abstract.Empty(self.vm), abstract.Nothing(self.vm))
    self.assertEquals(result, {})


if __name__ == "__main__":
  unittest.main()
