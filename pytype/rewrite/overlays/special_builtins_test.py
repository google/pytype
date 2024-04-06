from pytype.rewrite import context
from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import special_builtins

import unittest


class AssertTypeTest(unittest.TestCase):

  def test_types_match(self):
    ctx = context.Context()
    assert_type_func = special_builtins.AssertType(ctx)
    var = ctx.consts[0].to_variable()
    typ = abstract.SimpleClass(ctx, 'int', {}).to_variable()
    ret = assert_type_func.call(abstract.Args(posargs=(var, typ)))
    self.assertEqual(ret.get_return_value(), ctx.consts[None])


if __name__ == '__main__':
  unittest.main()
