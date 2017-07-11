"""Test instance and class attributes."""

import unittest

from pytype import utils
from pytype.tests import test_inference


class TestAttributes(test_inference.InferenceTest):
  """Tests for attributes."""

  def testSimpleAttribute(self):
    ty = self.Infer("""
      class A(object):
        def method1(self):
          self.a = 3
        def method2(self):
          self.a = 3j
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        a = ...  # type: complex or int
        def method1(self) -> NoneType
        def method2(self) -> NoneType
    """)

  def testOutsideAttributeAccess(self):
    ty = self.Infer("""
      class A(object):
        pass
      def f1():
        A().a = 3
      def f2():
        A().a = 3j
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        a = ...  # type: complex or int
      def f1() -> NoneType
      def f2() -> NoneType
    """)

  def testPrivate(self):
    ty = self.Infer("""
      class C(object):
        def __init__(self):
          self._x = 3
        def foo(self):
          return self._x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class C(object):
        _x = ...  # type: int
        def foo(self) -> int
    """)

  def testPublic(self):
    ty = self.Infer("""
      class C(object):
        def __init__(self):
          self.x = 3
        def foo(self):
          return self.x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class C(object):
        x = ...  # type: int
        def foo(self) -> int
    """)

  def testCrosswise(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          if id(self):
            self.b = B()
        def set_on_b(self):
          self.b.x = 3
      class B(object):
        def __init__(self):
          if id(self):
            self.a = A()
        def set_on_a(self):
          self.a.x = 3j
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        b = ...  # type: B
        x = ...  # type: complex
        def set_on_b(self) -> NoneType
      class B(object):
        a = ...  # type: A
        x = ...  # type: int
        def set_on_a(self) -> NoneType
    """)

  def testAttrWithBadGetAttr(self):
    self.assertNoErrors("""
      class AttrA(object):
        def __getattr__(self, name2):
          pass
      class AttrB(object):
        def __getattr__(self):
          pass
      class AttrC(object):
        def __getattr__(self, x, y):
          pass
      class Foo(object):
        A = AttrA
        B = AttrB
        C = AttrC
        def foo(self):
          self.A
          self.B
          self.C
    """)

  def testInheritGetAttribute(self):
    ty = self.Infer("""
      class MyClass1(object):
        def __getattribute__(self, name):
          return super(MyClass1, self).__getattribute__(name)

      class MyClass2(object):
        def __getattribute__(self, name):
          return object.__getattribute__(self, name)
    """)
    self.assertTypesMatchPytd(ty, """
      class MyClass1(object): pass
      class MyClass2(object): pass
    """)

  def testGetAttribute(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return 42
      a = A()
      a.x = "hello world"
      x = a.x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
        def __getattribute__(self, name) -> int
      a = ...  # type: A
      x = ...  # type: int
    """)

  def testGetAttributeBranch(self):
    ty = self.Infer("""
      class A(object):
        x = "hello world"
      class B(object):
        def __getattribute__(self, name):
          return False
      def f(x):
        v = A()
        if x:
          v.__class__ = B
        return v.x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
      class B(object):
        def __getattribute__(self, name) -> bool
      def f(x) -> str or bool
    """)

  def testSetClass(self):
    ty = self.Infer("""
      def f(x):
        y = None
        y.__class__ = x.__class__
        return set([x, y])
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> set
    """)

  def testGetMro(self):
    ty = self.Infer("""
      x = int.mro()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: list
    """)

  def testCall(self):
    ty = self.Infer("""
      class A(object):
        def __call__(self):
          return 42
      x = A()()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __call__(self) -> int
      x = ...  # type: int
    """)

  @unittest.skip("Magic methods aren't computed")
  def testCallComputed(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return int
      x = A().__call__()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __getattribute__(self, name) -> int
      x = ...  # type: int
    """)

  def testAttrOnOptional(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()
    """)

  def testHasDynamicAttributes(self):
    self.assertNoErrors("""\
      class Foo(object):
        has_dynamic_attributes = True
      Foo().baz
    """)

  def testHasDynamicAttributesSubClass(self):
    # has_dynamic_attributes doesn't apply to subclasses
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        has_dynamic_attributes = True
      class Bar(Foo):
        pass
      Bar().baz
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", "baz")])

  def testHasDynamicAttributesPYI(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Foo(object):
          has_dynamic_attributes = True
      """)
      self.assertNoErrors("""\
        import mod
        mod.Foo().baz
      """, pythonpath=[d.path])

  def testAttrOnStaticMethod(self):
    self.assertNoErrors("""\
      import collections

      X = collections.namedtuple("X", "a b")
      X.__new__.__defaults__ = (1, 2)
      """)

  def testModuleTypeAttribute(self):
    self.assertNoErrors("""
      import types
      v = None  # type: types.ModuleType
      v.some_attribute
    """)

  def testAttrOnNone(self):
    _, errors = self.InferAndCheck("""\
      def f(arg):
        x = "foo" if arg else None
        if not x:
          x.upper()
    """)
    self.assertErrorLogIs(errors, [(4, "none-attr")])

  def testIteratorOnNone(self):
    _, errors = self.InferAndCheck("""\
      def f():
        pass
      a, b = f()
    """)
    self.assertErrorLogIs(errors, [(3, "none-attr")])

  def testOverloadedBuiltin(self):
    self.assertNoErrors("""
      if __random__:
        getattr = None
      else:
        getattr(__any_object__, __any_object__)
    """)

  def testTypeParameterInstance(self):
    ty = self.Infer("""
      class A(object):
        values = 42
      args = {A(): ""}
      for x, y in sorted(args.iteritems()):
        z = x.values
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      class A(object):
        values = ...  # type: int
      args = ...  # type: Dict[A, str]
      x = ...  # type: A
      y = ...  # type: str
      z = ...  # type: int
    """)

  def testEmptyTypeParameterInstance(self):
    self.assertNoErrors("""
      args = {}
      for x, y in sorted(args.iteritems()):
        x.values
    """)

  def testTypeParameterInstanceMultipleBindings(self):
    _, errors = self.InferAndCheck("""\
      class A(object):
        values = 42
      args = {A() if __random__ else True: ""}
      for x, y in sorted(args.iteritems()):
        x.values  # line 5
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", r"'values' on bool")])

  def testCallableReturn(self):
    self.assertNoErrors("""
      from typing import Callable
      class Foo(object):
        def __init__(self):
          self.x = 42
      v = None  # type: Callable[[], Foo]
      w = v().x
    """)


if __name__ == "__main__":
  test_inference.main()
