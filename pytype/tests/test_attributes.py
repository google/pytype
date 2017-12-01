"""Test instance and class attributes."""

import unittest

from pytype import utils
from pytype.tests import test_base


class TestStrictNone(test_base.BaseTest):
  """Tests for strict attribute checking on None."""

  def setUp(self):
    super(TestStrictNone, self).setUp()
    self.options.tweak(strict_none=True)

  def testModuleConstant(self):
    self.Check("""
      x = None
      def f():
        return x.upper()
    """)

  def testClassConstant(self):
    self.Check("""
      class Foo(object):
        x = None
        def f(self):
          return self.x.upper()
    """)

  def testExplicitNone(self):
    errors = self.CheckWithErrors("""\
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"upper.*None")])

  def testMultiplePaths(self):
    errors = self.CheckWithErrors("""\
      x = None
      def f():
        z = None if __random__ else x
        y = z
        return y.upper()
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", r"upper.*None")])

  def testLateInitialization(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.x = None
        def f(self):
          return self.x.upper()
        def set_x(self):
          self.x = ""
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Optional
      class Foo(object):
        x = ...  # type: Optional[str]
        def f(self) -> Any: ...
        def set_x(self) -> None: ...
    """)

  def testPyiConstant(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: None
      """)
      self.Check("""
        import foo
        def f():
          return foo.x.upper()
      """, pythonpath=[d.path])

  def testPyiAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          x = ...  # type: None
      """)
      self.Check("""
        import foo
        def f():
          return foo.Foo.x.upper()
      """, pythonpath=[d.path])

  def testReturnValue(self):
    errors = self.CheckWithErrors("""\
      def f():
        pass
      def g():
        return f().upper()
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"upper.*None")])

  def testMethodReturnValue(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def f(self):
          pass
      def g():
        return Foo().f().upper()
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", r"upper.*None")])

  def testPyiReturnValue(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "def f() -> None: ...")
      errors = self.CheckWithErrors("""\
        import foo
        def g():
          return foo.f().upper()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "attribute-error", r"upper.*None")])

  def testPassThroughNone(self):
    errors = self.CheckWithErrors("""\
      def f(x):
        return x
      def g():
        return f(None).upper()
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"upper.*None")])

  def testShadowedLocalOrigin(self):
    self.Check("""
      x = None
      def f():
        y = None
        y = "hello"
        return x if __random__ else y
      def g():
        return f().upper()
    """)

  @unittest.skip("has_strict_none_origins can't tell if an origin is blocked.")
  def testBlockedLocalOrigin(self):
    self.Check("""
      x = None
      def f():
        v = __random__
        if v:
          y = None
        return x if v else y
      def g():
        return f().upper()
    """)

  def testReturnConstant(self):
    self.Check("""\
      x = None
      def f():
        return x
      def g():
        return f().upper()
    """)


class TestAttributes(test_base.BaseTest):
  """Tests for attributes."""

  def testSimpleAttribute(self):
    ty = self.Infer("""
      class A(object):
        def method1(self):
          self.a = 3
        def method2(self):
          self.a = 3j
    """)
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
    """)
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
    """)
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
    """)
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
    """)
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
    self.Check("""
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
    """, deep=False)
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
    """)
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
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> set
    """)

  def testGetMro(self):
    ty = self.Infer("""
      x = int.mro()
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: list
    """)

  def testCall(self):
    ty = self.Infer("""
      class A(object):
        def __call__(self):
          return 42
      x = A()()
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __getattribute__(self, name) -> int
      x = ...  # type: int
    """)

  def testAttrOnOptional(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()
    """)

  def testHasDynamicAttributes(self):
    self.Check("""\
      class Foo(object):
        has_dynamic_attributes = True
      Foo().baz
    """)

  def testHasDynamicAttributesUpperCase(self):
    self.Check("""\
      class Foo(object):
        HAS_DYNAMIC_ATTRIBUTES = True
      class Bar(Foo):
        pass
      Foo().baz
      # has_dynamic_attributes doesn't work for subclasses
      Bar().baz  # pytype: disable=attribute-error
    """)

  def testHasDynamicAttributesSubClass(self):
    # has_dynamic_attributes doesn't apply to subclasses
    _, errors = self.InferWithErrors("""\
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
      self.Check("""\
        import mod
        mod.Foo().baz
      """, pythonpath=[d.path])

  def testAttrOnStaticMethod(self):
    self.Check("""\
      import collections

      X = collections.namedtuple("X", "a b")
      X.__new__.__defaults__ = (1, 2)
      """)

  def testModuleTypeAttribute(self):
    self.Check("""
      import types
      v = None  # type: types.ModuleType
      v.some_attribute
    """)

  def testAttrOnNone(self):
    _, errors = self.InferWithErrors("""\
      def f(arg):
        x = "foo" if arg else None
        if not x:
          x.upper()
    """)
    self.assertErrorLogIs(errors, [(4, "none-attr")])

  def testIteratorOnNone(self):
    _, errors = self.InferWithErrors("""\
      def f():
        pass
      a, b = f()
    """)
    self.assertErrorLogIs(errors, [(3, "none-attr")])

  def testOverloadedBuiltin(self):
    self.Check("""
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
    """, deep=False)
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
    self.Check("""
      args = {}
      for x, y in sorted(args.iteritems()):
        x.values
    """)

  def testTypeParameterInstanceMultipleBindings(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        values = 42
      args = {A() if __random__ else True: ""}
      for x, y in sorted(args.iteritems()):
        x.values  # line 5
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", r"'values' on bool")])

  def testTypeParameterInstanceSetAttr(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      class Bar(object):
        def bar(self):
          d = {42: Foo()}
          for _, foo in sorted(d.iteritems()):
            foo.x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        x = ...  # type: int
      class Bar(object):
        def bar(self) -> None: ...
    """)

  def testCallableReturn(self):
    self.Check("""
      from typing import Callable
      class Foo(object):
        def __init__(self):
          self.x = 42
      v = None  # type: Callable[[], Foo]
      w = v().x
    """)

  def testPropertyOnUnion(self):
    ty = self.Infer("""
      class A():
        def __init__(self):
          self.foo = 1
      class B():
        def __init__(self):
          self.bar = 2
        @property
        def foo(self):
          return self.bar
      x = A() if __random__ else B()
      a = x.foo
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      x = ...  # type: Union[A, B]
      class A:
          foo = ...  # type: int
          def __init__(self) -> None: ...
      class B:
          bar = ...  # type: int
          foo = ...  # type: int
          def __init__(self) -> None: ...
    """)

if __name__ == "__main__":
  test_base.main()
