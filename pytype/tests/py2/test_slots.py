"""Tests for slots."""

from pytype.tests import test_base


class SlotsTest(test_base.TargetPython27FeatureTest):
  """Tests for __slots__."""

  def testBuiltinAttr(self):
    _, errors = self.InferWithErrors("""\
      buffer("foo").bar = 16
    """)
    self.assertErrorLogIs(errors, [(1, "not-writable")])

  def testSlotWithBytes(self):
    _ = self.Check("""\
      class Foo(object):
        __slots__ = (b"x",)
    """)

  def testSlotWithUnicode(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        __slots__ = (u"fo\\xf6", u"b\\xe4r", "baz")
      Foo().baz = 3
    """)
    self.assertErrorLogIs(errors, [(1, "bad-slots", r"fo\\xc3\\xb6")])


if __name__ == "__main__":
  test_base.main()
