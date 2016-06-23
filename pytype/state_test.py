"""Test state.py."""

from pytype import state
from pytype.pytd import cfg

import unittest


def source_summary(binding):
  """A simple deterministic listing of source variables."""
  clauses = []
  for origin in binding.origins:
    for sources in origin.source_sets:
      bindings = ["%s=%s" % (b.variable.name, b.data) for b in sources]
      clauses.append(" ".join(sorted(bindings)))
  return " | ".join(sorted(clauses))


class FakeValue(object):

  def __init__(self, name, true_compat, false_compat):
    self._name = name
    self._compatible = {
        True: true_compat,
        False: false_compat}

  def compatible_with(self, logical_value):
    return self._compatible[logical_value]

  def __str__(self):
    return self._name


ONLY_TRUE = FakeValue("T", True, False)
ONLY_FALSE = FakeValue("F", False, True)
AMBIGUOUS = FakeValue("?", True, True)


class ConditionTestBase(unittest.TestCase):

  def setUp(self):
    self._program = cfg.Program()
    self._node = self._program.NewCFGNode("test")

  def new_binding(self, name, value=AMBIGUOUS):
    var = self._program.NewVariable(name)
    return var.AddBinding(value)

  def check_binding(self, expected, binding):
    self.assertEquals(1, len(binding.origins))
    self.assertEquals(self._node, binding.origins[0].where)
    self.assertEquals(expected, source_summary(binding))


class ConditionTest(ConditionTestBase):

  def test_no_parent(self):
    x = self.new_binding("x")
    y = self.new_binding("y")
    z = self.new_binding("z")
    c = state.Condition(self._node, None, [[x, y], [z]])
    self.assertIsNone(c.parent)
    self.check_binding("x=? y=? | z=?", c.binding)

  def test_parent_combination(self):
    p = self.new_binding("p")
    parent = state.Condition(self._node, None, [[p]])
    x = self.new_binding("x")
    y = self.new_binding("y")
    z = self.new_binding("z")
    c = state.Condition(self._node, parent, [[x, y], [z]])
    self.assertIs(parent, c.parent)
    self.check_binding("__split=None x=? y=? | __split=None z=?", c.binding)


class SplitConditionTest(ConditionTestBase):

  def test(self):
    # Test that we split both sides and that everything gets passed through
    # correctly.  Don't worry about special cases within _restrict_condition
    # since those are tested separately.
    p = self.new_binding("x")
    parent = state.Condition(self._node, None, [[p]])
    var = self._program.NewVariable("v")
    var.AddBinding(ONLY_TRUE)
    var.AddBinding(ONLY_FALSE)
    var.AddBinding(AMBIGUOUS)
    true_cond, false_cond = state.split_conditions(self._node, parent, var)
    self.assertIs(parent, true_cond.parent)
    self.check_binding("__split=None v=? | __split=None v=T", true_cond.binding)
    self.assertIs(parent, false_cond.parent)
    self.check_binding("__split=None v=? | __split=None v=F",
                       false_cond.binding)


class RestrictConditionTest(ConditionTestBase):

  def setUp(self):
    super(RestrictConditionTest, self).setUp()
    p = self.new_binding("p")
    self._parent = state.Condition(self._node, None, [[p]])

  def test_no_bindings(self):
    c = state._restrict_condition(self._node, self._parent, [], False)
    self.assertIs(state.UNSATISFIABLE, c)
    c = state._restrict_condition(self._node, self._parent, [], True)
    self.assertIs(state.UNSATISFIABLE, c)

  def test_none_restricted(self):
    x = self.new_binding("x")
    y = self.new_binding("y")
    c = state._restrict_condition(self._node, self._parent, [x, y], False)
    self.assertIs(self._parent, c)
    c = state._restrict_condition(self._node, self._parent, [x, y], True)
    self.assertIs(self._parent, c)

  def test_all_restricted(self):
    x = self.new_binding("x", ONLY_FALSE)
    y = self.new_binding("y", ONLY_FALSE)
    c = state._restrict_condition(self._node, self._parent, [x, y], True)
    self.assertIs(state.UNSATISFIABLE, c)

  def test_some_restricted_no_parent(self):
    x = self.new_binding("x")  # Can be true or false.
    y = self.new_binding("y", ONLY_FALSE)
    z = self.new_binding("z")  # Can be true or false.
    c = state._restrict_condition(self._node, None, [x, y, z], True)
    self.assertIsNone(c.parent)
    self.check_binding("x=? | z=?", c.binding)

  def test_some_restricted_with_parent(self):
    x = self.new_binding("x")  # Can be true or false.
    y = self.new_binding("y", ONLY_FALSE)
    z = self.new_binding("z")  # Can be true or false.
    c = state._restrict_condition(self._node, self._parent, [x, y, z], True)
    self.assertIs(self._parent, c.parent)
    self.check_binding("__split=None x=? | __split=None z=?", c.binding)

  def test_restricted_to_dnf(self):
    # DNF for a | (b & c)
    dnf = [[self.new_binding("a")],
           [self.new_binding("b"), self.new_binding("c")]]
    x = self.new_binding("x")  # Compatible with everything
    y = self.new_binding("z", FakeValue("DNF", dnf, False))  # Reduce to dnf
    c = state._restrict_condition(self._node, None, [x, y], True)
    self.assertIsNone(c.parent)
    self.check_binding("a=? | b=? c=? | x=?", c.binding)


class CommonConditionTest(ConditionTestBase):

  def test(self):
    # Create the following trees (parents are to the left)
    #
    # 1 - 2 - 3 - 4
    #      \
    #       5 - 6
    #
    # 7 - 8
    conds = [None]  # index 0 is the condition of None
    for number, parent in enumerate([0, 1, 2, 3, 2, 5, 0, 7], 1):
      binding = self.new_binding("v%d" % number)
      conds.append(state.Condition(self._node, conds[parent], [[binding]]))

    def check(expected, left, right):
      self.assertEquals(conds[expected],
                        state._common_condition(conds[left], conds[right]))

    # Check that None (conds[0]) is handled correctly.
    check(0, 0, 0)
    check(0, 0, 4)
    check(0, 4, 0)
    # One condition a descendant of the other.
    check(2, 2, 4)
    check(2, 4, 2)
    # Common ancestor.
    check(2, 3, 6)
    check(2, 4, 6)
    # Unrelated.
    check(0, 4, 8)


if __name__ == "__main__":
  unittest.main()
