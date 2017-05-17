"""Tests for inline annotations."""

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
      def bar(p1: file, p2: float) -> int
    """)

  def testOnlyAnnotations(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: str, p2: complex) -> int:
         pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def bar(p1: str, p2: complex) -> int
    """)

  def testDeep(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def bar(p1: str, p2: complex) -> None:
         pass
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def bar(p1: str, p2: complex) -> None
    """)

  def testUnion(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      def foo(x: typing.Union[int, float], y: int):
        return x + y
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
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
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"x: int.*x: float")])

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
    self.assertErrorLogIs(errors, [(3, "attribute-error", r"upper.*int")])

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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
        from typing import List
        def foo(l1: List[int], l2: List[str], b) -> None: ...
    """)

  def testAnalyzeInit(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import List
      class Foo:
        def f(self, x: List[int]):
          pass
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo:
        def f(self, x: List[int]) -> None: ...
    """)

  def testStringAnnotation(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(c: "int") -> "None":
        c += 1
        return
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
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
        (2, "invalid-annotation", r"float or int.*x.*constant"),
        # For a late annotation, we print the string literal, which is why
        # 'int or float' below is not in alphabetical order.
        (4, "invalid-annotation", r"int or float.*x.*constant")})

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
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> None: ...
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
    """, deep=True)
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
    """, deep=True)
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
    """, deep=True)
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
    """, deep=True)
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
        errorlog, [(3, "invalid-annotation", r"Foo")])

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
      def foo() -> None
      def bar(path: str, **kwargs) -> str
    """)
    error = r"Actually passed:.*path: None"
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
      def foo() -> None
      def bar(path: str, **kwargs) -> str
    """)
    error = r"Actually passed:.*path: None"
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
    """, deep=True, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
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
    ty, errors = self.InferAndCheck("""
      from __future__ import google_type_annotations
      from typing import Union
      class A: pass
      class B:
        x = 42
      def f(v: Union[A, B]):
        return v.x
      f(A())
    """, strict_attr_checking=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A: ...
      class B:
        x = ...  # type: int
      def f(v: Union[A, B]) -> int: ...
    """)
    self.assertErrorLogIs(errors, [(8, "attribute-error", "x.*A")])

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
      from typing import Tuple
      def f() -> Tuple[int, str]: ...
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
      from typing import Any, List
      def f(x: List[Any]):
        pass
      f([])
    """)

  def testInnerString(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import List, Union
      def f(x: List["int"]):
        pass
      def g(x: Union["int"]):
        pass
    """)

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
        (3, "invalid-annotation", r"int or str.*constant"),
        (5, "invalid-annotation", r"int or str.*constant")])

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
      from typing import Tuple
      def f(x, *args) -> Tuple[int, ...]
    """)
    error = r"Expected.*Iterable\[int\].*Actually passed.*List\[float\]"
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
      from typing import Dict
      def f(x, **kwargs) -> Dict[str, int]
      def g() -> Dict[str, float]
      def h() -> Dict[float, int]
    """)
    error1 = (r"Expected.*Mapping\[str, int\].*"
              r"Actually passed.*Dict\[str, float\]")
    error2 = (r"Expected.*Mapping\[str, int\].*"
              r"Actually passed.*Dict\[float, int\]")
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
      from typing import List, Union
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
      class A(object):
        x = ...  # type: int
        @staticmethod
        def New() -> A: ...
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
      class A(object):
        x = ...  # type: int
        @staticmethod
        def New() -> "A": ...
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

  def testNestedLateAnnotation(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import List
      Type = "int"
      def f(x: "List[Type]"):
        pass
    """)

  def testChangeAnnotatedArg(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Dict
      def f(x: Dict[str, str]):
        x[True] = 42
        return x
      v = f({"a": "b"})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f(x: Dict[str, str]) -> Dict[str or bool, str or int]: ...
      v = ...  # type: Dict[str or bool, str or int]
    """)

  def testInnerStringAnnotation(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import List
      def f(x: List["A"]) -> int:
        pass
      class A(object):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import typing

      def f(x: typing.List[A]) -> int: ...

      class A(object): ...
    """)

  def testTypeAliasAnnotation(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import List
      TypeA = "A"
      ListA = "List[A]"
      def f(x: "ListA") -> int:
        pass
      class A(object):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import typing
      ListA = ...  # type: str
      TypeA = ...  # type: str
      def f(x: typing.List[A]) -> int: ...
      class A(object):
          pass
    """)

  def testDoubleString(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import List
      def f(x: "List[\\"int\\"]") -> int:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f(x: List[int]) -> int: ...
    """)

  def testDuplicateIdentifier(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      t = int
      def f(x: t) -> int: pass
      def g(x: "t") -> int: pass
      t = float
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      t = ...  # type: Type[float]
      def f(x: int) -> int: ...
      def g(x: float) -> int: ...
    """)

  def testEllipsis(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Dict, Tuple
      def f(x: ...): pass
      def g(x: Tuple[str, ...]): pass
      def h(x: Dict[..., int]): pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Tuple
      def f(x) -> None: ...
      def g(x: Tuple[str, ...]) -> None: ...
      def h(x: Dict[Any, int]) -> None: ...
    """)
    self.assertErrorLogIs(errors, [(3, "invalid-annotation", r"Ellipsis.*x")])

  def testCustomContainer(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic
        T = TypeVar("T")
        T2 = TypeVar("T2")
        class Foo(Generic[T]):
          def __init__(self, x: T2):
            self := Foo[T2]
      """)
      _, errors = self.InferAndCheck("""\
        from __future__ import google_type_annotations
        import foo
        def f(x: foo.Foo[int]):
          pass
        f(foo.Foo(42))
        f(foo.Foo(""))
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                      r"Foo\[int\].*Foo\[str\]")])

  def testImplicitOptional(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Optional, Union
      def f1(x: str = None):
        pass
      def f2(x: Optional[str] = None):
        pass
      def f3(x: Union[str, None] = None):
        pass
      def f4(x: Union[str, int] = None):
        pass
      f1(None)
      f2(None)
      f3(None)
      f4(None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      def f1(x: Optional[str] = ...) -> None: ...
      def f2(x: Optional[str] = ...) -> None: ...
      def f3(x: Optional[str] = ...) -> None: ...
      def f4(x: Optional[Union[str, int]] = ...) -> None: ...
    """)


if __name__ == "__main__":
  test_inference.main()
