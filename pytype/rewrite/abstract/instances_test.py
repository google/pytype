from typing import Dict, List

from pytype.rewrite.abstract import base
from pytype.rewrite.abstract import instances
from pytype.rewrite.flow import variables
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest

# Type aliases
_ConstVar = variables.Variable[base.PythonConstant]


class ListTest(test_utils.ContextfulTestBase):

  def test_constant_type(self):
    a = base.PythonConstant(self.ctx, "a").to_variable()
    c = instances.List(self.ctx, [a])
    assert_type(c.constant, List[_ConstVar])


class DictTest(test_utils.ContextfulTestBase):

  def test_constant_type(self):
    a = base.PythonConstant(self.ctx, "a").to_variable()
    b = base.PythonConstant(self.ctx, "1").to_variable()
    c = instances.Dict(self.ctx, {a: b})
    assert_type(c.constant, Dict[_ConstVar, _ConstVar])


if __name__ == "__main__":
  unittest.main()
