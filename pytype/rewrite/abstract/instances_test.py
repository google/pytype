from typing import Dict, List, Set, Tuple

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import instances
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest

# Type aliases
_ConstVar = variables.Variable[base.PythonConstant]


class BaseTest(test_utils.ContextfulTestBase):
  """Base class for constant tests."""

  def const_var(self, const, name=None):
    return base.PythonConstant(self.ctx, const).to_variable(name)


class ListTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    c = instances.List(self.ctx, [a])
    assert_type(c.constant, List[_ConstVar])


class DictTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    b = self.const_var("b")
    c = instances.Dict(self.ctx, {a: b})
    assert_type(c.constant, Dict[_ConstVar, _ConstVar])


class SetTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    c = instances.Set(self.ctx, {a})
    assert_type(c.constant, Set[_ConstVar])


class TupleTest(BaseTest):

  def test_constant_type(self):
    a = self.const_var("a")
    b = self.const_var("b")
    c = instances.Tuple(self.ctx, (a, b))
    assert_type(c.constant, Tuple[_ConstVar, _ConstVar])


if __name__ == "__main__":
  unittest.main()
