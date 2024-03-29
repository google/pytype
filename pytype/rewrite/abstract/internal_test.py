from typing import Any

from pytype.rewrite.abstract import internal
from pytype.rewrite.tests import test_utils

import unittest


class ConstKeyDictTest(test_utils.ContextfulTestBase):

  def test_asserts_dict(self):
    _ = internal.ConstKeyDict(self.ctx, {'a': self.ctx.ANY})
    with self.assertRaises(AssertionError):
      x: Any = ['a', 'b']
      _ = internal.ConstKeyDict(self.ctx, x)


class SplatTest(test_utils.ContextfulTestBase):

  def test_basic(self):
    # Basic smoke test, remove when we have some real functionality to test.
    x = internal.Splat(self.ctx, (1, 2, 3))
    self.assertEqual(x.iterable, (1, 2, 3))


if __name__ == '__main__':
  unittest.main()
