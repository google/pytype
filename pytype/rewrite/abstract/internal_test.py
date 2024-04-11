from typing import Any

from pytype.rewrite.abstract import internal
from pytype.rewrite.tests import test_utils

import unittest


class ConstKeyDictTest(test_utils.ContextfulTestBase):

  def test_asserts_dict(self):
    _ = internal.ConstKeyDict(self.ctx, {
        'a': self.ctx.consts.Any.to_variable()
    })
    with self.assertRaises(AssertionError):
      x: Any = ['a', 'b']
      _ = internal.ConstKeyDict(self.ctx, x)


class SplatTest(test_utils.ContextfulTestBase):

  def test_basic(self):
    # Basic smoke test, remove when we have some real functionality to test.
    cls = self.ctx.abstract_loader.load_raw_type(tuple)
    seq = cls.instantiate().to_variable()
    x = internal.Splat(self.ctx, seq)
    self.assertEqual(x.iterable, seq)


if __name__ == '__main__':
  unittest.main()
