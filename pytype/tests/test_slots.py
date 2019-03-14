"""Tests for slots."""

from pytype.tests import test_base


class SlotsTest(test_base.TargetIndependentTest):
  """Tests for __slots__."""

  def testSlots(self):
    ty = self.Infer("""
      class Foo(object):
        __slots__ = ("foo", "bar", "baz")
        def __init__(self):
          self.foo = 1
          self.bar = 2
          self.baz = 4
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        __slots__ = ["foo", "bar", "baz"]
        foo = ...  # type: int
        bar = ...  # type: int
        baz = ...  # type: int
    """)

  def testAmbiguousSlot(self):
    ty = self.Infer("""
      class Foo(object):
        __slots__ = () if __random__ else ("foo")
        def __init__(self):
          self.foo = 1
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        foo = ...  # type: int
    """)

  def testAmbiguousSlotEntry(self):
    self.Check("""
      class Foo(object):
        __slots__ = ("foo" if __random__ else "bar",)
    """)

  def testTupleSlot(self):
    self.Check("""
      class Foo(object):
        __slots__ = ("foo", "bar")
    """)

  def testTupleSlot_unicode(self):
    self.Check("""
      class Foo(object):
        __slots__ = (u"foo", u"bar")
    """)

  def testListSlot(self):
    ty = self.Infer("""
      class Foo(object):
        __slots__ = ["foo", "bar"]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        __slots__ = ["foo", "bar"]
    """)

  def testSlotWithNonStrings(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        __slots__ = (1, 2, 3)
    """)
    self.assertErrorLogIs(
        errors,
        [(2, "bad-slots", r"Invalid __slot__ entry: '1'")]
    )

  def testSetSlot(self):
    self.Check("""
      class Foo(object):
        __slots__ = {"foo", "bar"}  # Note: Python actually allows this.
      Foo().bar = 3
    """)

  def testSlotAsAttribute(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.__slots__ = ["foo"]
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        pass
    """)

  def testAssignAttribute(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        __slots__ = ("x", "y")
      foo = Foo()
      foo.x = 1  # ok
      foo.y = 2  # ok
      foo.z = 3  # error
    """)
    self.assertErrorLogIs(
        errors,
        [(7, "not-writable", r"z")]
    )

  def testObject(self):
    _, errors = self.InferWithErrors("""\
      object().foo = 42
    """)
    self.assertErrorLogIs(errors, [
        (1, "not-writable", r"object")
    ])

  def testAnyBaseClass(self):
    self.Check("""
      class Foo(__any_object__):
        __slots__ = ()
      Foo().foo = 42
    """)

  def testParameterizedBaseClass(self):
    _, errors = self.InferWithErrors("""\
      from typing import List
      class Foo(List[int]):
        __slots__ = ()
      Foo().foo = 42
    """)
    self.assertErrorLogIs(errors, [
        (4, "not-writable", r"foo")
    ])

  def testEmptySlots(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        __slots__ = ()
      Foo().foo = 42
    """)
    self.assertErrorLogIs(
        errors,
        [(3, "not-writable", r"foo")]
    )

  def testNamedTuple(self):
    _, errors = self.InferWithErrors("""\
      import collections
      Foo = collections.namedtuple("_", ["a", "b", "c"])
      foo = Foo(None, None, None)
      foo.a = 1
      foo.b = 2
      foo.c = 3
      foo.d = 4  # error
    """)
    self.assertErrorLogIs(errors, [
        (7, "not-writable", r"d")
    ])

  def testBuiltinAttr(self):
    _, errors = self.InferWithErrors("""\
      "foo".bar = 1
      u"foo".bar = 2
      ().bar = 3
      [].bar = 4
      {}.bar = 5
      set().bar = 6
      frozenset().bar = 7
      frozenset().bar = 8
      Ellipsis.bar = 9
      bytearray().bar = 10
      enumerate([]).bar = 11
      True.bar = 12
      (42).bar = 13
      (3.14).bar = 14
      (3j).bar = 15
      slice(1,10).bar = 17
      memoryview(b"foo").bar = 18
      range(10).bar = 19
    """)
    self.assertErrorLogIs(
        errors,
        [(line, "not-writable") for line in range(1, 19)]
    )

  def testGeneratorAttr(self):
    _, errors = self.InferWithErrors("""\
      def f(): yield 42
      f().foo = 42
    """)
    self.assertErrorLogIs(
        errors,
        [(2, "not-writable", r"foo")]
    )

  def testSetAttr(self):
    self.Check("""\
      class Foo(object):
        __slots__ = ()
        def __setattr__(self, name, value):
          pass
      class Bar(Foo):
        __slots__ = ()
      Foo().baz = 1
      Bar().baz = 2
    """)

  def testDescriptors(self):
    self.Check("""\
      class Descriptor(object):
        def __set__(self, obj, cls):
          pass
      class Foo(object):
        __slots__ = ()
        baz = Descriptor()
      class Bar(Foo):
        __slots__ = ()
      Foo().baz = 1
      Bar().baz = 2
    """)

  def testNameMangling(self):
    _, errors = self.InferWithErrors("""\
      class Bar(object):
        __slots__ = ["__baz"]
        def __init__(self):
          self.__baz = 42
      class Foo(Bar):
        __slots__ = ["__foo"]
        def __init__(self):
          self.__foo = 42
          self.__baz = 42  # __baz is class-private
    """)
    self.assertErrorLogIs(
        errors,
        [(9, "not-writable", "__baz")]
    )


test_base.main(globals(), __name__ == "__main__")
