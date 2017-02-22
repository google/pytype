"""Tests for mro.py."""


from pytype import mro
from pytype.pytd import pytd

import unittest


class MroTest(unittest.TestCase):

  def testFlattenSuperclasses(self):
    cls_a = pytd.Class("A", None, (), (), (), ())
    cls_b = pytd.Class("B", None, (cls_a,), (), (), ())
    cls_c = pytd.Class("C", None, (cls_a,), (), (), ())
    cls_d = pytd.Class("D", None, (cls_c,), (), (), ())
    cls_e = pytd.Class("E", None, (cls_d, cls_b), (), (), ())
    self.assertItemsEqual(mro.flattened_superclasses(cls_e),
                          [cls_a, cls_b, cls_c, cls_d, cls_e])


if __name__ == '__main__':
  unittest.main()
