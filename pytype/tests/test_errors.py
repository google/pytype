"""Tests for displaying errors."""

import unittest

from pytype import utils
from pytype.tests import test_base


class ErrorTest(test_base.BaseTest):
  """Tests for errors."""

  def testDeduplicate(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        y = 42
        y.foobar
      f(3)
      f(4)
    """)
    self.assertErrorLogIs(errors, [(3, "attribute-error", r"'foobar' on int$")])

  def testUnknownGlobal(self):
    _, errors = self.InferWithErrors("""
      def f():
        return foobar()
    """)
    self.assertErrorLogIs(errors, [(3, "name-error", r"foobar")])

  def testInvalidAttribute(self):
    ty, errors = self.InferWithErrors("""\
      class A(object):
        pass
      def f():
        (3).parrot
        return "foo"
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        pass

      def f() -> str
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"parrot.*int")])

  def testImportError(self):
    _, errors = self.InferWithErrors("""\
      import rumplestiltskin
    """)
    self.assertErrorLogIs(errors, [(1, "import-error", r"rumplestiltskin")])

  def testImportFromError(self):
    _, errors = self.InferWithErrors("""\
      from sys import foobar
    """)
    self.assertErrorLogIs(errors, [(1, "import-error", r"sys\.foobar")])

  def testNameError(self):
    _, errors = self.InferWithErrors("""\
      foobar
    """)
    self.assertErrorLogIs(errors, [(1, "name-error", r"foobar")])

  def testUnsupportedOperands(self):
    _, errors = self.InferWithErrors("""\
      def f():
        x = "foo"
        y = "bar"
        return x ^ y
    """)
    self.assertErrorLogIs(errors, [(4, "unsupported-operands",
                                    r"__xor__.*str.*str")])

  def testUnsupportedOperands2(self):
    _, errors = self.InferWithErrors("""
      def f():
        x = "foo"
        y = 3
        return x + y
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types",
                                    r"Expected.*y: str.*Actual.*y: int")])

  def testWrongArgCount(self):
    _, errors = self.InferWithErrors("""\
      hex(1, 2, 3, 4)
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-count", r"expects 1.*got 4")])

  def testWrongArgTypes(self):
    _, errors = self.InferWithErrors("""\
      hex(3j)
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-types", r"int.*complex")])

  def testInterpreterFunctionNameInMsg(self):
    _, errors = self.InferWithErrors("""\
      class A(list): pass
      A.append(3)
    """)
    self.assertErrorLogIs(
        errors,
        [(2, "missing-parameter", r"function list.append")]
    )

  def testPyTDFunctionNameInMsg(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "class A(list): pass")
      _, errors = self.InferWithErrors("""\
        import foo
        foo.A.append(3)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(
          errors,
          [(2, "missing-parameter", r"function list.append")]
      )

  def testBuiltinFunctionNameInMsg(self):
    _, errors = self.InferWithErrors("""\
      x = list
      x += (1,2)
      """)
    self.assertErrorLogIs(
        errors,
        [(2, "missing-parameter", r"function list.__iadd__")]
    )

  def testRewriteBuiltinFunctionName(self):
    """Should rewrite `function __builtin__.len` to `built-in function len`."""
    _, errors = self.InferWithErrors("x = len(None)")
    self.assertErrorLogIs(
        errors,
        [(1, "wrong-arg-types", r"Built-in function len")]
    )

  def BoundMethodNameInMsg(self):
    _, errors = self.InferWithErrors("""\
      "".join(1)
      """)
    self.assertErrorLogIs(
        errors,
        [(1, "missing-parameter", r"Function str.join")]
    )

  def testPrettyPrintWrongArgs(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(a: int, b: int, c: int, d: int, e: int): ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f(1, 2, 3, "four", 5)
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [
        (2, "wrong-arg-types", ("a, b, c, d: int, [.][.][.].*"
                                "a, b, c, d: str, [.][.][.]"))])

  def testInvalidBaseClass(self):
    _, errors = self.InferWithErrors("""\
      class Foo(3):
        pass
    """)
    self.assertErrorLogIs(errors, [(1, "base-class-error")])

  def testInvalidIteratorFromImport(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Codec(object):
            def __init__(self) -> None: ...
      """)
      _, errors = self.InferWithErrors("""
        import mod
        def f():
          for row in mod.Codec():
            pass
      """, pythonpath=[d.path])
      error = r"No attribute.*__iter__.*on mod\.Codec"
      self.assertErrorLogIs(errors, [(4, "attribute-error", error)])

  def testInvalidIteratorFromClass(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        pass
      def f():
        for row in A():
          pass
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"__iter__.*A")])

  def testIterOnModule(self):
    errors = self.CheckWithErrors("""\
      import sys
      for _ in sys:
        pass
    """)
    self.assertErrorLogIs(
        errors, [(2, "module-attr", r"__iter__.*module 'sys'")])

  def testInheritFromGeneric(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]): ...
        class Bar(Foo[int]): ...
      """)
      _, errors = self.InferWithErrors("""\
        import mod
        chr(mod.Bar())
      """, pythonpath=[d.path])
      # "Line 3, in f: Can't retrieve item out of dict. Empty?"
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"int.*mod\.Bar")])

  def testWrongKeywordArg(self):
    with utils.Tempdir() as d:
      d.create_file("mycgi.pyi", """
        def escape(x: str or unicode) -> str or unicode
      """)
      _, errors = self.InferWithErrors("""\
        import mycgi
        def foo(s):
          return mycgi.escape(s, quote=1)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "wrong-keyword-args",
                                      r"quote.*mycgi\.escape")])

  def testMissingParameter(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar(xray, yankee, zulu) -> str
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.bar(1, 2)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "missing-parameter",
                                      r"zulu.*foo\.bar")])

  def testBadInheritance(self):
    _, errors = self.InferWithErrors("""\
      class X:
          pass
      class Bar(X):
          pass
      class Baz(X, Bar):
          pass
    """)
    self.assertErrorLogIs(errors, [(5, "mro-error")])

  def testBadCall(self):
    with utils.Tempdir() as d:
      d.create_file("other.pyi", """
        def foo(x: int, y: str) -> str: ...
      """)
      _, errors = self.InferWithErrors("""\
        import other
        other.foo(1.2, [])
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (2, "wrong-arg-types", r"\(x: int")])

  def testCallUncallable(self):
    _, errors = self.InferWithErrors("""\
      0()
    """)
    self.assertErrorLogIs(errors, [(1, "not-callable", r"int")])

  def testSuperError(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        def __init__(self):
          super(A, self, "foo").__init__()
    """)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-count", "2.*3")])

  def testAttributeError(self):
    with utils.Tempdir() as d:
      d.create_file("modfoo.pyi", "")
      _, errors = self.InferWithErrors("""\
        class Foo(object):
          def __getattr__(self, name):
            return "attr"
        def f():
          return Foo.foo  # line 5
        def g(x):
          if x:
            y = None
          else:
            y = 1
          return y.bar  # line 11
        def h():
          return Foo().foo  # No error
        import modfoo
        modfoo.baz  # line 15
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (5, "attribute-error", r"No attribute 'foo' on Type\[Foo\]"),
          (11, "attribute-error",
           r"No attribute 'bar' on None\nIn Union\[None, int\]"),
          (11, "attribute-error",
           r"No attribute 'bar' on int\nIn Union\[None, int\]"),
          (15, "module-attr",
           "No attribute 'baz' on module 'modfoo'")])

  def testAttributeErrorGetAttribute(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def __getattribute__(self, name):
          return "attr"
      def f():
        return Foo().x  # There should be no error on this line.
      def g():
        return Foo.x
    """)
    self.assertErrorLogIs(errors, [(7, "attribute-error", r"x")])

  def testNoneAttribute(self):
    _, errors = self.InferWithErrors("""\
      None.foo
    """)
    self.assertErrorLogIs(errors, [(1, "attribute-error", r"foo")])

  def testPyiType(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: list[int]) -> int: ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f([""])
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types",
                                      r"List\[int\].*List\[str\]")])

  def testTooManyArgs(self):
    _, errors = self.InferWithErrors("""\
      def f():
        pass
      f(3)
    """, deep=True)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-count", r"0.*1")])

  def testTooFewArgs(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        pass
      f()
    """, deep=True)
    self.assertErrorLogIs(errors, [(3, "missing-parameter", r"x.*f")])

  def testDuplicateKeyword(self):
    _, errors = self.InferWithErrors("""\
      def f(x, y):
        pass
      f(3, x=3)
    """, deep=True)
    self.assertErrorLogIs(errors, [(3, "duplicate-keyword-argument", r"f.*x")])

  def testBadImport(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error")])

  def testBadImportDependency(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from b import X
        class Y(X): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error")])

  def testBadImportFrom(self):
    with utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      d.create_file("foo/__init__.pyi", "")
      _, errors = self.InferWithErrors("""\
        from foo import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"foo\.a")])

  def testBadImportFromDependency(self):
    with utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
          from a import X
          class Y(X): ...
      """)
      d.create_file("foo/__init__.pyi", "")
      _, errors = self.InferWithErrors("""\
        from foo import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"foo\.a")])

  def testBadContainer(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import SupportsInt
        class A(SupportsInt[int]): pass
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error",
                                      r"SupportsInt is not a container")])

  def testBadTypeParameterOrder(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Generic[K, V], Generic[V, K]): pass
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"Illegal.*order.*a\.A")])

  def testDuplicateTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T, T]): pass
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"T")])

  def testTypeParameterInModuleConstant(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        x = ...  # type: T
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"a.*T.*a\.x")])

  def testTypeParameterInClassAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          x = ...  # type: T
      """)
      _, errors = self.InferWithErrors("""\
        import a
        def f():
          return a.A.x
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "unbound-type-param", r"x.*A.*T")])

  def testUnboundTypeParameterInInstanceAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        class A(object):
          x = ...  # type: T
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"a.*T.*a\.A\.x")])

  def testPrintUnionArg(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(x: int or str) -> None
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.f(4.2)
      """, deep=True, pythonpath=[d.path])
      pattern = r"Expected.*Union\[int, str\].*Actually passed"
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", pattern)])

  def testPrintTypeArg(self):
    _, errors = self.InferWithErrors("""\
      hex(int)
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(1, "wrong-arg-types", r"Actually passed.*Type\[int\]")])

  def testNotSupported(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generic
    """)
    self.assertErrorLogIs(errors, [(1, "not-supported-yet")])

  def testDeleteFromSet(self):
    _, errors = self.InferWithErrors("""\
      s = {1}
      del s[1]
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"__delitem__")])

  def testBadReference(self):
    ty, errors = self.InferWithErrors("""\
      def main():
        x = foo
        for foo in []:
          pass
        return x
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "name-error", r"foo")])
    # Make sure we recovered from the error and got the right return type
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def main() -> Any
    """)

  def testSetIntAttribute(self):
    _, errors = self.InferWithErrors("""\
      x = 42
      x.y = 42
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "not-writable", r"y.*int")])

  def testInvalidParametersOnMethod(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __init__(self, x: int) -> None
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.A("")
        x = a.A("", 42)
        x = a.A(42, y="")
        x = a.A(42, x=42)
        x = a.A()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"A\.__init__"),
                                     (3, "wrong-arg-count", r"A\.__init__"),
                                     (4, "wrong-keyword-args", r"A\.__init__"),
                                     (5, "duplicate-keyword-argument",
                                      r"A\.__init__"),
                                     (6, "missing-parameter", r"A\.__init__")])

  def testDuplicateKeywords(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x, *args, y) -> None
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f(1, y=2)
        foo.f(1, 2, y=3)
        foo.f(1, x=1)
        # foo.f(y=1, y=2)  # caught by compiler
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (4, "duplicate-keyword-argument"),
      ])

  def testInvalidParametersDetails(self):
    _, errors = self.InferWithErrors("""\
      float(list())
      float(1, list(), foobar=str)
      float(1, foobar=list())
      float(1, x="")
      hex()
    """)
    self.assertErrorLogIs(errors, [
        (1, "wrong-arg-types",
         r"Actually passed:.*self, x: List\[nothing\]"),
        (2, "wrong-arg-count", r"Actually passed:.*self, x, "
         r"_, foobar"),
        (3, "wrong-keyword-args",
         r"Actually passed:.*self, x, foobar"),
        (4, "duplicate-keyword-argument",
         r"Actually passed:.*self, x, x"),
        (5, "missing-parameter", r"Actually passed: \(\)")
    ])

  def testBadSuperClass(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        def f(self):
          return "foo"

      class B(A):
        def f(self):
          return super(self, B).f()  # should be super(B, self)
    """, deep=True)
    self.assertErrorLogIs(errors, [
        (7, "wrong-arg-types", r"cls: type.*cls: B")])

  @unittest.skip("Need to type-check second argument to super")
  def testBadSuperInstance(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        pass
      class B(A):
        def __init__(self):
          super(B, A).__init__()  # A cannot be the second argument to super
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(5, "wrong-arg-types", r"Type\[B\].*Type\[A\]")])

  def testBadNameImport(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        import typing
        x = ...  # type: typing.Rumpelstiltskin
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"Rumpelstiltskin")])

  def testBadNameImportFrom(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Rumpelstiltskin
        x = ...  # type: Rumpelstiltskin
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"Rumpelstiltskin")])

  def testMatchType(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type
        class A(object): ...
        class B(A): ...
        class C(object): ...
        def f(x: Type[A]) -> bool
      """)
      ty, errors = self.InferWithErrors("""\
        import a
        x = a.f(a.A)
        y = a.f(a.B)
        z = a.f(a.C)
      """, pythonpath=[d.path], deep=True)
      error = r"Expected.*Type\[a\.A\].*Actual.*Type\[a\.C\]"
      self.assertErrorLogIs(errors, [(4, "wrong-arg-types", error)])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        x = ...  # type: bool
        y = ...  # type: bool
        z = ...  # type: Any
      """)

  def testMatchParameterizedType(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Type, TypeVar
        T = TypeVar("T")
        class A(Generic[T]): ...
        class B(A[str]): ...
        def f(x: Type[A[int]]): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.f(a.B)
      """, pythonpath=[d.path], deep=True)
      expected_error = r"Expected.*Type\[a\.A\[int\]\].*Actual.*Type\[a\.B\]"
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", expected_error)])

  def testMROError(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object): ...
        class B(object): ...
        class C(A, B): ...
        class D(B, A): ...
        class E(C, D): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.E()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "mro-error", r"E")])

  def testBadMRO(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(BaseException, ValueError): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
        class B(a.A): pass
        raise a.A()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "mro-error", r"A")])

  def testUnsolvableAsMetaclass(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      d.create_file("b.pyi", """
        from a import A
        class B(metaclass=A): ...
      """)
      _, errors = self.InferWithErrors("""\
        import b
        class C(b.B):
          def __init__(self):
            f = open(self.x, 'r')
      """, pythonpath=[d.path], deep=True)
      self.assertErrorLogIs(errors, [(4, "attribute-error", r"x.*C")])

  def testDontTimeoutOnComplex(self):
    # Tests that we can solve a complex file without timing out.
    # Useful for catching large performance regressions.
    ty = self.Infer("""\
      if __random__:
        x = [1]
      else:
        x = [1j]
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: Any
    """)

  def testFailedFunctionCall(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(x: str, y: int) -> bool
        def f(x: str) -> bool
      """)
      _, errors = self.InferWithErrors("""\
        import a
        x = a.f(0, "")
      """, pythonpath=[d.path])
      # Tests that [wrong-arg-types] rather than [wrong-arg-count] is reported
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"")])

  def testNoncomputableMethod(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def copy(x: T) -> T
      """)
      _, errors = self.InferWithErrors("""\
        import a
        class A(object):
          def __getattribute__(self, name):
            return a.copy(self)
        x = A()()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(5, "not-callable", r"A")])

  def testBadTypeName(self):
    _, errors = self.InferWithErrors("""\
      X = type(3, (int, object), {"a": 1})
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-types", r"Actual.*int")])

  def testBadTypeBases(self):
    _, errors = self.InferWithErrors("""\
      X = type("X", (42,), {"a": 1})
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-types",
                                    r"Actual.*Tuple\[int\]")])

  def testHalfBadTypeBases(self):
    _, errors = self.InferWithErrors("""\
      X = type("X", (42, object), {"a": 1})
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-types",
                                    r"Actual.*Tuple\[int, Type\[object\]\]")])

  def testBadTypeMembers(self):
    _, errors = self.InferWithErrors("""\
      X = type("X", (int, object), {0: 1})
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-types",
                                    r"Actual.*Dict\[int, int\]")])

  def testUnion(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def f(x: int):
        pass
      if __random__:
        i = 0
      else:
        i = 1
      x = (3.14, "")
      f(x[i])
    """)
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types",
                                    r"Actually passed:.*Union\[float, str\]")])

  def testRecursion(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(B): ...
        class B(A): ...
      """)
      ty, errors = self.InferWithErrors("""\
        import a
        v = a.A()
        x = v.x  # No error because there is an Unsolvable in the MRO of a.A
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        v = ...  # type: a.A
        x = ...  # type: Any
      """)
      self.assertErrorLogIs(errors, [(2, "recursion-error", r"a\.A")])

  def testInvalidAnnotations(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      from typing import Dict, List, Union
      def f1(x: Dict):  # okay
        pass
      def f2(x: Dict[str]):  # okay, "Any" is automatically filled in for V
        pass
      def f3(x: List[int, str]):
        pass
      def f4(x: Union):
        pass
    """)
    self.assertErrorLogIs(errors, [(7, "invalid-annotation", r"1.*2"),
                                   (9, "invalid-annotation", r"Union.*x")])

  def testEmptyUnionOrOptional(self):
    with utils.Tempdir() as d:
      d.create_file("f1.pyi", """\
        def f(x: Union): ...
      """)
      d.create_file("f2.pyi", """\
        def f(x: Optional): ...
      """)
      _, errors = self.InferWithErrors("""\
        import f1
        import f2
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"f1.*Union"),
                                     (2, "pyi-error", r"f2.*Optional")])

  def testPrintUnsolvable(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      from typing import List
      def f(x: List[nonsense], y: str, z: float):
        pass
      f({nonsense}, "", "")
    """)
    self.assertErrorLogIs(errors, [
        (3, "name-error", r"nonsense"),
        (5, "name-error", r"nonsense"),
        (5, "wrong-arg-types", r"Expected:.*x: list.*Actual.*x: set")])

  def testPrintUnionOfContainers(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def f(x: str):
        pass
      if __random__:
        x = dict
      else:
        x = [float]
      f(x)
    """)
    error = r"Actual.*Union\[List\[Type\[float\]\], Type\[dict\]\]"
    self.assertErrorLogIs(errors, [(8, "wrong-arg-types", error)])

  def testBadDictAttribute(self):
    _, errors = self.InferWithErrors("""\
      x = {"a": 1}
      y = x.a
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error",
                                    r"a.*Dict\[str, int\]")])

  def testBadPyiDict(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict
        x = ...  # type: Dict[str, int, float]
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"2.*3")])

  def testWrongBrackets(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      from typing import List
      def f(x: List(str)):
        pass
    """)
    self.assertErrorLogIs(errors, [(3, "not-callable", r"List")])

  def testInterpreterClassPrinting(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      class Foo(object): pass
      def f(x: str): pass
      f(Foo())
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types", r"str.*Foo")])

  def testCallNone(self):
    _, errors = self.InferWithErrors("""\
      None()
    """)
    self.assertErrorLogIs(errors, [(1, "not-callable")])

  def testInNone(self):
    _, errors = self.InferWithErrors("""\
      3 in None
    """)
    self.assertErrorLogIs(errors, [(1, "unsupported-operands")])

  def testNoAttrError(self):
    _, errors = self.InferWithErrors("""\
      if __random__:
        y = 42
      else:
        y = "foo"
      y.upper
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error")])

  def testAttrError(self):
    _, errors = self.InferWithErrors("""\
      if __random__:
        y = 42
      else:
        y = "foo"
      y.upper
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", "upper.*int")])

  def testPrintDictAndTuple(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      from typing import Tuple
      tup = None  # type: Tuple[int, ...]
      dct = None  # type: dict[str, int]
      def f1(x: (int, str)):  # line 5
        pass
      def f2(x: tup):  # line 7
        pass
      def g1(x: {"a": 1}):  # line 9
        pass
      def g2(x: dct):  # line 11
        pass
    """)
    self.assertErrorLogIs(errors, [
        (5, "invalid-annotation", r"(int, str).*Not a type"),
        (7, "invalid-annotation",
         r"instance of Tuple\[int, \.\.\.\].*Not a type"),
        (9, "invalid-annotation", r"{'a': '1'}.*Not a type"),
        (11, "invalid-annotation", r"instance of Dict\[str, int\].*Not a type")
    ])

  def testMoveUnionInward(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def f() -> str:
        y = "hello" if __random__ else u"hello"
        yield y
    """)
    self.assertErrorLogIs(errors, [(
        4, "bad-return-type",
        r"Generator\[Union\[str, unicode\], None, None\]")])

  def testPrintCallableInstance(self):
    _, errors = self.InferWithErrors("""\
      from typing import Callable
      v = None  # type: Callable[[int], str]
      hex(v)
    """)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-types",
                                    r"Actual.*Callable\[\[int\], str\]")])

  def testSameNameAndLine(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        return x + 42
      f("hello")
      f(u"world")
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"str.*int"),
                                   (2, "wrong-arg-types", r"unicode.*int")])

  def testKwargOrder(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(*args, y, x, z: int): ...
        def g(x): ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f(x=1, y=2, z="3")
        foo.g(42, v4="the", v3="quick", v2="brown", v1="fox")
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (2, "wrong-arg-types", r"x, y, z.*x, y, z"),
          (3, "wrong-keyword-args", r"v1, v2, v3, v4")])

  def testBadBaseClass(self):
    _, errors = self.InferWithErrors("""\
      class Foo(None): pass
      class Bar(None if __random__ else 42): pass
    """)
    self.assertErrorLogIs(errors, [
        (1, "base-class-error", r"Invalid base class: None"),
        (2, "base-class-error", r"Union\[<instance of int>, None\]")])

  def testCallableInUnsupportedOperands(self):
    _, errors = self.InferWithErrors("""\
      def f(x, y=None): pass
      f in f
    """)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"Callable\[\[Any, Any\], Any\].*"
                                    r"Callable\[\[Any, Any\], Any\]")])

  def testInnerClassError(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def f(x: str): pass
      def g():
        class Foo(object): pass
        f(Foo())
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"x: str.*x: Foo")])

  def testInnerClassError2(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def f():
        class Foo(object): pass
        def g(x: Foo): pass
        g("")
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"x: Foo.*x: str")])

  def testCleanNamedtupleNames(self):
    # Make sure the namedtuple renaming in _pytd_print correctly extracts type
    # names and doesn't erase other types accidentally.
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      import collections
      X = collections.namedtuple("X", "a b c d")
      Y = collections.namedtuple("Z", "")
      W = collections.namedtuple("W", "abc def ghi abc", rename=True)
      def bar(x: str):
        return x
      bar(X(1,2,3,4))  # 8
      bar(Y())         # 9
      bar(W(1,2,3,4))  # 10
      bar({1: 2}.__iter__())  # 11
      if __random__:
        a = X(1,2,3,4)
      else:
        a = 1
      bar(a)  # 16
      """)
    self.assertErrorLogIs(errors,
                          [(8, "wrong-arg-types", r"`X`"),
                           (9, "wrong-arg-types", r"`Z`"),
                           (10, "wrong-arg-types", r"`W`"),
                           (11, "wrong-arg-types", r"`dictionary-keyiterator`"),
                           (16, "wrong-arg-types", r"Union\[int, `X`\]")
                          ])

  def testCleanPyiNamedtupleNames(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        X = NamedTuple("X", [])
        def f(x: int): ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f(foo.X())
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"`X`")])

  def testBadAnnotation(self):
    _, errors = self.InferWithErrors("""\
      tuple[0]
      dict[42]
      class A(object): pass
      A[3]
    """)
    self.assertErrorLogIs(errors, [
        (1, "not-indexable", r"class tuple"),
        (2, "not-indexable", r"class dict"),
        (4, "not-indexable", r"class A"),
    ])

  def testRevealType(self):
    _, errors = self.InferWithErrors("""\
      reveal_type(42 or "foo")
      class Foo(object):
        pass
      reveal_type(Foo)
      reveal_type(Foo())
      reveal_type([1,2,3])
    """)
    self.assertErrorLogIs(errors, [
        (1, "reveal-type", r"^Union\[int, str\]$"),
        (4, "reveal-type", r"^Type\[Foo\]$"),
        (5, "reveal-type", r"^Foo$"),
        (6, "reveal-type", r"^List\[int\]$"),
    ])

  def testArgumentOrder(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def g(f: str, a, b, c, d, e,):
        pass
      g(a=1, b=2, c=3, d=4, e=5, f=6)
      """)
    self.assertErrorLogIs(
        errors,
        [(4, "wrong-arg-types",
          r"Expected.*f: str, \.\.\..*Actual.*f: int, \.\.\.")]
    )

  def testConversionOfGeneric(self):
    _, errors = self.InferWithErrors("""
      from __future__ import google_type_annotations
      import os
      def f() -> None:
        return os.walk("/tmp")
    """)
    self.assertErrorLogIs(errors, [
        (5, "bad-return-type")
    ])

  def testProtocolMismatch(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object): pass
      next(Foo())
    """)
    self.assertErrorLogIs(errors, [
        (2, "wrong-arg-types", "__iter__, next")
    ])

  def testProtocolMismatchPartial(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def __iter__(self):
          return self
      next(Foo())
    """)
    self.assertErrorLogIs(errors, [(
        4, "wrong-arg-types", r"\n\s*next\s*$")])  # `next` on its own line

  def testNotProtocol(self):
    _, errors = self.InferWithErrors("""\
      a = []
      a.append(1)
      a = "".join(a)
    """)
    self.assertErrorLogIs(errors, [(
        3, "wrong-arg-types", r"\(.*List\[int\]\)$")])  # no protocol details

  def testInnerClass(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def f() -> int:
        class Foo(object):
          pass
        return Foo()  # line 5
    """)
    self.assertErrorLogIs(errors, [(5, "bad-return-type", r"int.*Foo")])

  def testHiddenError(self):
    errors = self.CheckWithErrors("""\
      use_option = False
      def f():
        if use_option:
          name_error
    """)
    self.assertErrorLogIs(errors, [(4, "name-error")])


if __name__ == "__main__":
  test_base.main()
