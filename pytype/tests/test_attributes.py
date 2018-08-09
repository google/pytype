"""Test instance and class attributes."""

from pytype import file_utils
from pytype.tests import test_base


class TestStrictNone(test_base.TargetIndependentTest):
  """Tests for strict attribute checking on None."""

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

  def testClassConstantError(self):
    errors = self.CheckWithErrors("""\
      x = None
      class Foo(object):
        x = x.upper()
    """)
    self.assertErrorLogIs(errors, [(3, "attribute-error", r"upper.*None")])

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
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: None
      """)
      self.Check("""
        import foo
        def f():
          return foo.x.upper()
      """, pythonpath=[d.path])

  def testPyiAttribute(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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

  @test_base.skip("has_strict_none_origins can't tell if an origin is blocked.")
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

  def testUnpackedNone(self):
    errors = self.CheckWithErrors("""\
      _, a = 42, None
      b = a.upper()
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"upper.*None")])

  def testFunctionDefault(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def __init__(self, v=None):
          v.upper()
      def f():
        Foo()
    """)
    self.assertErrorLogIs(
        errors, [(3, "attribute-error", r"upper.*None.*Traceback.*line 5")])

  def testKeepNoneReturn(self):
    ty = self.Infer("""
      def f():
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> None: ...
    """)

  def testKeepNoneYield(self):
    ty = self.Infer("""
      def f():
        yield None
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator, Any
      def f() -> Generator[None, Any, None]
    """)

  def testKeepContainedNoneReturn(self):
    ty = self.Infer("""
      def f():
        return [None]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f() -> List[None]
    """)

  def testDiscardNoneReturn(self):
    ty = self.Infer("""
      x = None
      def f():
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: None
      def f() -> Any
    """)

  def testDiscardNoneYield(self):
    ty = self.Infer("""
      x = None
      def f():
        yield x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      x = ...  # type: None
      def f() -> Generator[Any, Any, None]
    """)

  def testDiscardContainedNoneReturn(self):
    ty = self.Infer("""
      x = None
      def f():
        return [x]
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: None
      def f() -> list
    """)

  def testDiscardAttributeNoneReturn(self):
    ty = self.Infer("""
      class Foo:
        x = None
      def f():
        return Foo.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo:
        x = ...  # type: None
      def f() -> Any
    """)

  def testGetItem(self):
    errors = self.CheckWithErrors("""\
      def f():
        x = None
        return x[0]
    """)
    self.assertErrorLogIs(
        errors, [(3, "unsupported-operands", r"__getitem__.*None.*int")])

  def testIgnoreGetItem(self):
    self.Check("""
      x = None
      def f():
        return x[0]
    """)

  def testIgnoreIter(self):
    self.Check("""
      x = None
      def f():
        return [y for y in x]
    """)

  def testContains(self):
    errors = self.CheckWithErrors("""\
      def f():
        x = None
        return 42 in x
    """)
    self.assertErrorLogIs(
        errors, [(3, "unsupported-operands", r"__contains__.*None.*int")])

  def testIgnoreContains(self):
    self.Check("""
      x = None
      def f():
        return 42 in x
    """)

  def testProperty(self):
    self.Check("""
      class Foo(object):
        def __init__(self):
          self._dofoo = __random__
        @property
        def foo(self):
          return "hello" if self._dofoo else None
      foo = Foo()
      if foo.foo:
        foo.foo.upper()
    """)

  def testIsInstance(self):
    self.Check("""
      class Foo(object):
        def f(self):
          instance = None if __random__ else {}
          if instance is not None:
            self.g(instance)
        def g(self, instance):
          if isinstance(instance, str):
            instance.upper()  # line 10
    """)

  def testImpossibleReturnType(self):
    self.Check("""
      from typing import Dict
      def f():
        d = None  # type: Dict[str, str]
        instance = d.get("hello")
        return instance if instance else "world"
      def g():
        return f().upper()
    """)

  def testNoReturn(self):
    self.Check("""
      def f():
        text_value = "hello" if __random__ else None
        if not text_value:
          missing_value()
        return text_value.strip()
      def missing_value():
        raise ValueError()
    """)


class TestAttributes(test_base.TargetIndependentTest):
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
      from typing import Any
      class A(object):
        x = ...  # type: str
      class B(object):
        def __getattribute__(self, name) -> bool
      def f(x) -> Any
    """)

  @test_base.skip("TODO(b/63407497): implement strict checking for __setitem__")
  def testUnionSetAttribute(self):
    ty, errors = self.InferWithErrors("""\
      class A(object):
        x = "Hello world"
      def f(i):
        t = A()
        l = [t]
        l[i].x = 1  # line 6
        return l[i].x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        x = ...  # type: str
      def f(i) -> Any
    """)
    self.assertErrorLogIs(errors, [(6, "not-writable")])

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

  @test_base.skip("Magic methods aren't computed")
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

  def testHasDynamicAttributes(self):
    self.Check("""\
      class Foo1(object):
        has_dynamic_attributes = True
      class Foo2(object):
        _has_dynamic_attributes = True
      class Foo3(object):
        HAS_DYNAMIC_ATTRIBUTES = True
      class Foo4(object):
        _HAS_DYNAMIC_ATTRIBUTES = True
      Foo1().baz
      Foo2().baz
      Foo3().baz
      Foo4().baz
    """)

  def testHasDynamicAttributesUpperCase(self):
    self.Check("""\
      class Foo(object):
        HAS_DYNAMIC_ATTRIBUTES = True
      Foo().baz
    """)

  def testHasDynamicAttributesSubClass(self):
    self.Check("""\
      class Foo(object):
        has_dynamic_attributes = True
      class Bar(Foo):
        pass
      Foo().baz
      Bar().baz
    """)

  def testHasDynamicAttributesPYI(self):
    with file_utils.Tempdir() as d:
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
    self.assertErrorLogIs(errors, [(4, "attribute-error")])

  def testIteratorOnNone(self):
    _, errors = self.InferWithErrors("""\
      def f():
        pass
      a, b = f()
    """)
    self.assertErrorLogIs(errors, [(3, "attribute-error")])

  def testOverloadedBuiltin(self):
    self.Check("""
      if __random__:
        getattr = None
      else:
        getattr(__any_object__, __any_object__)
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

  @test_base.skip("Needs vm._get_iter() to iterate over individual bindings.")
  def testMetaclassIter(self):
    self.Check("""
      class Meta(type):
        def __iter__(cls):
          return iter([])
      class Foo(object):
        __metaclass__ = Meta
        def __iter__(self):
          return iter([])
      for _ in Foo:
        pass
    """)

  @test_base.skip("Needs better handling of __getitem__ in vm._get_iter().")
  def testMetaclassGetItem(self):
    self.Check("""
      class Meta(type):
        def __getitem__(cls, x):
          return 0
      class Foo(object):
        __metaclass__ = Meta
        def __getitem__(self, x):
          return 0
      for _ in Foo:
        pass
    """)

  @test_base.skip("Needs vm._get_iter() to iterate over individual bindings.")
  def testBadIter(self):
    errors = self.CheckWithErrors("""\
      v = [] if __random__ else 42
      for _ in v:
        pass
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"__iter__.*int")])

  def testBadGetItem(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def __getitem__(self, x):
          return 0
      v = Foo() if __random__ else 42
      for _ in v:  # line 5
        pass
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error",
                                    r"__iter__.*int.*Union\[Foo, int\]")])

  def testBadContains(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def __iter__(self):
          return iter([])
      v = Foo() if __random__ else 42
      if 42 in v:  # line 5
        pass
    """)
    self.assertErrorLogIs(
        errors, [(5, "unsupported-operands",
                  r"__contains__.*'Union\[Foo, int\]' and 'int'")])

  def testSubclassShadowing(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """\
        class X:
          b = ...  # type: int
        """)
      self.Check("""\
        import foo
        a = foo.X()
        a.b  # The attribute exists
        if __random__:
          a.b = 1  # A new value is assigned
        else:
          a.b  # The original attribute isn't overwritten by the assignment
        """, pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
