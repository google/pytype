"""Tests for displaying errors."""

from pytype import file_utils
from pytype.tests import test_base


class ErrorTest(test_base.TargetIndependentTest):
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
      d.create_file("mycgi.pyi", """
        def escape(x: str or int) -> str or int
      """)
      _, errors = self.InferWithErrors("""\
        import mycgi
        def foo(s):
          return mycgi.escape(s, quote=1)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "wrong-keyword-args",
                                      r"quote.*mycgi\.escape")])

  def testMissingParameter(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
           r"No attribute 'bar' on None\nIn Optional\[int\]"),
          (11, "attribute-error",
           r"No attribute 'bar' on int\nIn Optional\[int\]"),
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error")])

  def testBadImportDependency(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from b import X
        class Y(X): ...
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error")])

  def testBadImportFrom(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Generic[K, V]): pass
        class B(Generic[K, V]): pass
        class C(A[K, V], B[V, K]): pass
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"Illegal.*order.*a\.C")])

  def testDuplicateTypeParameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T, T]): pass
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"T")])

  def testDuplicateGenericBaseClass(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        V = TypeVar("V")
        class A(Generic[T], Generic[V]): pass
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"inherit.*Generic")])

  def testTypeParameterInModuleConstant(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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

  def testDeleteFromSet(self):
    _, errors = self.InferWithErrors("""\
      s = {1}
      del s[1]
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(2, "unsupported-operands", r"item deletion")])

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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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

  @test_base.skip("Need to type-check second argument to super")
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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

  def testRecursion(self):
    with file_utils.Tempdir() as d:
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

  def testEmptyUnionOrOptional(self):
    with file_utils.Tempdir() as d:
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

  def testBadDictAttribute(self):
    _, errors = self.InferWithErrors("""\
      x = {"a": 1}
      y = x.a
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error",
                                    r"a.*Dict\[str, int\]")])

  def testBadPyiDict(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict
        x = ...  # type: Dict[str, int, float]
      """)
      _, errors = self.InferWithErrors("""\
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"2.*3")])

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
      f([])
    """)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands", r"str.*int"),
                                   (2, "unsupported-operands", r"List.*int")])

  def testKwargOrder(self):
    with file_utils.Tempdir() as d:
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
        (2, "base-class-error", r"Optional\[<instance of int>\]")])

  def testCallableInUnsupportedOperands(self):
    _, errors = self.InferWithErrors("""\
      def f(x, y=None): pass
      f in f
    """)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"Callable\[\[Any, Any\], Any\].*"
                                    r"Callable\[\[Any, Any\], Any\]")])

  def testCleanPyiNamedtupleNames(self):
    with file_utils.Tempdir() as d:
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
      dict[1, 2]
      class A(object): pass
      A[3]
    """)
    self.assertErrorLogIs(errors, [
        (1, "not-indexable", r"class tuple"),
        (2, "invalid-annotation", r"1.*Not a type"),
        (2, "invalid-annotation", r"2.*Not a type"),
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

  def testNotProtocol(self):
    _, errors = self.InferWithErrors("""\
      a = []
      a.append(1)
      a = "".join(a)
    """)
    self.assertErrorLogIs(errors, [(
        3, "wrong-arg-types", r"\(.*List\[int\]\)$")])  # no protocol details

  def testHiddenError(self):
    errors = self.CheckWithErrors("""\
      use_option = False
      def f():
        if use_option:
          name_error
    """)
    self.assertErrorLogIs(errors, [(4, "name-error")])

  def testUnknownInError(self):
    errors = self.CheckWithErrors("""\
      def f(x):
        y = x if __random__ else None
        return y.groups()
    """)
    self.assertErrorLogIs(errors, [(3, "attribute-error", r"Optional\[Any\]")])


class OperationsTest(test_base.TargetIndependentTest):
  """Test operations."""

  def testXor(self):
    errors = self.CheckWithErrors("def f(): return 'foo' ^ 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\^.*str.*int.*'__xor__' on str.*'__rxor__' on int")])

  def testAdd(self):
    errors = self.CheckWithErrors("def f(): return 'foo' + 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\+.*str.*int.*__add__ on str.*str")])

  def testInvert(self):
    errors = self.CheckWithErrors("def f(): return ~None")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\~.*None.*'__invert__' on None")])

  def testSub(self):
    errors = self.CheckWithErrors("def f(): return 'foo' - 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\-.*str.*int.*'__sub__' on str.*'__rsub__' on int")])

  def testMul(self):
    errors = self.CheckWithErrors("def f(): return 'foo' * None")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\*.*str.*None.*__mul__ on str.*int")])

  def testDiv(self):
    errors = self.CheckWithErrors("def f(): return 'foo' / 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\/.*str.*int.*'__(true)?div__' on str.*'__r(true)?div__' on int")])

  def testMod(self):
    errors = self.CheckWithErrors("def f(): return None % 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\%.*None.*int.*'__mod__' on None")])

  def testLShift(self):
    errors = self.CheckWithErrors("def f(): return 3 << None")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\<\<.*int.*None.*__lshift__ on int.*int")])

  def testRShift(self):
    errors = self.CheckWithErrors("def f(): return 3 >> None")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\>\>.*int.*None.*__rshift__ on int.*int")])

  def testAnd(self):
    errors = self.CheckWithErrors("def f(): return 'foo' & 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\&.*str.*int.*'__and__' on str.*'__rand__' on int")])

  def testOr(self):
    errors = self.CheckWithErrors("def f(): return 'foo' | 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\|.*str.*int.*'__or__' on str.*'__ror__' on int")])

  def testFloorDiv(self):
    errors = self.CheckWithErrors("def f(): return 3 // 'foo'")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\/\/.*int.*str.*__floordiv__ on int.*int")])

  def testPow(self):
    errors = self.CheckWithErrors("def f(): return 3 ** 'foo'")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\*\*.*int.*str.*__pow__ on int.*int")])

  def testNeg(self):
    errors = self.CheckWithErrors("def f(): return -None")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\-.*None.*'__neg__' on None")])

  def testPos(self):
    errors = self.CheckWithErrors("def f(): return +None")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"\+.*None.*'__pos__' on None")])


class InPlaceOperationsTest(test_base.TargetIndependentTest):
  """Test in-place operations."""

  def testIAdd(self):
    errors = self.CheckWithErrors("def f(): v = []; v += 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"\+\=.*List.*int.*__iadd__ on List.*Iterable")])


class NoSymbolOperationsTest(test_base.TargetIndependentTest):
  """Test operations with no native symbol."""

  def testGetItem(self):
    errors = self.CheckWithErrors("def f(): v = []; return v['foo']")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"item retrieval.*List.*str.*__getitem__ on List.*int")])

  def testDelItem(self):
    errors = self.CheckWithErrors("def f(): v = {'foo': 3}; del v[3]")
    d = r"Dict\[str, int\]"
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"item deletion.*{d}.*int.*__delitem__ on {d}.*str".format(d=d))])

  def testSetItem(self):
    errors = self.CheckWithErrors("def f(): v = []; v['foo'] = 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"item assignment.*List.*str.*__setitem__ on List.*int")])

  def testContains(self):
    errors = self.CheckWithErrors("def f(): return 'foo' in 3")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands", r"'in'.*int.*str.*'__contains__' on int")])


test_base.main(globals(), __name__ == "__main__")
