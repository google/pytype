from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins

import unittest


class AssertTypeTest(unittest.TestCase):

  def test_types_match(self):
    assert_type_func = special_builtins.AssertType()
    var = abstract.PythonConstant(0).to_variable()
    typ = abstract.BaseClass('int', {}).to_variable()
    ret = assert_type_func.call(abstract.Args(posargs=(var, typ)))
    self.assertEqual(ret.get_return_value(), abstract.PythonConstant(None))


if __name__ == '__main__':
  unittest.main()
