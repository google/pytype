"""Tests for slots."""

from pytype.tests import test_base


class SlotsTest(test_base.TargetPython27FeatureTest):
  """Tests for __slots__."""

  def test_builtin_attr(self):
    self.InferWithErrors("""
      buffer("foo").bar = 16  # not-writable
    """)

  def test_slot_with_bytes(self):
    self.Check("""
      class Foo(object):
        __slots__ = (b"x",)
    """)

  def test_slot_with_unicode(self):
    errors = self.CheckWithErrors("""
      class Foo(object):  # bad-slots[e]
        __slots__ = (u"fo\\xf6", u"b\\xe4r", "baz")
      Foo().baz = 3
    """)
    self.assertErrorRegexes(errors, {"e": r"fo\\xc3\\xb6"})


test_base.main(globals(), __name__ == "__main__")
