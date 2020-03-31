"""Tests for type comments."""

from pytype.tests import test_base


class FunctionCommentTest(test_base.TargetIndependentTest):
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

  def testFunctionCommentOnColon(self):
    self.InferWithErrors("""\
      def f(x) \\
        : # type: (None) -> None
        return True  # bad-return-type
    """)

  def testMultipleFunctionComments(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        # type: (None) -> bool
        # type: (str) -> str  # ignored-type-comment[e]
        return True
    """)
    self.assertErrorRegexes(errors, {"e": r"Stray type comment:.*str"})

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

  def testFunctionWithoutBody(self):
    ty = self.Infer("""
      def foo(x, y):
        # type: (int, str) -> None
        '''Docstring but no body.'''
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str) -> None
    """)

  def testFilterOutClassConstructor(self):
    # We should not associate the typecomment with the function A()
    self.Check("""
      class A:
        x = 0 # type: int
    """)

  def testTypeCommentAfterDocstring(self):
    """Type comments after the docstring should not be picked up."""
    self.InferWithErrors("""\
      def foo(x, y):
        '''Ceci n'est pas une type.'''
        # type: (int, str) -> None  # ignored-type-comment
    """)

  def testFunctionNoReturn(self):
    self.InferWithErrors("""\
      def foo():
        # type: () ->  # invalid-function-type-comment
        pass
    """)

  def testFunctionTooManyArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: (int, str) -> None  # invalid-function-type-comment[e]
        y = x
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 1 args, 2 given"})

  def testFunctionTooFewArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x, y, z):
        # type: (int, str) -> None  # invalid-function-type-comment[e]
        y = x
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 3 args, 2 given"})

  def testFunctionTooFewArgsDoNotCountSelf(self):
    _, errors = self.InferWithErrors("""\
      def foo(self, x, y, z):
        # type: (int, str) -> None  # invalid-function-type-comment[e]
        y = x
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 3 args, 2 given"})

  def testFunctionMissingArgs(self):
    self.InferWithErrors("""\
      def foo(x):
        # type: () -> int  # invalid-function-type-comment
        return x
    """)

  def testInvalidFunctionTypeComment(self):
    self.InferWithErrors("""\
      def foo(x):
        # type: blah blah blah  # invalid-function-type-comment
        return x
    """)

  def testInvalidFunctionArgs(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: (abc def) -> int  # invalid-function-type-comment[e]
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"abc def.*unexpected EOF"})

  def testAmbiguousAnnotation(self):
    _, errors = self.InferWithErrors("""\
      def foo(x):
        # type: (int if __random__ else str) -> None  # invalid-function-type-comment[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str.*constant"})


class AssignmentCommentTest(test_base.TargetIndependentTest):
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
      X = None  # type: abc def  # invalid-type-comment[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"abc def.*unexpected EOF"})
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def testConversionError(self):
    ty, errors = self.InferWithErrors("""\
      X = None  # type: 1 if __random__ else 2  # invalid-type-comment[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"1 if __random__ else 2.*constant"})
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def testNameErrorInsideComment(self):
    _, errors = self.InferWithErrors("""\
      X = None  # type: Foo  # invalid-type-comment[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Foo"})

  def testWarnOnIgnoredTypeComment(self):
    _, errors = self.InferWithErrors("""\
      X = []
      X[0] = None  # type: str  # ignored-type-comment[e1]
      # type: int  # ignored-type-comment[e2]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e1": r"str", "e2": r"int"})

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
      x = None  # type: sys  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"instance of module.*x"})

  def testForwardReference(self):
    ty, errors = self.InferWithErrors("""\
      a = None  # type: "A"
      b = None  # type: "Nonexistent"  # name-error[e]
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
    self.assertErrorRegexes(errors, {"e": r"Nonexistent"})

  def testClassVariableForwardReference(self):
    ty = self.Infer("""\
      class A(object):
        a = None  # type: 'A'
        def __init__(self):
          self.x = 42
    """)
    self.assertTypesMatchPytd(ty, """\
      class A(object):
        a: A
        x: int
    """)

  def testUseForwardReference(self):
    ty = self.Infer("""\
      a = None  # type: "A"
      x = a.x
      class A(object):
        def __init__(self):
          self.x = 42
    """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any
      class A(object):
        x = ...  # type: int
      a = ...  # type: A
      x = ...  # type: Any
    """)

  def testUseClassVariableForwardReference(self):
    # Attribute accesses for A().a all get resolved to Any (b/134706992)
    ty = self.Infer("""\
      class A(object):
        a = None  # type: 'A'
        def f(self):
          return self.a
      x = A().a
      def g():
        return A().a
      y = g()
    """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any, TypeVar
      _TA = TypeVar('_TA', bound=A)
      class A(object):
        a: A
        def f(self: _TA) -> _TA: ...
      x: A
      y: A
      def g() -> A: ...
    """)

  def testClassVariableForwardReferenceError(self):
    self.InferWithErrors("""\
      class A(object):
        a = None  # type: 'A'
      g = A().a.foo()  # attribute-error
    """)

  def testMultilineValue(self):
    ty, errors = self.InferWithErrors("""\
      v = [
        {
        "a": 1  # type: complex  # ignored-type-comment[e1]

        }  # type: dict[str, int]  # ignored-type-comment[e2]
      ]  # type: list[dict[str, float]]
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: list[dict[str, float]]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Stray type comment: complex",
        "e2": r"Stray type comment: dict\[str, int\]"})

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
        x = None  # type: Any  # invalid-type-comment[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"not defined$"})

  def testTypeCommentInvalidSyntax(self):
    _, errors = self.InferWithErrors("""\
      def f():
        x = None  # type: y = 1  # invalid-type-comment[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"invalid syntax$"})

  def testDiscardedTypeComment(self):
    """Discard the first whole-line comment, keep the second."""
    ty = self.Infer("""\
        # We want either # type: ignore or # type: int
        def hello_world():
          # type: () -> str
          return 'hello world'
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def hello_world() -> str: ...
    """)

  def testMultipleTypeComments(self):
    """We should not allow multiple type comments on one line."""
    _, errors = self.InferWithErrors("""\
      a = 42  # type: int  # type: float  # invalid-directive[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Multiple"})

  def testMultipleDirectives(self):
    """We should support multiple directives on one line."""
    self.Check("""\
      a = list() # type: list[int, str]  # pytype: disable=invalid-type-comment
      b = list() # pytype: disable=invalid-type-comment  # type: list[int, str]
      def foo(x): pass
      c = foo(a, b.i) # pytype: disable=attribute-error  # pytype: disable=wrong-arg-count
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

  def testRecursiveTypeAlias(self):
    errors = self.CheckWithErrors("""\
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      x = 'hello'  # type: Foo  # not-supported-yet[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def testInstantiateFullyQuotedType(self):
    ty, errors = self.InferWithErrors("""\
      from typing import Optional
      x = None  # type: "Optional[A]"
      class A(object):
        a = 0
      y = x.a  # attribute-error[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      x: Optional[A]
      class A(object):
        a: int
      y: int
    """)
    self.assertErrorRegexes(errors, {"e": r"a.*None"})

  def testDoNotResolveLateTypeToFunction(self):
    ty = self.Infer("""
      v = None  # type: "A"
      class A(object):
        def A(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      v: A
      class A(object):
        def A(self) -> None: ...
    """)

  def testIllegalFunctionLateType(self):
    self.CheckWithErrors("""\
      v = None  # type: "F"  # invalid-annotation
      def F(): pass
    """)

  def testBadTypeCommentInConstructor(self):
    self.CheckWithErrors("""\
      class Foo(object):
        def __init__(self):
          self.x = None  # type: "Bar"  # name-error
    """)


test_base.main(globals(), __name__ == "__main__")
