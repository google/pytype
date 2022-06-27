"""Test state.py."""

from pytype import compare
from pytype import state
from pytype.typegraph import cfg

import unittest


def source_summary(binding, **varnames):
  """A simple deterministic listing of source variables."""
  clauses = []
  name_map = {b.variable: name for name, b in varnames.items()}
  for origin in binding.origins:
    for sources in origin.source_sets:
      bindings = [f"{name_map[b.variable]}={b.data}" for b in sources]
      clauses.append(" ".join(sorted(bindings)))
  return " | ".join(sorted(clauses))


class FakeValue:

  def __init__(self, name, true_compat, false_compat):
    self._name = name
    self.compatible = {
        True: true_compat,
        False: false_compat}

  def __str__(self):
    return self._name


ONLY_TRUE = FakeValue("T", True, False)
ONLY_FALSE = FakeValue("F", False, True)
AMBIGUOUS = FakeValue("?", True, True)


def fake_compatible_with(value, logical_value):
  return value.compatible[logical_value]


class ConditionTestBase(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self._program = cfg.Program()
    self._node = self._program.NewCFGNode("test")
    self._old_compatible_with = compare.compatible_with
    compare.compatible_with = fake_compatible_with

  def tearDown(self):
    super().tearDown()
    compare.compatible_with = self._old_compatible_with

  def new_binding(self, value=AMBIGUOUS):
    var = self._program.NewVariable()
    return var.AddBinding(value)

  def check_binding(self, expected, binding, **varnames):
    self.assertEqual(len(binding.origins), 1)
    self.assertEqual(self._node, binding.origins[0].where)
    self.assertEqual(expected, source_summary(binding, **varnames))


class ConditionTest(ConditionTestBase):

  def test_no_parent(self):
    x = self.new_binding()
    y = self.new_binding()
    z = self.new_binding()
    c = state.Condition(self._node, [[x, y], [z]])
    self.check_binding("x=? y=? | z=?", c.binding, x=x, y=y, z=z)

  def test_parent_combination(self):
    p = self.new_binding()
    x = self.new_binding()
    y = self.new_binding()
    z = self.new_binding()
    c = state.Condition(self._node, [[x, y], [z]])
    self.check_binding("x=? y=? | z=?", c.binding,
                       p=p, x=x, y=y, z=z)


class SplitConditionTest(ConditionTestBase):

  def test(self):
    # Test that we split both sides and that everything gets passed through
    # correctly.  Don't worry about special cases within _restrict_condition
    # since those are tested separately.
    self.new_binding()
    var = self._program.NewVariable()
    var.AddBinding(ONLY_TRUE)
    var.AddBinding(ONLY_FALSE)
    var.AddBinding(AMBIGUOUS)
    true_cond, false_cond = state.split_conditions(self._node, var)
    self.check_binding("v=? | v=T", true_cond.binding,
                       v=var.bindings[0])
    self.check_binding("v=? | v=F",
                       false_cond.binding,
                       v=var.bindings[0])


class RestrictConditionTest(ConditionTestBase):

  def setUp(self):
    super().setUp()
    p = self.new_binding()
    self._parent = state.Condition(self._node, [[p]])

  def test_no_bindings(self):
    c = state._restrict_condition(self._node, [], False)
    self.assertIs(state.UNSATISFIABLE, c)
    c = state._restrict_condition(self._node, [], True)
    self.assertIs(state.UNSATISFIABLE, c)

  def test_none_restricted(self):
    x = self.new_binding()
    y = self.new_binding()
    state._restrict_condition(self._node, [x, y], False)
    state._restrict_condition(self._node, [x, y], True)

  def test_all_restricted(self):
    x = self.new_binding(ONLY_FALSE)
    y = self.new_binding(ONLY_FALSE)
    c = state._restrict_condition(self._node, [x, y], True)
    self.assertIs(state.UNSATISFIABLE, c)

  def test_some_restricted_no_parent(self):
    x = self.new_binding()  # Can be true or false.
    y = self.new_binding(ONLY_FALSE)
    z = self.new_binding()  # Can be true or false.
    c = state._restrict_condition(self._node, [x, y, z], True)
    self.check_binding("x=? | z=?", c.binding, x=x, y=y, z=z)

  def test_some_restricted_with_parent(self):
    x = self.new_binding()  # Can be true or false.
    y = self.new_binding(ONLY_FALSE)
    z = self.new_binding()  # Can be true or false.
    c = state._restrict_condition(self._node, [x, y, z], True)
    self.check_binding("x=? | z=?", c.binding,
                       x=x, y=y, z=z)

  def test_restricted_to_dnf(self):
    # DNF for a | (b & c)
    a = self.new_binding()
    b = self.new_binding()
    c = self.new_binding()
    dnf = [[a],
           [b, c]]
    x = self.new_binding()  # Compatible with everything
    y = self.new_binding(FakeValue("DNF", dnf, False))  # Reduce to dnf
    cond = state._restrict_condition(self._node, [x, y], True)
    self.check_binding("a=? | b=? c=? | x=?", cond.binding,
                       a=a, b=b, c=c, x=x, y=y)


if __name__ == "__main__":
  unittest.main()
