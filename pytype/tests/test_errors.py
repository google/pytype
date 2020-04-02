"""Tests for displaying errors."""

from pytype import file_utils
from pytype.tests import test_base


class ErrorTest(test_base.TargetIndependentTest):
  """Tests for errors."""

  def testDeduplicate(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        y = 42
        y.foobar  # attribute-error[e]
      f(3)
      f(4)
    """)
    self.assertErrorRegexes(errors, {"e": r"'foobar' on int$"})

  def testUnknownGlobal(self):
    _, errors = self.InferWithErrors("""
      def f():
        return foobar()  # name-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"foobar"})

  def testInvalidAttribute(self):
    ty, errors = self.InferWithErrors("""
      class A(object):
        pass
      def f():
        (3).parrot  # attribute-error[e]
        return "foo"
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        pass

      def f() -> str
    """)
    self.assertErrorRegexes(errors, {"e": r"parrot.*int"})

  def testImportError(self):
    self.InferWithErrors("""
      import rumplestiltskin  # import-error
    """)

  def testImportFromError(self):
    _, errors = self.InferWithErrors("""
      from sys import foobar  # import-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"sys\.foobar"})

  def testNameError(self):
    self.InferWithErrors("""
      foobar  # name-error
    """)

  def testWrongArgCount(self):
    _, errors = self.InferWithErrors("""
      hex(1, 2, 3, 4)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"expects 1.*got 4"})

  def testWrongArgTypes(self):
    _, errors = self.InferWithErrors("""
      hex(3j)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*complex"})

  def testInterpreterFunctionNameInMsg(self):
    _, errors = self.InferWithErrors("""
      class A(list): pass
      A.append(3)  # missing-parameter[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"function list\.append"})

  def testPyTDFunctionNameInMsg(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", "class A(list): pass")
      _, errors = self.InferWithErrors("""
        import foo
        foo.A.append(3)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"function list\.append"})

  def testBuiltinFunctionNameInMsg(self):
    _, errors = self.InferWithErrors("""
      x = list
      x += (1,2)  # missing-parameter[e]
      """)
    self.assertErrorRegexes(errors, {"e": r"function list\.__iadd__"})

  def testRewriteBuiltinFunctionName(self):
    """Should rewrite `function __builtin__.len` to `built-in function len`."""
    _, errors = self.InferWithErrors("x = len(None)  # wrong-arg-types[e]")
    self.assertErrorRegexes(errors, {"e": r"Built-in function len"})

  def testBoundMethodNameInMsg(self):
    _, errors = self.InferWithErrors("""
      "".join(1)  # wrong-arg-types[e]
      """)
    self.assertErrorRegexes(errors, {"e": r"Function str\.join"})

  def testNestedClassMethodNameIsMsg(self):
    errors = self.CheckWithErrors("""
      class A(object):
        class B(object):
          def f(self):
            pass
      A.B().f("oops")  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Function B.f"})

  def testPrettyPrintWrongArgs(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(a: int, b: int, c: int, d: int, e: int): ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f(1, 2, 3, "four", 5)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {
        "e": r"a, b, c, d: int, [.][.][.].*a, b, c, d: str, [.][.][.]"})

  def testInvalidBaseClass(self):
    self.InferWithErrors("""
      class Foo(3):  # base-class-error
        pass
    """)

  def testInvalidIteratorFromImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Codec(object):
            def __init__(self) -> None: ...
      """)
      _, errors = self.InferWithErrors("""
        import mod
        def f():
          for row in mod.Codec():  # attribute-error[e]
            pass
      """, pythonpath=[d.path])
      error = r"No attribute.*__iter__.*on mod\.Codec"
      self.assertErrorRegexes(errors, {"e": error})

  def testInvalidIteratorFromClass(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        pass
      def f():
        for row in A():  # attribute-error[e]
          pass
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__.*A"})

  def testIterOnModule(self):
    errors = self.CheckWithErrors("""
      import sys
      for _ in sys:  # module-attr[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__.*module 'sys'"})

  def testInheritFromGeneric(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]): ...
        class Bar(Foo[int]): ...
      """)
      _, errors = self.InferWithErrors("""
        import mod
        chr(mod.Bar())  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      # "Line 3, in f: Can't retrieve item out of dict. Empty?"
      self.assertErrorRegexes(errors, {"e": r"int.*mod\.Bar"})

  def testWrongKeywordArg(self):
    with file_utils.Tempdir() as d:
      d.create_file("mycgi.pyi", """
        def escape(x: str or int) -> str or int
      """)
      _, errors = self.InferWithErrors("""
        import mycgi
        def foo(s):
          return mycgi.escape(s, quote=1)  # wrong-keyword-args[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"quote.*mycgi\.escape"})

  def testMissingParameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar(xray, yankee, zulu) -> str
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.bar(1, 2)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"zulu.*foo\.bar"})

  def testBadInheritance(self):
    self.InferWithErrors("""
      class X:
          pass
      class Bar(X):
          pass
      class Baz(X, Bar):  # mro-error
          pass
    """)

  def testBadCall(self):
    with file_utils.Tempdir() as d:
      d.create_file("other.pyi", """
        def foo(x: int, y: str) -> str: ...
      """)
      _, errors = self.InferWithErrors("""
        import other
        other.foo(1.2, [])  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"\(x: int"})

  def testCallUncallable(self):
    _, errors = self.InferWithErrors("""
      0()  # not-callable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int"})

  def testSuperError(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        def __init__(self):
          super(A, self, "foo").__init__()  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"2.*3"})

  def testAttributeError(self):
    with file_utils.Tempdir() as d:
      d.create_file("modfoo.pyi", "")
      _, errors = self.InferWithErrors("""
        class Foo(object):
          def __getattr__(self, name):
            return "attr"
        def f():
          return Foo.foo  # attribute-error[e1]
        def g(x):
          if x:
            y = None
          else:
            y = 1
          return y.bar  # attribute-error[e2]  # attribute-error[e3]
        def h():
          return Foo().foo  # No error
        import modfoo
        modfoo.baz  # module-attr[e4]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"No attribute 'foo' on Type\[Foo\]",
          "e2": r"No attribute 'bar' on int\nIn Optional\[int\]",
          "e3": r"No attribute 'bar' on None\nIn Optional\[int\]",
          "e4": r"No attribute 'baz' on module 'modfoo'"})

  def testAttributeErrorGetAttribute(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __getattribute__(self, name):
          return "attr"
      def f():
        return Foo().x  # There should be no error on this line.
      def g():
        return Foo.x  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x"})

  def testNoneAttribute(self):
    _, errors = self.InferWithErrors("""
      None.foo  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"foo"})

  def testPyiType(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: list[int]) -> int: ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f([""])  # wrong-arg-types[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"List\[int\].*List\[str\]"})

  def testTooManyArgs(self):
    _, errors = self.InferWithErrors("""
      def f():
        pass
      f(3)  # wrong-arg-count[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"0.*1"})

  def testTooFewArgs(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        pass
      f()  # missing-parameter[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"x.*f"})

  def testDuplicateKeyword(self):
    _, errors = self.InferWithErrors("""
      def f(x, y):
        pass
      f(3, x=3)  # duplicate-keyword-argument[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"f.*x"})

  def testBadImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      self.InferWithErrors("""
        import a  # pyi-error
      """, pythonpath=[d.path])

  def testBadImportDependency(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from b import X
        class Y(X): ...
      """)
      self.InferWithErrors("""
        import a  # pyi-error
      """, pythonpath=[d.path])

  def testBadImportFrom(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      d.create_file("foo/__init__.pyi", "")
      _, errors = self.InferWithErrors("""
        from foo import a  # pyi-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.a"})

  def testBadImportFromDependency(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
          from a import X
          class Y(X): ...
      """)
      d.create_file("foo/__init__.pyi", "")
      _, errors = self.InferWithErrors("""
        from foo import a  # pyi-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.a"})

  def testBadContainer(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import SupportsInt
        class A(SupportsInt[int]): pass
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"SupportsInt is not a container"})

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
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"Illegal.*order.*a\.C"})

  def testDuplicateTypeParameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T, T]): pass
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"T"})

  def testDuplicateGenericBaseClass(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        V = TypeVar("V")
        class A(Generic[T], Generic[V]): pass
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"inherit.*Generic"})

  def testTypeParameterInModuleConstant(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        x = ...  # type: T
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"a.*T.*a\.x"})

  def testTypeParameterInClassAttribute(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          x = ...  # type: T
      """)
      _, errors = self.InferWithErrors("""
        import a
        def f():
          return a.A.x  # unbound-type-param[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"x.*A.*T"})

  def testUnboundTypeParameterInInstanceAttribute(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        class A(object):
          x = ...  # type: T
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"a.*T.*a\.A\.x"})

  def testPrintUnionArg(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(x: int or str) -> None
      """)
      _, errors = self.InferWithErrors("""
        import a
        x = a.f(4.2)  # wrong-arg-types[e]
      """, deep=True, pythonpath=[d.path])
      pattern = r"Expected.*Union\[int, str\].*Actually passed"
      self.assertErrorRegexes(errors, {"e": pattern})

  def testPrintTypeArg(self):
    _, errors = self.InferWithErrors("""
      hex(int)  # wrong-arg-types[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Actually passed.*Type\[int\]"})

  def testDeleteFromSet(self):
    _, errors = self.InferWithErrors("""
      s = {1}
      del s[1]  # unsupported-operands[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"item deletion"})

  def testBadReference(self):
    ty, errors = self.InferWithErrors("""
      def main():
        x = foo  # name-error[e]
        for foo in []:
          pass
        return x
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"foo"})
    # Make sure we recovered from the error and got the right return type
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def main() -> Any
    """)

  def testSetIntAttribute(self):
    _, errors = self.InferWithErrors("""
      x = 42
      x.y = 42  # not-writable[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"y.*int"})

  def testInvalidParametersOnMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __init__(self, x: int) -> None
      """)
      _, errors = self.InferWithErrors("""
        import a
        x = a.A("")  # wrong-arg-types[e1]
        x = a.A("", 42)  # wrong-arg-count[e2]
        x = a.A(42, y="")  # wrong-keyword-args[e3]
        x = a.A(42, x=42)  # duplicate-keyword-argument[e4]
        x = a.A()  # missing-parameter[e5]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"A\.__init__", "e2": r"A\.__init__", "e3": r"A\.__init__",
          "e4": r"A\.__init__", "e5": r"A\.__init__"})

  def testDuplicateKeywords(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x, *args, y) -> None
      """)
      self.InferWithErrors("""
        import foo
        foo.f(1, y=2)
        foo.f(1, 2, y=3)
        foo.f(1, x=1)  # duplicate-keyword-argument
        # foo.f(y=1, y=2)  # caught by compiler
      """, deep=True, pythonpath=[d.path])

  def testInvalidParametersDetails(self):
    _, errors = self.InferWithErrors("""
      float(list())  # wrong-arg-types[e1]
      float(1, list(), foobar=str)  # wrong-arg-count[e2]
      float(1, foobar=list())  # wrong-keyword-args[e3]
      float(1, x="")  # duplicate-keyword-argument[e4]
      hex()  # missing-parameter[e5]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Actually passed:.*self, x: List\[nothing\]",
        "e2": r"_, foobar", "e3": r"Actually passed:.*self, x, foobar",
        "e4": r"Actually passed:.*self, x, x", "e5": r"Actually passed: \(\)",
    })

  def testBadSuperClass(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        def f(self):
          return "foo"

      class B(A):
        def f(self):
          return super(self, B).f()  # should be super(B, self)  # wrong-arg-types[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"cls: type.*cls: B"})

  @test_base.skip("Need to type-check second argument to super")
  def testBadSuperInstance(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        pass
      class B(A):
        def __init__(self):
          super(B, A).__init__()  # A cannot be the second argument to super  # wrong-arg-types[e]
    """, deep=True)
    self.assertErrorRegexes(
        errors, {"e": r"Type\[B\].*Type\[A\]"})

  def testBadNameImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        import typing
        x = ...  # type: typing.Rumpelstiltskin
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorRegexes(errors, {"e": r"Rumpelstiltskin"})

  def testBadNameImportFrom(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Rumpelstiltskin
        x = ...  # type: Rumpelstiltskin
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorRegexes(errors, {"e": r"Rumpelstiltskin"})

  def testMatchType(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type
        class A(object): ...
        class B(A): ...
        class C(object): ...
        def f(x: Type[A]) -> bool
      """)
      ty, errors = self.InferWithErrors("""
        import a
        x = a.f(a.A)
        y = a.f(a.B)
        z = a.f(a.C)  # wrong-arg-types[e]
      """, pythonpath=[d.path], deep=True)
      error = r"Expected.*Type\[a\.A\].*Actual.*Type\[a\.C\]"
      self.assertErrorRegexes(errors, {"e": error})
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
      _, errors = self.InferWithErrors("""
        import a
        x = a.f(a.B)  # wrong-arg-types[e]
      """, pythonpath=[d.path], deep=True)
      expected_error = r"Expected.*Type\[a\.A\[int\]\].*Actual.*Type\[a\.B\]"
      self.assertErrorRegexes(errors, {"e": expected_error})

  def testMROError(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object): ...
        class B(object): ...
        class C(A, B): ...
        class D(B, A): ...
        class E(C, D): ...
      """)
      _, errors = self.InferWithErrors("""
        import a
        x = a.E()  # mro-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"E"})

  def testBadMRO(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(BaseException, ValueError): ...
      """)
      _, errors = self.InferWithErrors("""
        import a
        class B(a.A): pass  # mro-error[e]
        raise a.A()
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"A"})

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
      _, errors = self.InferWithErrors("""
        import b
        class C(b.B):
          def __init__(self):
            f = open(self.x, 'r')  # attribute-error[e]
      """, pythonpath=[d.path], deep=True)
      self.assertErrorRegexes(errors, {"e": r"x.*C"})

  def testDontTimeoutOnComplex(self):
    # Tests that we can solve a complex file without timing out.
    # Useful for catching large performance regressions.
    ty = self.Infer("""
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
      self.InferWithErrors("""
        import a
        x = a.f(0, "")  # wrong-arg-types
      """, pythonpath=[d.path])

  def testNoncomputableMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def copy(x: T) -> T
      """)
      _, errors = self.InferWithErrors("""
        import a
        class A(object):
          def __getattribute__(self, name):
            return a.copy(self)
        x = A()()  # not-callable[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"A"})

  def testBadTypeName(self):
    _, errors = self.InferWithErrors("""
      X = type(3, (int, object), {"a": 1})  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Actual.*int"})

  def testBadTypeBases(self):
    _, errors = self.InferWithErrors("""
      X = type("X", (42,), {"a": 1})  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Actual.*Tuple\[int\]"})

  def testHalfBadTypeBases(self):
    _, errors = self.InferWithErrors("""
      X = type("X", (42, object), {"a": 1})  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Actual.*Tuple\[int, Type\[object\]\]"})

  def testBadTypeMembers(self):
    _, errors = self.InferWithErrors("""
      X = type("X", (int, object), {0: 1})  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Actual.*Dict\[int, int\]"})

  def testRecursion(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(B): ...
        class B(A): ...
      """)
      ty, errors = self.InferWithErrors("""
        import a
        v = a.A()  # recursion-error[e]
        x = v.x  # No error because there is an Unsolvable in the MRO of a.A
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        v = ...  # type: a.A
        x = ...  # type: Any
      """)
      self.assertErrorRegexes(errors, {"e": r"a\.A"})

  def testEmptyUnionOrOptional(self):
    with file_utils.Tempdir() as d:
      d.create_file("f1.pyi", """
        def f(x: Union): ...
      """)
      d.create_file("f2.pyi", """
        def f(x: Optional): ...
      """)
      _, errors = self.InferWithErrors("""
        import f1  # pyi-error[e1]
        import f2  # pyi-error[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e1": r"f1.*Union", "e2": r"f2.*Optional"})

  def testBadDictAttribute(self):
    _, errors = self.InferWithErrors("""
      x = {"a": 1}
      y = x.a  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"a.*Dict\[str, int\]"})

  def testBadPyiDict(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict
        x = ...  # type: Dict[str, int, float]
      """)
      _, errors = self.InferWithErrors("""
        import a  # pyi-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"2.*3"})

  def testCallNone(self):
    self.InferWithErrors("""
      None()  # not-callable
    """)

  def testInNone(self):
    self.InferWithErrors("""
      3 in None  # unsupported-operands
    """)

  def testNoAttrError(self):
    self.InferWithErrors("""
      if __random__:
        y = 42
      else:
        y = "foo"
      y.upper  # attribute-error
    """)

  def testAttrError(self):
    _, errors = self.InferWithErrors("""
      if __random__:
        y = 42
      else:
        y = "foo"
      y.upper  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})

  def testPrintCallableInstance(self):
    _, errors = self.InferWithErrors("""
      from typing import Callable
      v = None  # type: Callable[[int], str]
      hex(v)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Actual.*Callable\[\[int\], str\]"})

  def testSameNameAndLine(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        return x + 42  # unsupported-operands[e1]  # unsupported-operands[e2]
      f("hello")
      f([])
    """)
    self.assertErrorRegexes(errors, {"e1": r"str.*int", "e2": r"List.*int"})

  def testKwargOrder(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(*args, y, x, z: int): ...
        def g(x): ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f(x=1, y=2, z="3")  # wrong-arg-types[e1]
        foo.g(42, v4="the", v3="quick", v2="brown", v1="fox")  # wrong-keyword-args[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e1": r"x, y, z.*x, y, z", "e2": r"v1, v2, v3, v4"})

  def testBadBaseClass(self):
    _, errors = self.InferWithErrors("""
      class Foo(None): pass  # base-class-error[e1]
      class Bar(None if __random__ else 42): pass  # base-class-error[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Invalid base class: None",
                                     "e2": r"Optional\[<instance of int>\]"})

  def testCallableInUnsupportedOperands(self):
    _, errors = self.InferWithErrors("""
      def f(x, y=None): pass
      f in f  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": (r"Callable\[\[Any, Any\], Any\].*"
                       r"Callable\[\[Any, Any\], Any\]")})

  def testCleanPyiNamedtupleNames(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        X = NamedTuple("X", [])
        def f(x: int): ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f(foo.X())  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"`X`"})

  def testBadAnnotation(self):
    _, errors = self.InferWithErrors("""
      tuple[0]  # not-indexable[e1]
      dict[1, 2]  # invalid-annotation[e2]  # invalid-annotation[e3]
      class A(object): pass
      A[3]  # not-indexable[e4]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"class tuple", "e2": r"1.*Not a type", "e3": r"2.*Not a type",
        "e4": r"class A"})

  def testRevealType(self):
    _, errors = self.InferWithErrors("""
      reveal_type(42 or "foo")  # reveal-type[e1]
      class Foo(object):
        pass
      reveal_type(Foo)  # reveal-type[e2]
      reveal_type(Foo())  # reveal-type[e3]
      reveal_type([1,2,3])  # reveal-type[e4]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"^Union\[int, str\]$", "e2": r"^Type\[Foo\]$", "e3": r"^Foo$",
        "e4": r"^List\[int\]$"})

  def testNotProtocol(self):
    _, errors = self.InferWithErrors("""
      a = []
      a.append(1)
      a = "".join(a)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\(.*List\[int\]\)$"})  # no protocol details

  def testHiddenError(self):
    self.CheckWithErrors("""
      use_option = False
      def f():
        if use_option:
          name_error  # name-error
    """)

  def testUnknownInError(self):
    errors = self.CheckWithErrors("""
      def f(x):
        y = x if __random__ else None
        return y.groups()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Optional\[Any\]"})


class OperationsTest(test_base.TargetIndependentTest):
  """Test operations."""

  def testXor(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' ^ 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\^.*str.*int.*'__xor__' on str.*'__rxor__' on int"})

  def testAdd(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' + 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\+.*str.*int.*__add__ on str.*str"})

  def testInvert(self):
    errors = self.CheckWithErrors("""
      def f(): return ~None  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\~.*None.*'__invert__' on None"})

  def testSub(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' - 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\-.*str.*int.*'__sub__' on str.*'__rsub__' on int"})

  def testMul(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' * None  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\*.*str.*None.*__mul__ on str.*int"})

  def testDiv(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' / 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\/.*str.*int.*'__(true)?div__' on str.*'__r(true)?div__' on int"
    })

  def testMod(self):
    errors = self.CheckWithErrors("""
      def f(): return None % 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\%.*None.*int.*'__mod__' on None"})

  def testLShift(self):
    errors = self.CheckWithErrors("""
      def f(): return 3 << None  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\<\<.*int.*None.*__lshift__ on int.*int"})

  def testRShift(self):
    errors = self.CheckWithErrors("""
      def f(): return 3 >> None  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\>\>.*int.*None.*__rshift__ on int.*int"})

  def testAnd(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' & 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\&.*str.*int.*'__and__' on str.*'__rand__' on int"})

  def testOr(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' | 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\|.*str.*int.*'__or__' on str.*'__ror__' on int"})

  def testFloorDiv(self):
    errors = self.CheckWithErrors("""
      def f(): return 3 // 'foo'  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\/\/.*int.*str.*__floordiv__ on int.*int"})

  def testPow(self):
    errors = self.CheckWithErrors("""
      def f(): return 3 ** 'foo'  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\*\*.*int.*str.*__pow__ on int.*int"})

  def testNeg(self):
    errors = self.CheckWithErrors("""
      def f(): return -None  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\-.*None.*'__neg__' on None"})

  def testPos(self):
    errors = self.CheckWithErrors("""
      def f(): return +None  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\+.*None.*'__pos__' on None"})


class InPlaceOperationsTest(test_base.TargetIndependentTest):
  """Test in-place operations."""

  def testIAdd(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; v += 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"\+\=.*List.*int.*__iadd__ on List.*Iterable"})


class NoSymbolOperationsTest(test_base.TargetIndependentTest):
  """Test operations with no native symbol."""

  def testGetItem(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; return v['foo']  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"item retrieval.*List.*str.*__getitem__ on List.*int"})

  def testDelItem(self):
    errors = self.CheckWithErrors("""
      def f(): v = {'foo': 3}; del v[3]  # unsupported-operands[e]
    """)
    d = r"Dict\[str, int\]"
    self.assertErrorRegexes(errors, {
        "e": r"item deletion.*{d}.*int.*__delitem__ on {d}.*str".format(d=d)})

  def testSetItem(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; v['foo'] = 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"item assignment.*List.*str.*__setitem__ on List.*int"})

  def testContains(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' in 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"'in'.*int.*str.*'__contains__' on int"})

  def testRecursion(self):
    self.CheckWithErrors("""
      def f():
        if __random__:
          f()
          name_error  # name-error
    """)


test_base.main(globals(), __name__ == "__main__")
