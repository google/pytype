from pytype.rewrite.abstract import abstract
from pytype.rewrite.abstract import test_utils
from pytype.rewrite.overlays import special_builtins

import unittest


class AssertTypeTest(test_utils.AbstractTestBase):

  def test_types_match(self):
    assert_type_func = special_builtins.AssertType(self.ctx)
    var = abstract.PythonConstant(self.ctx, 0).to_variable()
    typ = abstract.BaseClass(self.ctx, 'int', {}).to_variable()
    ret = assert_type_func.call(abstract.Args(posargs=(var, typ)))
    self.assertEqual(ret.get_return_value(),
                     abstract.PythonConstant(self.ctx, None))


if __name__ == '__main__':
  unittest.main()
