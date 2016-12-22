"""Tests for inline annotations."""

import os
import unittest


from pytype import utils
from pytype.tests import test_inference


class AnnotationTest(test_inference.InferenceTest):
  """Tests for PEP 484 style inline annotations."""


  def testNoneUnpackingIs(self):
    """Tests that is works with None."""
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is None:
          return ""
        return x
      """)

  def testNoneUnpackingIsNot(self):
    """Tests that is not works with None."""
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is not None:
          return x
        return ""
      """)

  def testSimple(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: file, p2: float) -> int:
        a = ...
        p1.read()
        p2.as_integer_ratio()
        return 1
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def bar(p1: file, p2: float) -> int
    """)

  def testOnlyAnnotations(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: str, p2: complex) -> int:
         pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def bar(p1: str, p2: complex) -> int
    """)

  def testDeep(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: str, p2: complex) -> None:
         pass
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def bar(p1: str, p2: complex) -> None
    """)

  def testUnion(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      def foo(x: typing.Union[int, float], y: int):
        return x + y
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      typing = ...  # type: module
      def foo(x: Union[int, float], y:int) -> Union[int, float]: ...
    """)

  def testCallError(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      s = {1}
      def foo(x: int):
        s.intersection(x)
      foo(3.0)
    """)
    # File "t.py", line 8, in <module>:
    #   Function "foo" was called with the wrong arguments
    #   Expected: (x: int)
    #   Actually passed: (x: float)
    self.assertErrorLogContains(errors, r"line 5.*wrong arguments")

  def testAmbiguousArg(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def f(x: int):
        return x
      def g(y, z):
        if y:
          x = 3
        elif z:
          x = 3j
        else:
          x = "foo"
        f(x)
    """)

  def testInnerError(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: int):
        return x.upper()
    """)
    # Line 3, in foo:
    #   No attribute 'upper' on int
    self.assertErrorLogContains(errors, r"line 3.*no attribute.*upper")

  def testList(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations

      from typing import List

      def foo(l1: List[int], l2: List[str], b):
        if b:
          x = l1
          y = 3
        else:
          x = l2
          y = "foo"
        x.append(y)
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
        List = ...  # type: type
        google_type_annotations = ...  # type: __future__._Feature

        def foo(l1: List[int], l2: List[str], b) -> None: ...
    """)

  def testAnalyzeInit(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import List
      class Foo:
        def f(self, x: List[int]):
          pass
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      List = ...  # type: type
      class Foo:
        def f(self, x: List[int]) -> None: ...
    """)

  def testStringAnnotation(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(c: "int") -> "None":
        c += 1
        return
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def f(c: int) -> None: ...
    """)

  def testTypingOnlyImport(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      import typing
      if typing.TYPE_CHECKING:
        import calendar
      # TODO(kramm): should use quotes
      def f(c: "calendar.Calendar") -> int:
        return c.getfirstweekday()
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      typing = ...  # type: module
      calendar = ...  # type: module
      def f(c: calendar.Calendar) -> int: ...
    """)

  def testAmbiguousAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: int or float):
        return x
      def foo(x: "int or float"):
        return x
    """)
    self.assertErrorLogIs(errors, {
        (2, "invalid-annotation", r"x.*constant"),
        (4, "invalid-annotation", r"x.*constant")})

  def testBadStringAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str()):
        return x
    """)
    self.assertErrorLogIs(errors, {
        (2, "invalid-annotation", r"x.*constant")})

  def testBadReturn(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str, y: str) -> int:
        return "foo"
    """)
    self.assertErrorLogIs(errors, {
        (3, "bad-return-type")})

  def testMultipleReturns(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str, y: str) -> int:
        if x:
          return "foo"
        else:
          return 3j
    """)
    self.assertErrorLogIs(errors, {
        (4, "bad-return-type", r"Expected.*int.*Actual.*str"),
        (6, "bad-return-type", r"Expected.*int.*Actual.*complex")
    })

  def testAmbiguousReturn(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def foo(x: str) -> int:
        if x:
          y = "foo"
        else:
          y = 3j
        return y
    """)
    self.assertErrorLogIs(errors, {
        (7, "bad-return-type",
         r"Expected.*int.*Actual.*Union(?=.*complex).*str"),
    })

  def testDefaultReturn(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      class Foo(object):
        def bar(self, x: float, default="") -> str:
          default.upper
          return default
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      class Foo(object):
        def bar(self, x: float, default=...) -> str: ...
    """)

  def testCompatBool(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: bool) -> bool:
        return None
      bar(None)
    """)

  def testCompatFloat(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: float) -> float:
        return 1
      bar(42)
    """)

  def testCompatUnicodeStr(self):
    # Use str to be identical in py2 and py3
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: unicode) -> unicode:
        return str("foo")
      bar(str("bar"))
    """)

  def testCompatUnicodeBytes(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: unicode) -> unicode:
        return b"foo"
      bar(b"bar")
    """)

  def testCompatUnicodeUnicode(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      def bar(x: unicode) -> unicode:
        return u"foo"
      bar(u"bar")
    """)

  def testUnsolvable(self):
    self.assertNoCrash("""\
      from __future__ import google_type_annotations
      import unknown_module
      def f(x: unknown_module.Iterable):
        pass
    """)

  def testAny(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Any
      def f(x: Any):
        pass
      x = f(3)
    """, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      google_type_annotations = ...  # type: __future__._Feature
      Any = ...  # type: Any
      def f(x: Any) -> None: ...
      x = ...  # type: None
    """)

  def testDict(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Dict, List
      def keys(d: Dict[str, int]):
        return
      keys({"foo": 3})
      keys({})  # ok
      keys({3: 3})  # not allowed
    """, deep=True, extract_locals=True)
    self.assertErrorLogIs(errors, [
        (7, "wrong-arg-types"),
    ])

  def testSequence(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Sequence
      def f(s: Sequence):
        return s
      f([1,2,3])
      f((1,2,3))
      f({1,2,3})
      f(1)
    """, deep=True, extract_locals=True)
    self.assertErrorLogIs(errors, [
        (7, "wrong-arg-types"),
        (8, "wrong-arg-types"),
    ])

  def testOptional(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Optional
      def f(s: Optional[int]):
        return s
      f(1)
      f(None)
      f("foo")
    """, deep=True)
    self.assertErrorLogIs(errors, [
        (7, "wrong-arg-types"),
    ])

  def testSet(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Set
      def f(d: Set[str]):
        return
      f({"foo"})  # ok
      f({})  # not allowed
      f({3})  # not allowed
    """, deep=True, extract_locals=True)
    self.assertErrorLogIs(errors, [
        (6, "wrong-arg-types"),
        (7, "wrong-arg-types"),
    ])

  def testFrozenSet(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import FrozenSet
      def f(d: FrozenSet[str]):
        return
      f(frozenset(["foo"]))  # ok
      f(frozenset())  # ok
      f(frozenset([3]))  # not allowed
    """, deep=True, extract_locals=True)
    self.assertErrorLogIs(errors, [
        (7, "wrong-arg-types"),
    ])

  def testGenericAndTypeVar(self):
    self.assertNoCrash("""\
      from __future__ import google_type_annotations
      import typing
      _T = typing.TypeVar("_T")
      class A(typing.Generic[_T]):
        ...
    """)

  def testJumpIntoClassThroughAnnotation(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      class Foo(object):
        def __init__(self) -> None:
          self.myset = set()
        def qux(self):
          self.myset.add("foo")

      def bar(foo: "Foo"):
        foo.qux()
    """)

  def testForwardDeclarations(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations

      def f(a: "B"):
        return a

      class B(object):
        pass
    """)
    self.assertNoErrors("""
      from __future__ import google_type_annotations

      def f(a) -> "B":
        return B()

      class B(object):
        pass
    """)

  def testWithoutForwardDecl(self):
    _, errorlog = self.InferAndCheck("""\
      from __future__ import google_type_annotations

      def f(a) -> Bar:
        return Bar()

      class Bar(object):
        pass
    """)
    self.assertErrorLogIs(errorlog, [(3, "name-error", r"Bar")])

  def testInvalidForwardDecl(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations

      def f(a) -> "Foo":
        return Foo()

      class Foo(object):
        pass
    """)
    _, errorlog = self.InferAndCheck("""\
      from __future__ import google_type_annotations

      def f(a: "Foo"):
        return B()

      class B(object):
        pass
    """)
    self.assertErrorLogIs(
        errorlog, [(1, "name-error", r"Foo")])

  def testForwardDeclBadReturn(self):
    _, errorlog = self.InferAndCheck("""\
        from __future__ import google_type_annotations

        def f() -> "Foo":
          return 1

        class Foo(object):
          pass
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorLogIs(
        errorlog, [(4, "bad-return-type", r"return type.*int")])

  def testConfusingForwardDecl(self):
    _, errorlog = self.InferAndCheck("""\
        from __future__ import google_type_annotations

        class Foo(object):
          def bar(self):
            return 4

        def f() -> "Foo":
          return Foo()

        class Foo(object):
          def foo(self):
            return 2

        def g():
          return f().bar()
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorLogIs(
        errorlog, [(15, "attribute-error", r"\'bar\'.*Foo")])

  def testReturnTypeError(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      class FooBar(object): pass
      def f() -> FooBar:
        return 3
    """, deep=True)
    self.assertErrorLogIs(errors, [(
        4, "bad-return-type", r"Expected: FooBar")])

  def testUnknownArgument(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def factory() -> type
      """)
      ty = self.Infer("""\
        from __future__ import google_type_annotations
        import a
        A = a.factory()
        def f(x: A):
          return x.name
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        google_type_annotations = ...  # type: __future__._Feature
        from typing import Any
        a = ...  # type: module
        A = ...  # type: type
        def f(x) -> Any
      """)

  def testBadCallNoKwarg(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations

      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(
          labels['baz'])

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def foo() -> None
      def bar(path: str, **kwargs) -> str
    """)
    error = r"Actually passed:.*path: NoneType"
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types", error)])

  def testBadCallWithKwarg(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations

      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(
          labels['baz'], x=42)

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def foo() -> None
      def bar(path: str, **kwargs) -> str
    """)
    error = r"Actually passed:.*path: NoneType, x: int"
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types", error)])

  def testSkipFunctionsWithAnnotations(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      _analyzed_baz = None
      class Foo(object):
        def __init__(self):
          self._executed_init = True
        def bar(self, x: int) -> None:
          self._analyzed_bar = True
      def baz(x: int) -> None:
        global _analyzed_baz
        _analyzed_baz = 3
    """, deep=True, extract_locals=True, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      _analyzed_baz = ... # type: None
      class Foo(object):
        # We expect to *not* see _analyzed_bar here, because it's an attribute
        # initialized by a function we're not analyzing.
        _executed_init = ...  # type: bool
        def bar(self, x: int) -> None: ...
      def baz(x: int) -> None: ...
    """)

  def testAnnotatedInit(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      class A(object):
        def __init__(self, x: str):
          self.x = x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      class A(object):
        x = ...  # type: str
        def __init__(self, x: str) -> None: ...
    """)

  def testUnionInstantiation(self):
    # If unions are not instantiated properly, the call to x.value will
    # cause an error and Infer will fail.
    self.Infer("""
      from __future__ import google_type_annotations
      from typing import Union

      class Container1(object):
        def __init__(self, value):
          self.value1 = value

      class Container2(object):
        def __init__(self, value):
          self.value2 = value

      def func(x: Union[Container1, Container2]):
        if isinstance(x, Container1):
          return x.value1
        else:
          return x.value2
    """, deep=True)

  def testImpreciseAnnotation(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import Union
      class A: pass
      class B:
        x = 42
      def f(v: Union[A, B]):
        return v.x
      f(A())
    """)
    self.assertTypesMatchPytd(ty, """
      Union = ...  # type: type
      google_type_annotations = ...  # type: __future__._Feature
      class A: ...
      class B:
        x = ...  # type: int
      def f(v: Union[A, B]) -> int: ...
    """)

  def testTuple(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def f():
        return (0, "")
      def g(x: str):
        return x
      x = g(f()[1])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def f() -> Tuple[Union[int, str], ...]: ...
      def g(x: str) -> str: ...
      x = ...  # type: str
    """)

  def testOptionalArg(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      def f(x: str, y: bool=False):
        pass
      f("", y=True)
    """)

  def testEmpty(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import List, Any
      def f(x: List[Any]):
        pass
      f([])
    """)

  def testInnerString(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import List, Union
      def f(x: List["int"]):
        pass
      def g(x: Union["int"]):
        pass
    """)
    self.assertErrorLogIs(errors, [(3, "invalid-annotation", r"int.*x.*quote"),
                                   (5, "invalid-annotation", r"int.*x.*quote")])

  def testAmbiguousInnerAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import List, Union
      def f(x: List[int or str]):
        pass
      def g(x: Union[int or str]):
        pass
      def h(x: List[Union[int, str]]):  # okay
        pass
    """)
    self.assertErrorLogIs(errors, [
        (3, "invalid-annotation", r"List.*constant"),
        (5, "invalid-annotation", r"Union.*constant")])

  def testVarargs(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def f(x, *args: int):
        return args
      f("", 42)
      f("", *[])
      f("", *[42])
      f("", *[42.0])
    """)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      def f(x, *args) -> Tuple[int]
    """)
    error = r"Expected.*Tuple\[int\].*Actually passed.*List\[float\]"
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types", error)])

  def testKwargs(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Dict
      def f(x, **kwargs: int):
        return kwargs
      def g() -> Dict[str, float]:
        return __any_object__
      def h() -> Dict[float, int]:
        return __any_object__
      f("", y=42)
      f("", **{})
      f("", **{"y": 42})
      f("", **g())
      f("", **h())
    """)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      Dict = ...  # type: type
      def f(x, **kwargs) -> Dict[str, int]
      def g() -> Dict[str, float]
      def h() -> Dict[float, int]
    """)
    error1 = r"Expected.*Dict\[str, int\].*Actually passed.*Dict\[str, float\]"
    error2 = r"Expected.*Dict\[str, int\].*Actually passed.*Dict\[float, int\]"
    self.assertErrorLogIs(errors, [(12, "wrong-arg-types", error1),
                                   (13, "wrong-arg-types", error2)])

  @unittest.skip("Types not checked due to abstract.FunctionArgs.simplify")
  def testSimplifiedVarargsAndKwargs(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      def f(x, *args: int):
        pass
      def g(x, **kwargs: int):
        pass
      f("", 42.0)
      g("", y=42.0)
      g("", **{"y": 42.0})
    """)
    error = r"Expected.*int.*Actually passed.*float"
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types", error),
                                   (7, "wrong-arg-types", error),
                                   (8, "wrong-arg-types", error)])

  def testUseVarargsAndKwargs(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      class A(object):
        pass
      def f(*args: A):
        return args[0]
      def g(**kwargs: A):
        return kwargs["x"]
      v1 = f()
      v2 = g()
    """)
    # TODO(rechen): Why are the varargs and kwargs annotations dropped below?
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      class A(object): ...
      def f(*args) -> A: ...
      def g(**kwargs) -> A: ...
      v1 = ...  # type: A
      v2 = ...  # type: A
    """)

  def testUseVarargsAndKwargsInForwardReferences(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      class Foo(object):
        def f(self, *args: "Foo", **kwargs: "Foo"):
          for a in args:
            pass
          for a in kwargs:
            pass
      def Bar():
        Foo().f()
    """)

  def testNestedNoneType(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List, Union
      class A:
        x = 42
      def f() -> Union[A, None]:
        pass
      def g() -> List[None]:
        return [None]
      v1 = f().x
      v2 = g()[0]
    """)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      List = ...  # type: type
      Union = ...  # type: type
      class A:
        x = ...  # type: int
      def f() -> Union[A, None]: ...
      def g() -> List[None]: ...
      v1 = ...  # type: int
      v2 = ...  # type: None
    """)

  def testMatchLateAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      class A(object):
        def f(self, x: "A"):
          pass
      def f():
        A().f(42)
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types", r"A.*int")])

  def testRecursiveForwardReference(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      class A(object):
        def __init__(self, x: "A"):
          self.foo = x.foo
          f(x)
        def method1(self):
          self.foo
        def method2(self):
          self.bar
      def f(x: int):
        pass
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"int.*A"),
                                   (9, "attribute-error", r"bar")])

  def testReturnAnnotation1(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      class A(object):
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      x = A.New().x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      class A(object):
        x = ...  # type: int
        New = ...  # type: staticmethod
      x = ...  # type: int
    """)

  def testReturnAnnotation2(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      class A(object):
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      def f():
        return A.New().x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      google_type_annotations = ...  # type: __future__._Feature
      class A(object):
        x = ...  # type: int
        New = ...  # type: staticmethod
      def f() -> int: ...
    """)

  def testDeeplyNestedAnnotation(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Any, Dict, List, Optional
      def G(x: Optional[List[Dict[str, Any]]]):
        if x:
          pass
      def F(x: Optional[List[Dict[str, Any]]]):
        G(x)
    """)

  def testInvalidLateAnnotation(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import List
      Type = "int"
      def f(x: "List[Type]"):
        pass
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation", r"int.*x.*quote")])


if __name__ == "__main__":
  test_inference.main()
