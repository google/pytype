"""Tests for type comments."""


from pytype.tests import test_base


class FunctionCommentTest(test_base.BaseTest):
  """Tests for type comments."""

  def testFunctionUnspecifiedArgs(self):
    ty = self.Infer("""
      def foo(x):
        # type: (...) -> int
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> int
    """)

  def testFunctionReturnSpace(self):
    ty = self.Infer("""
      from typing import Dict
      def foo(x):
        # type: (...) -> Dict[int, int]
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def foo(x) -> Dict[int, int]
    """)

  def testFunctionZeroArgs(self):
    # Include some stray whitespace.
    ty = self.Infer("""
      def foo():
        # type: (  ) -> int
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo() -> int
    """)

  def testFunctionOneArg(self):
    # Include some stray whitespace.
    ty = self.Infer("""
      def foo(x):
        # type: ( int ) -> int
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int) -> int
    """)

  def testFunctionSeveralArgs(self):
    ty = self.Infer("""
      def foo(x, y, z):
        # type: (int, str, float) -> None
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str, z: float) -> None
    """)

  def testFunctionSeveralLines(self):
    ty = self.Infer("""
      def foo(x,
              y,
              z):
        # type: (int, str, float) -> None
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str, z: float) -> None
    """)

  def testFunctionNoneInArgs(self):
    ty = self.Infer("""
      def foo(x, y, z):
        # type: (int, str, None) -> None
        return x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str, z: None) -> None
    """)

  def testSelfIsOptional(self):
    ty = self.Infer("""
      class Foo(object):
        def f(self, x):
          # type: (int) -> None
          pass

        def g(self, x):
          # type: (Foo, int) -> None
          pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def f(self, x: int) -> None: ...
        def g(self, x: int) -> None: ...
    """)

  def testClsIsOptional(self):
    ty = self.Infer("""
      class Foo(object):
        @classmethod
        def f(cls, x):
          # type: (int) -> None
          pass

        @classmethod
        def g(cls, x):
          # type: (Foo, int) -> None
          pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        @classmethod
        def f(cls, x: int) -> None: ...
        @classmethod
        def g(cls: Foo, x: int) -> None: ...
    """)

  def testFunctionStarArg(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, *args):
          # type: (int) -> None
          self.value = args[0]
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        value = ...  # type: int
        def __init__(self, *args: int) -> None: ...
    """)

  def testFunctionStarStarArg(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, **kwargs):
          # type: (int) -> None
          self.value = kwargs['x']
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        value = ...  # type: int
        def __init__(self, **kwargs: int) -> None: ...
    """)

  def testFunctionNoReturn(self):
    _, errors = self.InferWithErrors("""\
      def foo():
        # type: () ->
        pass
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment")])

  def testFunctionTooManyArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: (int, str) -> None
        y = x
        return x
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment",
                                    r"Expected 1 args, 2 given")])

  def testFunctionTooFewArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x, y, z):
        # type: (int, str) -> None
        y = x
        return x
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment",
                                    r"Expected 3 args, 2 given")])

  def testFunctionTooFewArgsDoNotCountSelf(self):
    _, errors = self.InferWithErrors("""\
      def foo(self, x, y, z):
        # type: (int, str) -> None
        y = x
        return x
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment",
                                    r"Expected 3 args, 2 given")])

  def testFunctionMissingArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: () -> int
        return x
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment")])

  def testInvalidFunctionTypeComment(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: blah blah blah
        return x
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment",
                                    r"blah blah blah")])

  def testInvalidFunctionArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: (abc def) -> int
        return x
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment",
                                    r"abc def.*unexpected EOF")])

  def testAmbiguousAnnotation(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: (int or str) -> None
        pass
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-function-type-comment",
                                    r"int or str.*constant")])


class FunctionCommentWithAnnotationsTest(test_base.BaseTest):
  """Tests for type comments that require annotations."""

  def testFunctionTypeCommentPlusAnnotations(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      def foo(x: int) -> float:
        # type: (int) -> float
        return x
    """)
    self.assertErrorLogIs(errors, [(3, "redundant-function-type-comment")])


class AssignmentCommentTest(test_base.BaseTest):
  """Tests for type comments applied to assignments."""

  def testClassAttributeComment(self):
    ty = self.Infer("""
      class Foo(object):
        s = None  # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        s = ...  # type: str
    """)

  def testInstanceAttributeComment(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.s = None  # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        s = ...  # type: str
    """)

  def testGlobalComment(self):
    ty = self.Infer("""
      X = None  # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: str
    """)

  def testGlobalComment2(self):
    ty = self.Infer("""
      X = None  # type: str
      def f(): global X
    """)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: str
      def f() -> None
    """)

  def testLocalComment(self):
    ty = self.Infer("""
      X = None

      def foo():
        x = X  # type: str
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: None
      def foo() -> str: ...
    """)

  def testCellvarComment(self):
    """Type comment on an assignment generating the STORE_DEREF opcode."""
    ty = self.Infer("""
      from typing import Mapping
      def f():
        map = dict()  # type: Mapping
        return (map, {x: map.get(y) for x, y in __any_object__})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Mapping, Tuple
      def f() -> Tuple[Mapping, dict]: ...
    """)

  def testBadComment(self):
    ty, errors = self.InferWithErrors("""\
      X = None  # type: abc def
    """, deep=True)
    self.assertErrorLogIs(errors, [(1, "invalid-type-comment",
                                    r"abc def.*unexpected EOF")])
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def testConversionError(self):
    ty, errors = self.InferWithErrors("""\
      X = None  # type: 1 if __random__ else 2
    """, deep=True)
    self.assertErrorLogIs(errors, [(1, "invalid-type-comment",
                                    r"1 if __random__ else 2.*constant")])
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def testNameErrorInsideComment(self):
    _, errors = self.InferWithErrors("""\
      X = None  # type: Foo
    """, deep=True)
    self.assertErrorLogIs(errors, [(1, "invalid-type-comment", r"Foo")])

  def testWarnOnIgnoredTypeComment(self):
    _, errors = self.InferWithErrors("""\
      X = []
      X[0] = None  # type: str
      # type: int
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "ignored-type-comment", r"str"),
                                   (3, "ignored-type-comment", r"int")])

  def testAttributeInitialization(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 42
      a = None  # type: A
      x = a.x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: int
      a = ...  # type: A
      x = ...  # type: int
    """)

  def testNoneToNoneType(self):
    ty = self.Infer("""
      x = 0  # type: None
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: None
    """)

  def testModuleInstanceAsBadTypeComment(self):
    _, errors = self.InferWithErrors("""\
      import sys
      x = None  # type: sys
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-annotation",
                                    r"instance of module.*x")])

  def testForwardReference(self):
    ty, errors = self.InferWithErrors("""\
      a = None  # type: "A"
      b = None  # type: "Nonexistent"
      class A(object):
        def __init__(self):
          self.x = 42
        def f(self):
          return a.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        x = ...  # type: int
        def f(self) -> int
      a = ...  # type: A
      b = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(2, "invalid-annotation", r"Nonexistent")])

  def testUseForwardReference(self):
    ty = self.Infer("""\
      a = None  # type: "A"
      x = a.x
      class A(object):
        def __init__(self):
          self.x = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any
      class A(object):
        x = ...  # type: int
      a = ...  # type: A
      x = ...  # type: Any
    """)

  def testMultilineValue(self):
    ty, errors = self.InferWithErrors("""\
      v = [
        {
        "a": 1  # type: complex

        }  # type: dict[str, int]
      ]  # type: list[dict[unicode, float]]
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: list[dict[unicode, float]]
    """)
    self.assertErrorLogIs(errors, [(3, "ignored-type-comment",
                                    r"Stray type comment: complex"),
                                   (5, "ignored-type-comment",
                                    r"Stray type comment: dict\[str, int\]")])

  def testMultilineValueWithBlankLines(self):
    ty = self.Infer("""\
      a = [[

      ]

      ]  # type: list[list[int]]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: list[list[int]]
    """)

  def testTypeCommentNameError(self):
    _, errors = self.InferWithErrors("""\
      def f():
        x = None  # type: Any
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(2, "invalid-type-comment", r"not defined$")])

  def testTypeCommentInvalidSyntax(self):
    _, errors = self.InferWithErrors("""\
      def f():
        x = None  # type: y = 1
    """, deep=True)
    self.assertErrorLogIs(
        errors, [(2, "invalid-type-comment", r"invalid syntax$")])

  def testDiscardedTypeComment(self):
    """Discard the first whole-line comment, keep the second."""
    ty = self.Infer("""\
        # Yo dawg # type: ignore
        def hello_world():
          # type: () -> str
          return 'hello world'
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def hello_world() -> str: ...
    """)

  def testNestedCommentAlias(self):
    ty = self.Infer("""\
      class A(object): pass
      class B(object):
        C = A
        x = None  # type: C
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Type
      class A(object): pass
      class B(object):
        C = ...  # type: Type[A]
        x = ...  # type: A
      """)

  def testNestedClassesComments(self):
    ty = self.Infer("""\
      class A(object):
        class B(object): pass
        x = None  # type: B
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any
      class A(object):
        B = ...  # type: type
        x = ...  # type: Any
      """)

  def testListComprehensionComments(self):
    ty = self.Infer("""\
      from typing import List
      def f(x):
        # type: (str) -> None
        pass
      def g(xs):
        # type: (List[str]) -> List[str]
        ys = [f(x) for x in xs]  # type: List[str]
        return ys
    """)
    self.assertTypesMatchPytd(ty, """\
      from typing import List
      def f(x: str) -> None: ...
      def g(xs: List[str]) -> List[str]: ...
    """)

  def testMultipleAssignments(self):
    ty = self.Infer("""\
      a = 1; b = 2; c = 4  # type: float
    """)
    self.assertTypesMatchPytd(ty, """\
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: float
    """)


class Py3TypeCommentTest(test_base.BaseTest):
  """Tests for type comments in python3."""

  PYTHON_VERSION = (3, 6)

  def testListComprehensionComments(self):
    ty = self.Infer("""\
      from typing import List
      def f(x: str):
        pass
      def g(xs: List[str]) -> List[str]:
        ys = [f(x) for x in xs]  # type: List[str]
        return ys
    """)
    self.assertTypesMatchPytd(ty, """\
      from typing import List
      def f(x: str) -> None: ...
      def g(xs: List[str]) -> List[str]: ...
    """)


if __name__ == "__main__":
  test_base.main()
