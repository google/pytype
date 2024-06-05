"""Tests for slots."""

from pytype.tests import test_base


class SlotsTest(test_base.BaseTest):
  """Tests for __slots__."""

  def test_slot_with_unicode(self):
    self.Check("""
      class Foo:
        __slots__ = (u"fo\\xf6", u"b\\xe4r", "baz")
      Foo().baz = 3
    """)

  def test_slot_with_bytes(self):
    self.CheckWithErrors("""
      class Foo:  # bad-slots
        __slots__ = (b"x",)
    """)


if __name__ == "__main__":
  test_base.main()
