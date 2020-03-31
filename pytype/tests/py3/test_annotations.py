"""Tests for inline annotations."""


from pytype import file_utils
from pytype.tests import test_base


class AnnotationTest(test_base.TargetPython3BasicTest):
  """Tests for PEP 484 style inline annotations."""

  def testNoneUnpackingIs(self):
    """Tests that is works with None."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is None:
          return ""
        return x
      """)

  def testNoneUnpackingIsNot(self):
    """Tests that is not works with None."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is not None:
          return x
        return ""
      """)

  def testOnlyAnnotations(self):
    ty = self.Infer("""
      def bar(p1: str, p2: complex) -> int:
         pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def bar(p1: str, p2: complex) -> int
    """)

  def testDeep(self):
    ty = self.Infer("""
      def bar(p1: str, p2: complex) -> None:
         pass
    """)
    self.assertTypesMatchPytd(ty, """
      def bar(p1: str, p2: complex) -> None
    """)

  def testUnion(self):
    ty = self.Infer("""
      import typing
      def foo(x: typing.Union[int, float], y: int):
        return x + y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      typing = ...  # type: module
      def foo(x: Union[int, float], y:int) -> Union[int, float]: ...
    """)

  def testCallError(self):
    _, errors = self.InferWithErrors("""\
      s = {1}
      def foo(x: int):
        s.intersection(x)
      foo(3.0)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x: int.*x: float"})

  def testAmbiguousArg(self):
    self.Check("""\
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
    _, errors = self.InferWithErrors("""\
      def foo(x: int):
        return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})

  def testList(self):
    ty = self.Infer("""
      from typing import List

      def foo(l1: List[int], l2: List[str], b):
        if b:
          x = l1
          y = 3
        else:
          x = l2
          y = "foo"
        x.append(y)
    """)
    self.assertTypesMatchPytd(ty, """
        from typing import List
        def foo(l1: List[int], l2: List[str], b) -> None: ...
    """)

  def testAnalyzeInit(self):
    ty = self.Infer("""\
      from typing import List
      class Foo:
        def f(self, x: List[int]):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo:
        def f(self, x: List[int]) -> None: ...
    """)

  def testStringAnnotation(self):
    ty = self.Infer("""\
      def f(c: "int") -> "None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(ty, """
      def f(c: int) -> None: ...
    """)

  def testUnicodeAnnotation(self):
    ty = self.Infer("""\
      def f(c: u"int") -> u"None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(ty, """
      def f(c: int) -> None: ...
    """)

  def testFutureUnicodeLiteralAnnotation(self):
    ty = self.Infer("""\
      from __future__ import unicode_literals
      def f(c: "int") -> "None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(ty, """
      import __future__

      unicode_literals = ...  # type: __future__._Feature

      def f(c: int) -> None: ...
    """)

  def testTypingOnlyImport(self):
    ty = self.Infer("""\
      import typing
      if typing.TYPE_CHECKING:
        import calendar
      def f(c: "calendar.Calendar") -> int:
        return c.getfirstweekday()
    """)
    self.assertTypesMatchPytd(ty, """
      typing = ...  # type: module
      calendar = ...  # type: module
      def f(c: calendar.Calendar) -> int: ...
    """)

  def testAmbiguousAnnotation(self):
    _, errors = self.InferWithErrors("""\
      def foo(x: int if __random__ else float):  # invalid-annotation[e1]
        return x
      def foo(x: "int if __random__ else float"):  # invalid-annotation[e2]
        return x
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"float or int.*x.*constant",
        # For a late annotation, we print the string literal, which is why the
        # types below are not in alphabetical order.
        "e2": r"int.*float.*x.*constant"})

  def testBadStringAnnotation(self):
    _, errors = self.InferWithErrors("""\
      def foo(x: str()):  # invalid-annotation[e]
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*constant"})

  def testBadReturn(self):
    self.InferWithErrors("""\
      def foo(x: str, y: str) -> int:
        return "foo"  # bad-return-type
    """)

  def testMultipleReturns(self):
    _, errors = self.InferWithErrors("""\
      def foo(x: str, y: str) -> int:
        if x:
          return "foo"  # bad-return-type[e1]
        else:
          return 3j  # bad-return-type[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Expected.*int.*Actual.*str",
                                     "e2": r"Expected.*int.*Actual.*complex"})

  def testAmbiguousReturn(self):
    _, errors = self.InferWithErrors("""\
      def foo(x: str) -> int:
        if x:
          y = "foo"
        else:
          y = 3j
        return y  # bad-return-type[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*int.*Actual.*Union(?=.*complex).*str"})

  def testDefaultReturn(self):
    ty = self.Infer("""\
      class Foo(object):
        def bar(self, x: float, default="") -> str:
          default.upper
          return default
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def bar(self, x: float, default=...) -> str: ...
    """)

  def testCompatBool(self):
    self.Check("""\
      def bar(x: bool) -> bool:
        return None
      bar(None)
    """)

  def testCompatFloat(self):
    self.Check("""\
      def bar(x: float) -> float:
        return 1
      bar(42)
    """)

  def testCompatUnicodeStr(self):
    # Use str to be identical in py2 and py3
    self.Check("""\
      from typing import Text
      def bar(x: Text) -> Text:
        return str("foo")
      bar(str("bar"))
    """)

  def testUnsolvable(self):
    self.assertNoCrash(self.Check, """\
      import unknown_module
      def f(x: unknown_module.Iterable):
        pass
    """)

  def testAny(self):
    ty = self.Infer("""\
      from typing import Any
      def f(x: Any):
        pass
      x = f(3)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> None: ...
      x = ...  # type: None
    """)

  def testDict(self):
    self.InferWithErrors("""\
      from typing import Dict, List
      def keys(d: Dict[str, int]):
        return
      keys({"foo": 3})
      keys({})  # ok
      keys({3: 3})  # wrong-arg-types
    """, deep=True)

  def testSequence(self):
    self.InferWithErrors("""\
      from typing import Sequence
      def f(s: Sequence):
        return s
      f([1,2,3])
      f((1,2,3))
      f({1,2,3})  # wrong-arg-types
      f(1)  # wrong-arg-types
    """, deep=True)

  def testOptional(self):
    self.InferWithErrors("""\
      from typing import Optional
      def f(s: Optional[int]):
        return s
      f(1)
      f(None)
      f("foo")  # wrong-arg-types
    """, deep=True)

  def testSet(self):
    self.InferWithErrors("""\
      from typing import Set
      def f(d: Set[str]):
        return
      f({"foo"})  # ok
      f(set())  # ok
      f({})  # {} isn't a set  # wrong-arg-types
      f({3})  # wrong-arg-types
    """, deep=True)

  def testFrozenSet(self):
    self.InferWithErrors("""\
      from typing import FrozenSet
      def f(d: FrozenSet[str]):
        return
      f(frozenset(["foo"]))  # ok
      f(frozenset())  # ok
      f(frozenset([3]))  # wrong-arg-types
    """, deep=True)

  def testGenericAndTypeVar(self):
    self.assertNoCrash(self.Check, """\
      import typing
      _T = typing.TypeVar("_T")
      class A(typing.Generic[_T]):
        ...
    """)

  def testJumpIntoClassThroughAnnotation(self):
    self.Check("""\
      class Foo(object):
        def __init__(self) -> None:
          self.myset = set()
        def qux(self):
          self.myset.add("foo")

      def bar(foo: "Foo"):
        foo.qux()
    """)

  def testForwardDeclarations(self):
    self.Check("""
      def f(a: "B"):
        return a

      class B(object):
        pass
    """)
    self.Check("""
      def f(a) -> "B":
        return B()

      class B(object):
        pass
    """)

  def testWithoutForwardDecl(self):
    _, errorlog = self.InferWithErrors("""\
      def f(a) -> Bar:  # name-error[e]
        return Bar()

      class Bar(object):
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Bar"})

  def testInvalidForwardDecl(self):
    self.Check("""
      def f(a) -> "Foo":
        return Foo()

      class Foo(object):
        pass
    """)
    _, errorlog = self.InferWithErrors("""\
      def f(a: "Foo"):  # name-error[e]
        return B()

      class B(object):
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Foo"})

  def testForwardDeclBadReturn(self):
    _, errorlog = self.InferWithErrors("""\
        def f() -> "Foo":
          return 1  # bad-return-type[e]

        class Foo(object):
          pass
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorRegexes(errorlog, {"e": r"return type.*int"})

  def testConfusingForwardDecl(self):
    _, errorlog = self.InferWithErrors("""\
        class Foo(object):
          def foo(self):
            return 4

        def f() -> "Foo":
          return Foo()

        class Foo(object):
          def bar(self):
            return 2

        def g():
          return f().bar()  # attribute-error[e]
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorRegexes(errorlog, {"e": r"\'bar\'.*Foo"})

  def testReturnTypeError(self):
    _, errors = self.InferWithErrors("""\
      class FooBar(object): pass
      def f() -> FooBar:
        return 3  # bad-return-type[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Expected: FooBar"})

  def testUnknownArgument(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def factory() -> type
      """)
      ty = self.Infer("""\
        import a
        A = a.factory()
        def f(x: A):
          return x.name
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        A = ...  # type: Any
        def f(x) -> Any
      """)

  def testBadCallNoKwarg(self):
    ty, errors = self.InferWithErrors("""\
      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(
          labels['baz'])  # wrong-arg-types[e]

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> None
      def bar(path: str, **kwargs) -> str
    """)
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  def testBadCallWithKwarg(self):
    ty, errors = self.InferWithErrors("""\
      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(
          labels['baz'], x=42)  # wrong-arg-types[e]

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> None
      def bar(path: str, **kwargs) -> str
    """)
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  def testSkipFunctionsWithAnnotations(self):
    ty = self.Infer("""\
      _analyzed_baz = None
      class Foo(object):
        def __init__(self):
          self._executed_init = True
        def bar(self, x: int) -> None:
          self._analyzed_bar = True
      def baz(x: int) -> None:
        global _analyzed_baz
        _analyzed_baz = 3
    """, analyze_annotated=False)
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
      class A(object):
        def __init__(self, x: str):
          self.x = x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
        def __init__(self, x: str) -> None: ...
    """)

  def testUnionInstantiation(self):
    # If unions are not instantiated properly, the call to x.value will
    # cause an error and Infer will fail.
    self.Infer("""
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
    """)

  def testImpreciseAnnotation(self):
    ty, errors = self.InferWithErrors("""\
      from typing import Union
      class A: pass
      class B:
        x = 42
      def f(v: Union[A, B]):
        return v.x  # attribute-error[e]
      f(A())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A: ...
      class B:
        x = ...  # type: int
      def f(v: Union[A, B]) -> int: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*A"})

  def testTuple(self):
    ty = self.Infer("""
      def f():
        return (0, "")
      def g(x: str):
        return x
      x = g(f()[1])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      def f() -> Tuple[int, str]: ...
      def g(x: str) -> str: ...
      x = ...  # type: str
    """)

  def testOptionalArg(self):
    self.Check("""
      def f(x: str, y: bool=False):
        pass
      f("", y=True)
    """)

  def testEmpty(self):
    self.Check("""
      from typing import Any, List
      def f(x: List[Any]):
        pass
      f([])
    """)

  def testInnerString(self):
    self.Check("""\
      from typing import List, Union
      def f(x: List["int"]):
        pass
      def g(x: Union["int"]):
        pass
    """)

  def testAmbiguousInnerAnnotation(self):
    _, errors = self.InferWithErrors("""\
      from typing import List, Union
      def f(x: List[int if __random__ else str]):  # invalid-annotation[e1]
        pass
      def g(x: Union[int if __random__ else str]):  # invalid-annotation[e2]
        pass
      def h(x: List[Union[int, str]]):  # okay
        pass
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"List\[int\] or List\[str\].*constant",
        "e2": r"int or str.*constant"})

  def testKwargs(self):
    ty, errors = self.InferWithErrors("""\
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
      f("", **g())  # wrong-arg-types[e1]
      f("", **h())  # wrong-arg-types[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f(x, **kwargs: int) -> Dict[str, int]
      def g() -> Dict[str, float]
      def h() -> Dict[float, int]
    """)
    error1 = (r"Expected.*Mapping\[str, int\].*"
              r"Actually passed.*Dict\[str, float\]")
    error2 = (r"Expected.*Mapping\[str, int\].*"
              r"Actually passed.*Dict\[float, int\]")
    self.assertErrorRegexes(errors, {"e1": error1, "e2": error2})

  @test_base.skip("Types not checked due to function.Args.simplify")
  def testSimplifiedVarargsAndKwargs(self):
    _, errors = self.InferWithErrors("""\
      def f(x, *args: int):
        pass
      def g(x, **kwargs: int):
        pass
      f("", 42.0)  # wrong-arg-types[e1]
      g("", y=42.0)  # wrong-arg-types[e2]
      g("", **{"y": 42.0})  # wrong-arg-types[e3]
    """)
    error = r"Expected.*int.*Actually passed.*float"
    self.assertErrorRegexes(errors, {"e1": error, "e2": error, "e3": error})

  def testUseVarargsAndKwargs(self):
    ty = self.Infer("""
      class A(object):
        pass
      def f(*args: A):
        return args[0]
      def g(**kwargs: A):
        return kwargs["x"]
      v1 = f()
      v2 = g()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class A(object): ...
      def f(*args: A) -> A: ...
      def g(**kwargs: A) -> A: ...
      v1 = ...  # type: A
      v2 = ...  # type: A
    """)

  def testUseVarargsAndKwargsInForwardReferences(self):
    self.Check("""
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
    ty, errors = self.InferWithErrors("""\
      from typing import List, Union
      class A:
        x = 42
      def f() -> Union[A, None]:
        pass
      def g() -> List[None]:
        return [None]
      v1 = f().x  # attribute-error[e]
      v2 = g()[0]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      class A:
        x = ...  # type: int
      def f() -> Union[A, None]: ...
      def g() -> List[None]: ...
      v1 = ...  # type: int
      v2 = ...  # type: None
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*None"})

  def testMatchLateAnnotation(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        def f(self, x: "A"):
          pass
      def f():
        A().f(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*int"})

  def testRecursiveForwardReference(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        def __init__(self, x: "A"):
          self.foo = x.foo
          f(x)  # wrong-arg-types[e1]
        def method1(self):
          self.foo
        def method2(self):
          self.bar  # attribute-error[e2]
      def f(x: int):
        pass
    """)
    self.assertErrorRegexes(errors, {"e1": r"int.*A", "e2": r"bar"})

  def testModuleLevelForwardReferenceError(self):
    errors = self.CheckWithErrors("""\
      class A(object):
        def f(self, x: "A"):
          pass
      A().f(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*int"})

  def testReturnAnnotation1(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      x = A.New().x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: int
        @staticmethod
        def New() -> A: ...
      x = ...  # type: int
    """)

  def testReturnAnnotation2(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      def f():
        return A.New().x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: int
        @staticmethod
        def New() -> A: ...
      def f() -> int: ...
    """)

  def testDeeplyNestedAnnotation(self):
    self.Check("""\
      from typing import Any, Dict, List, Optional
      def G(x: Optional[List[Dict[str, Any]]]):
        if x:
          pass
      def F(x: Optional[List[Dict[str, Any]]]):
        G(x)
    """)

  def testNestedLateAnnotation(self):
    self.Check("""\
      from typing import List
      Type = "int"
      def f(x: "List[Type]"):
        pass
    """)

  def testLateAnnotation(self):
    ty = self.Infer("""\
      def new_x() -> 'X':
        return X()
      class X(object):
        def __init__(self) -> None:
          self.foo = 1
      def get_foo() -> int:
        return new_x().foo
    """)
    self.assertTypesMatchPytd(ty, """
      def new_x() -> X: ...
      def get_foo() -> int: ...

      class X(object):
        foo = ...  # type: int
    """)

  def testChangeAnnotatedArg(self):
    ty = self.Infer("""\
      from typing import Dict
      def f(x: Dict[str, str]):
        x[True] = 42
        return x
      v = f({"a": "b"})
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f(x: Dict[str, str]) -> Dict[str or bool, str or int]: ...
      v = ...  # type: Dict[str or bool, str or int]
    """)

  def testInnerStringAnnotation(self):
    ty = self.Infer("""\
      from typing import List
      def f(x: List["A"]) -> int:
        pass
      class A(object):
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import typing

      def f(x: typing.List[A]) -> int: ...

      class A(object): ...
    """)

  def testTypeAliasAnnotation(self):
    ty = self.Infer("""\
      from typing import List
      TypeA = "A"
      ListA = "List[A]"
      def f(x: "ListA") -> int:
        pass
      class A(object):
        pass
    """, deep=False)
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
      from typing import List
      def f(x: "List[\\"int\\"]") -> int:
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f(x: List[int]) -> int: ...
    """)

  def testDuplicateIdentifier(self):
    ty = self.Infer("""\
      t = int
      def f(x: t) -> int: pass
      def g(x: "t") -> int: pass
      t = float
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      t: Type[float]
      def f(x: int) -> int: ...
      def g(x: int) -> int: ...
    """)

  def testEllipsis(self):
    ty, errors = self.InferWithErrors("""\
      from typing import Dict, Tuple
      def f(x: ...): pass  # invalid-annotation[e1]
      def g(x: Tuple[str, ...]): pass
      def h(x: Dict[..., int]): pass  # invalid-annotation[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Tuple
      def f(x) -> None: ...
      def g(x: Tuple[str, ...]) -> None: ...
      def h(x: Dict[Any, int]) -> None: ...
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Ellipsis.*x", "e2": r"Ellipsis.*Dict"})

  def testCustomContainer(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic
        T = TypeVar("T")
        T2 = TypeVar("T2")
        class Foo(Generic[T]):
          def __init__(self, x: T2):
            self = Foo[T2]
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        def f(x: foo.Foo[int]):
          pass
        f(foo.Foo(42))
        f(foo.Foo(""))  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"Foo\[int\].*Foo\[str\]"})

  def testNoImplicitOptional(self):
    ty, _ = self.InferWithErrors("""\
      from typing import Optional, Union
      def f1(x: str = None):
        pass
      def f2(x: Optional[str] = None):
        pass
      def f3(x: Union[str, None] = None):
        pass
      def f4(x: Union[str, int] = None):
        pass
      f1(None)  # wrong-arg-types
      f2(None)
      f3(None)
      f4(None)  # wrong-arg-types
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      def f1(x: str = ...) -> None: ...
      def f2(x: Optional[str] = ...) -> None: ...
      def f3(x: Optional[str] = ...) -> None: ...
      def f4(x: Union[str, int] = ...) -> None: ...
    """)

  def testInferReturn(self):
    ty = self.Infer("""
      def f(x: int):
        return x
    """, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> int: ...
    """)

  def testReturnAbstractDict(self):
    self.Check("""
      from typing import Dict
      def f(x, y):
        pass
      def g() -> Dict:
        return {"y": None}
      def h():
        f(x=None, **g())
    """)

  def testRecursiveTypeAlias(self):
    errors = self.CheckWithErrors("""\
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      def f(x: Foo):  # not-supported-yet[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def testFullyQuotedAnnotation(self):
    self.Check("""
      from typing import Optional
      class A(object):
        OBJ = ()
        def __init__(self, parent: "Optional[A]"):
          self.parent = (self.OBJ, parent)
    """)

  def testQuotedGenericParameter(self):
    ty = self.Infer("""
      from typing import Callable, List
      def f(x: List["Callable[[int], str]"]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, List
      def f(x: List[Callable[[int], str]]) -> None: ...
    """)

  def testLateAnnotationNonNameError(self):
    self.CheckWithErrors("""\
      class Foo(object):
        pass
      def f(x: "Foo.Bar"):  # attribute-error
        pass
    """)

  def testKeepContainerWithError(self):
    ty, _ = self.InferWithErrors("""\
      from typing import Dict
      def f(x: "Dict[str, int.error]"):  # attribute-error
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      def f(x: Dict[str, Any]) -> None: ...
    """)


class TestAnnotationsPython3Feature(test_base.TargetPython3FeatureTest):
  """Tests for PEP 484 style inline annotations."""

  def testVariableAnnotations(self):
    ty = self.Infer("""
      a : int = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a: int
    """)


test_base.main(globals(), __name__ == "__main__")
