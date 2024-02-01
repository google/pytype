from pytype.rewrite.flow import conditions

import unittest


class ConditionTest(unittest.TestCase):

  def test_or_true(self):
    condition = conditions.Or(conditions.Condition(), conditions.TRUE)
    self.assertIs(condition, conditions.TRUE)

  def test_or_false(self):
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    or_condition = conditions.Or(c1, c2, conditions.FALSE)
    self.assertEqual(or_condition.conditions, (c1, c2))

  def test_or_singleton(self):
    condition = conditions.Condition()
    or_condition = conditions.Or(condition, conditions.FALSE)
    self.assertIs(or_condition, condition)

  def test_and_false(self):
    condition = conditions.And(conditions.Condition(), conditions.FALSE)
    self.assertIs(condition, conditions.FALSE)

  def test_and_true(self):
    c1 = conditions.Condition()
    c2 = conditions.Condition()
    and_condition = conditions.And(c1, c2, conditions.TRUE)
    self.assertEqual(and_condition.conditions, (c1, c2))

  def test_and_singleton(self):
    condition = conditions.Condition()
    and_condition = conditions.And(condition, conditions.TRUE)
    self.assertIs(and_condition, condition)


if __name__ == '__main__':
  unittest.main()
