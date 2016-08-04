"""Tests for displaying errors."""

import StringIO

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

  def testIndexError(self):
    _, errors = self.InferAndCheck("""
      def f():
        return [][0]
    """)
    # "Line 3, in f: Can't retrieve item out of list. Empty?"
    self.assertErrorLogContains(errors, r"line 3.*item out of list")

  def testInvalidBaseClass(self):
    _, errors = self.InferAndCheck("""
      class Foo(3):
        pass
    """)
    # "Line 2, in <module>: Invalid base class: `~unknown0`"
    self.assertErrorLogContains(errors, r"Invalid base class")

  def testInvalidIteratorFromImport(self):
    _, errors = self.InferAndCheck("""
      import codecs
      def f():
        for row in codecs.Codec():
          pass
    """)
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

  def testWriteIndexError(self):
    _, errors = self.InferAndCheck("""
      def f():
        {}[0].x = 3
    """)
    # "Line 3, in f: Can't retrieve item out of dict. Empty?"
    self.assertErrorLogContains(errors, r"line 3.*item out of dict")

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

  def testEmpty(self):
    _, errors = self.InferAndCheck("""
      [][1]
    """)
    self.assertErrorLogContains(
        errors, "empty")
    self.assertErrorLogDoesNotContain(
        errors, "unsupported.operands")

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
    _, errors = self.InferAndCheck("""
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
    """)
    # When there is one binding, include the object type in the error.
    self.assertErrorLogContains(
        errors, r"No attribute 'foo' on Foo \[attribute-error\]")
    # When there are multiple bindings, there is no object type in the error.
    self.assertErrorLogContains(
        errors, r"No attribute 'bar' \[attribute-error\]")

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

  def testContainerError(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(SupportsInt[int]): pass
      """)
      _, errors = self.InferAndCheck("""
        import a
      """, deep=True, pythonpath=[d.path])
      self.assertErrorLogContains(errors, "a.*pyi-error.*SupportsInt")


if __name__ == "__main__":
  test_inference.main()
