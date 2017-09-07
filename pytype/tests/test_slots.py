"""Tests for slots."""

from pytype.tests import test_inference


class SlotsTest(test_inference.InferenceTest):
  """Tests for __slots__."""

  def testSlots(self):
    ty = self.Infer("""
      class Foo(object):
        __slots__ = ("foo", "bar", "baz")
        def __init__(self):
          self.foo = 1
          self.bar = 2
          self.baz = 4
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        __slots__ = ["foo", "bar", "baz"]
        foo = ...  # type: int
        bar = ...  # type: int
        baz = ...  # type: int
    """)

  def testAmbiguousSlot(self):
    ty, errors, = self.InferAndCheck("""
      class Foo(object):
        __slots__ = () if __random__ else ("foo")
        def __init__(self):
          self.foo = 1
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        foo = ...  # type: int
    """)
    self.assertErrorLogIs(errors, [])

  def testAmbiguousSlotEntry(self):
    self.assertNoErrors("""
      class Foo(object):
        __slots__ = ("foo" if __random__ else "bar",)
    """)

  def testTupleSlot(self):
    self.assertNoErrors("""
      class Foo(object):
        __slots__ = ("foo", "bar")
    """)

  def testListSlot(self):
    ty = self.Infer("""
      class Foo(object):
        __slots__ = ["foo", "bar"]
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        __slots__ = ["foo", "bar"]
    """)

  def testSlotWithNonStrings(self):
    _, errors = self.InferAndCheck("""
      class Foo(object):
        __slots__ = (1, 2, 3)
    """)
    self.assertErrorLogIs(
        errors,
        [(2, "bad-slots", r"Invalid __slot__ entry: '1'")]
    )

  def testSetSlot(self):
    self.assertNoErrors("""
      class Foo(object):
        __slots__ = {"foo", "bar"}  # Note: Python actually allows this.
      Foo().bar = 3
    """)

  def testSlotWithUnicode(self):
    self.assertNoErrors("""
      class Foo(object):
        __slots__ = (u"fo\xf6", u"b\xe4r", "baz")
      Foo().baz = 3
    """)

  def testSlotAsAttribute(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.__slots__ = ["foo"]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        pass
    """)

  def testSlotAsLateClassAttribute(self):
    ty = self.Infer("""
      class Foo(object): pass
      # It's rare to see this pattern in the wild. The only occurrence, outside
      # of tests, seems to be https://www.gnu.org/software/gss/manual/gss.html.
      # Note this doesn't actually do anything! Python ignores the next line.
      Foo.__slots__ = ["foo"]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        pass
    """)


if __name__ == "__main__":
  test_inference.main()
