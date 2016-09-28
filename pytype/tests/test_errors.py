"""Tests for displaying errors."""

import StringIO
import unittest

from pytype import utils
from pytype.tests import test_inference


class ErrorTest(test_inference.InferenceTest):
  """Tests for errors."""

  def testDeduplicate(self):
    _, errors = self.InferAndCheck("""
      def f(x):
        x.foobar
      f(3)
      f(4)
    """)
    s = StringIO.StringIO()
    errors.print_to_file(s)
    self.assertEquals(1, len([line for line in s.getvalue().splitlines()
                              if "foobar" in line]))

  def testUnknownGlobal(self):
    _, errors = self.InferAndCheck("""
      def f():
        return foobar()
    """)
    self.assertErrorLogContains(errors, r"line 3.*foobar")

  def testInvalidAttribute(self):
    ty, errors = self.InferAndCheck("""
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
    self.assertErrorLogContains(errors, r"line 5.*attribute.*parrot.*int")

  def testImportError(self):
    _, errors = self.InferAndCheck("""
      import rumplestiltskin
    """)
    self.assertErrorLogContains(
        errors, r".*line 2.*module.*rumplestiltskin[^\n]+\[import-error\]")

  def testImportFromError(self):
    _, errors = self.InferAndCheck("""
      from sys import foobar
    """)
    self.assertErrorLogContains(
        errors, r"sys.foobar.*\[import-error\]")

  def testNameError(self):
    _, errors = self.InferAndCheck("""
      foobar
    """)
    # "Line 2, in <module>: Name 'foobar' is not defined"
    self.assertErrorLogContains(errors, r"line 2.*name.*foobar.*not.defined")

  def testUnsupportedOperands(self):
    _, errors = self.InferAndCheck("""
      def f():
        x = "foo"
        y = "bar"
        return x ^ y
    """)
    # "Line 2, in f: Unsupported operands for __xor__: 'str' and 'str'
    self.assertErrorLogContains(errors,
                                r"line 5.*Unsupported.*__xor__.*str.*str")

  def testUnsupportedOperands2(self):
    _, errors = self.InferAndCheck("""
      def f():
        x = "foo"
        y = 3
        return x + y
    """)
    # "Line 2, in f: Unsupported operands for __add__: 'str' and 'int'
    self.assertErrorLogContains(errors,
                                r"line 5.*Unsupported.*__add__.*str.*int")

  def testWrongArgCount(self):
    _, errors = self.InferAndCheck("""
      hex(1, 2, 3, 4)
    """)
    self.assertErrorLogContains(
        errors, r"line 2.*hex was called with 4 args instead of expected 1")

  def testWrongArgTypes(self):
    _, errors = self.InferAndCheck("""
      hex(3j)
    """)
    self.assertErrorLogContains(
        errors, (r"line 2.*hex was called with the wrong arguments"
                 r"[^\n]+\[wrong-arg-types\]\n.*"
                 r"expected:.*int.*passed:.*complex"))

  def testInvalidBaseClass(self):
    _, errors = self.InferAndCheck("""
      class Foo(3):
        pass
    """)
    # "Line 2, in <module>: Invalid base class: `~unknown0`"
    self.assertErrorLogContains(errors, r"Invalid base class")

  def testInvalidIteratorFromImport(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Codec(object):
            def __init__(self) -> None: ...
      """)
      _, errors = self.InferAndCheck("""
        import mod
        def f():
          for row in mod.Codec():
            pass
      """, pythonpath=[d.path])
      # "Line 4, in f: No attribute '__iter__' on Codec"
      self.assertErrorLogContains(
          errors, r"line 4.*No attribute.*__iter__.*on Codec")
      self.assertErrorLogDoesNotContain(
          errors, "__class__")

  def testInvalidIteratorFromClass(self):
    _, errors = self.InferAndCheck("""
      class A(object):
        pass
      def f():
        for row in A():
          pass
    """)
    self.assertErrorLogContains(
        errors, r"line 5.*No attribute.*__iter__.*on A")
    self.assertErrorLogDoesNotContain(
        errors, "__class__")

  def testInheritFromGeneric(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        T = TypeVar("T")
        class Foo(Generic[T]): ...
        class Bar(Foo[int]): ...
      """)
      _, errors = self.InferAndCheck("""
        import mod
        chr(mod.Bar())
      """, pythonpath=[d.path])
      # "Line 3, in f: Can't retrieve item out of dict. Empty?"
      self.assertErrorLogContains(errors, r"chr.*wrong arguments")

  def testWrongKeywordArg(self):
    with utils.Tempdir() as d:
      d.create_file("mycgi.pyi", """
        def escape(x: str or unicode) -> str or unicode
      """)
      _, errors = self.InferAndCheck("""
        import mycgi
        def foo(s):
          return mycgi.escape(s, quote=1)
      """, pythonpath=[d.path])
      # "Line 4, in foo: Function mycgi.escape was called with extra argument
      #                  "quote"."
      self.assertErrorLogContains(errors, r"(?=.*quote).*mycgi.escape")

  def testMissingParameter(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar(xray, yankee, zulu) -> str
      """)
      _, errors = self.InferAndCheck("""
        import foo
        foo.bar(1, 2)
      """, pythonpath=[d.path])
      # "Line 3, in foo: Missing parameter 'zulu' in call to function foo.bar."
      self.assertErrorLogContains(errors, r"(?=.*foo.bar).*zulu")

  def testBadInheritance(self):
    _, errors = self.InferAndCheck("""
      class X:
          pass
      class Bar(X):
          pass
      class Baz(X, Bar):
          pass
    """)
    # "Line 6: Bad inheritance."
    self.assertErrorLogContains(errors, r"line 6.*inheritance")

  def testBadCall(self):
    with utils.Tempdir() as d:
      d.create_file("other.pyi", """
        def foo(x: int, y: str) -> str: ...
      """)
      _, errors = self.InferAndCheck("""
        import other
        other.foo(1.2, [])
      """, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"(x: float, y: list)")

  def testCallUncallable(self):
    _, errors = self.InferAndCheck("""
      0()
    """)
    self.assertErrorLogContains(errors, r"int.*\[not-callable\]")

  def testSuperError(self):
    _, errors = self.InferAndCheck("""
      class A(object):
        def __init__(self):
          super(A, self, "foo").__init__()
    """)
    self.assertErrorLogContains(errors, r"\[super-error\]")

  def testAttributeError(self):
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        def __getattr__(self, name):
          return "attr"
      def f():
        return Foo.foo
      def g(x):
        if x:
          y = None
        else:
          y = 1
        return y.bar
      def h():
        return Foo().foo  # No error
    """)
    self.assertErrorLogIs(errors, [
        # When there is one binding, include the object type in the error.
        (5, "attribute-error", r"No attribute 'foo' on Foo"),
        # With multiple bindings, there is no object type in the error.
        (11, "attribute-error", "No attribute 'bar'")])

  def testAttributeErrorGetAttribute(self):
    _, errors = self.InferAndCheck("""\
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
    _, errors = self.InferAndCheck("""\
      None.foo
    """)
    self.assertErrorLogIs(errors, [
        (1, "none-attr", r"foo")])

  def testPyiType(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: list[int]) -> int: ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.f([""])
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"List\[int\]")

  def testTooManyArgs(self):
    _, errors = self.InferAndCheck("""\
      def f():
        pass
      f(3)
    """, deep=True)
    self.assertErrorLogContains(errors, r"Line 3.*wrong-arg-count")

  def testTooFewArgs(self):
    _, errors = self.InferAndCheck("""\
      def f(x):
        pass
      f()
    """, deep=True)
    self.assertErrorLogContains(errors, r"Line 3.*missing-parameter")

  def testDuplicateKeyword(self):
    _, errors = self.InferAndCheck("""\
      def f(x, y):
        pass
      f(3, x=3)
    """, deep=True)
    self.assertErrorLogContains(errors, r"Line 3.*duplicate-keyword")

  def testBadImport(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      _, errors = self.InferAndCheck("""
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"a.*pyi-error")

  def testBadImportDependency(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from b import X
        class Y(X): ...
      """)
      _, errors = self.InferAndCheck("""
        import a
      """, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"a.*pyi-error")

  def testBadImportFrom(self):
    with utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      d.create_file("foo/__init__.pyi", "")
      _, errors = self.InferAndCheck("""
        from foo import a
      """, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"foo[.]a.*pyi-error")

  def testBadImportFromDependency(self):
    with utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
          from a import X
          class Y(X): ...
      """)
      d.create_file("foo/__init__.pyi", "")
      _, errors = self.InferAndCheck("""
        from foo import a
      """, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"foo[.]a.*pyi-error")

  def testBadContainer(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(SupportsInt[int]): pass
      """)
      _, errors = self.InferAndCheck("""
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"a.*pyi-error.*SupportsInt")

  def testBadTypeParameterOrder(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Generic[K, V], Generic[V, K]): pass
      """)
      _, errors = self.InferAndCheck("""
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogContains(errors, r"a.*pyi-error.*A")

  def testDuplicateTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        class A(Generic[T, T]): pass
      """)
      _, errors = self.InferAndCheck("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"T")])

  def testTypeParameterInModuleConstant(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        x = ...  # type: T
      """)
      _, errors = self.InferAndCheck("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"a.*T.*a\.x")])

  def testTypeParameterInClassAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        class A(Generic[T]):
          x = ...  # type: T
      """)
      _, errors = self.InferAndCheck("""\
        import a
        def f():
          return a.A.x
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(3, "unbound-type-param", r"x.*A.*T")])

  def testUnboundTypeParameterInInstanceAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        class A(object):
          x = ...  # type: T
      """)
      _, errors = self.InferAndCheck("""\
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"a.*T.*a\.A\.x")])

  def testPrintUnionArg(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(x: int or str) -> None
      """)
      _, errors = self.InferAndCheck("""\
        import a
        x = a.f(4.2)
      """, deep=True, pythonpath=[d.path])
      pattern = r"Expected.*Union\[int, str\].*Actually passed"
      self.assertErrorLogIs(errors, [(2, "wrong-arg-types", pattern)])

  def testPrintTypeArg(self):
    _, errors = self.InferAndCheck("""\
      max(int)
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(1, "wrong-arg-types", r"Actually passed.*Type\[int\]")])

  def testNotSupported(self):
    _, errors = self.InferAndCheck("""\
      from typing import TypeVar
      from typing import Generic
    """)
    self.assertErrorLogIs(
        errors, [(1, "not-supported-yet"),
                 (2, "not-supported-yet")])

  def testDeleteFromSet(self):
    _, errors = self.InferAndCheck("""\
      s = {1}
      del s[1]
    """, deep=True, solve_unknowns=True)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"__delitem__")])

  def testBadReference(self):
    ty, errors = self.InferAndCheck("""\
      def main():
        x = foo
        for foo in []:
          pass
        return x
    """, deep=True, solve_unknowns=True)
    self.assertErrorLogIs(errors, [(2, "name-error", r"foo")])
    # Make sure we recovered from the error and got the right return type
    self.assertTypesMatchPytd(ty, """
      def main() -> Any
    """)

  @unittest.skip("Some types shouldn't allow attribute setting.")
  def testSetIntAttribute(self):
    _, errors = self.InferAndCheck("""\
      x = 42
      x.y = 42
    """, deep=True, solve_unknowns=True)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"y")])

  def testInvalidParametersOnMethod(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __init__(self, x: int) -> None
      """)
      _, errors = self.InferAndCheck("""\
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
      _, errors = self.InferAndCheck("""\
        import foo
        foo.f(1, y=2)
        foo.f(1, 2, y=3)
        foo.f(1, x=1)
        # foo.f(y=1, y=2)  # caught by compiler
      """, deep=True, pythonpath=[d.path], solve_unknowns=False)
      self.assertErrorLogIs(errors, [
          (4, "duplicate-keyword-argument"),
      ])

  def testBadSuperClass(self):
    _, errors = self.InferAndCheck("""\
      class A(object):
        def f(self):
          return "foo"

      class B(A):
        def f(self):
          return super(self, B).f()  # should be super(B, self)
    """, deep=True)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types", r"B.*Type\[B\]")])

  @unittest.skip("Need to type-check second argument to super")
  def testBadSuperInstance(self):
    _, errors = self.InferAndCheck("""\
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
      _, errors = self.InferAndCheck("""\
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
      _, errors = self.InferAndCheck("""\
        import a
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorLogIs(errors, [(1, "pyi-error", r"Rumpelstiltskin")])

  def testMatchType(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object): ...
        class B(A): ...
        class C(object): ...
        def f(x: Type[A]) -> bool
      """)
      ty, errors = self.InferAndCheck("""\
        import a
        x = a.f(a.A)
        y = a.f(a.B)
        z = a.f(a.C)
      """, pythonpath=[d.path], deep=True)
      self.assertErrorLogIs(errors, [(
          4, "wrong-arg-types", r"Expected.*Type\[A\].*Actual.*Type\[C\]")])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: bool
        y = ...  # type: bool
        z = ...  # type: Any
      """)

  @unittest.skip("Need to match type parameters.")
  def testMatchParameterizedType(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        class A(Generic[T]): ...
        class B(A[str]): ...
        def f(x: Type[A[int]]): ...
      """)
      _, errors = self.InferAndCheck("""\
        import a
        x = a.f(a.B)
      """, pythonpath=[d.path], deep=True)
      expected_error = r"Expected.*Type\[A\[int\]\].*Actual.*Type\[B\]"
      self.assertErrorLogIs(errors, [(4, "wrong-arg-types", expected_error)])

  def testMROError(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object): ...
        class B(object): ...
        class C(A, B): ...
        class D(B, A): ...
        class E(C, D): ...
      """)
      _, errors = self.InferAndCheck("""\
        import a
        x = a.E()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "mro-error", r"E")])

  def testBadMRO(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(BaseException, ValueError): ...
      """)
      _, errors = self.InferAndCheck("""\
        import a
        class B(a.A): pass
        raise a.A()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "mro-error", r"A")])

  def testUnsolvableAsMetaclass(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def __getattr__(name) -> Any
      """)
      d.create_file("b.pyi", """
        from a import A
        class B(metaclass=A): ...
      """)
      _, errors = self.InferAndCheck("""\
        import b
        class C(b.B):
          def __init__(self):
            f = open(self.x, 'r')
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertErrorLogIs(errors, [(4, "attribute-error", r"x.*C")])


if __name__ == "__main__":
  test_inference.main()
