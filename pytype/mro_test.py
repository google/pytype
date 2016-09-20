"""Tests for mro.py."""


from pytype import mro
from pytype.pytd import pytd

import unittest


class MroTest(unittest.TestCase):

  def testFlattenSuperclasses(self):
    cls_a = pytd.Class("A", (), (), (), ())
    cls_b = pytd.Class("B", (cls_a,), (), (), ())
    cls_c = pytd.Class("C", (cls_a,), (), (), ())
    cls_d = pytd.Class("D", (cls_c,), (), (), ())
    cls_e = pytd.Class("E", (cls_d, cls_b), (), (), ())
    self.assertItemsEqual(mro.flattened_superclasses(cls_e),
                          [cls_a, cls_b, cls_c, cls_d, cls_e])

