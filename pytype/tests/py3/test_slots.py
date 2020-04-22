"""Tests for slots."""

from pytype.tests import test_base


class SlotsTest(test_base.TargetPython3FeatureTest):
  """Tests for __slots__."""

  def test_slot_with_unicode(self):
    self.Check("""
      class Foo(object):
        __slots__ = (u"fo\\xf6", u"b\\xe4r", "baz")
      Foo().baz = 3
    """)

  def test_slot_with_bytes(self):
    self.CheckWithErrors("""
      class Foo(object):  # bad-slots
        __slots__ = (b"x",)
    """)


test_base.main(globals(), __name__ == "__main__")
