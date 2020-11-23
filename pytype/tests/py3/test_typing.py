"""Tests for typing.py."""

from pytype import file_utils
from pytype.pytd import pep484
from pytype.tests import test_base
from pytype.tests import test_utils


class TypingTest(test_base.TargetPython3BasicTest):
  """Tests for typing.py."""

  _TEMPLATE = """
    import collections
    import typing
    def f(s: %(annotation)s):%(disables)s
      return s
    f(%(arg)s)
  """

  def _test_match(self, arg, annotation, disables=""):
    self.Check(self._TEMPLATE % locals())

  def _test_no_match(self, arg, annotation, disables=""):
    code = (self._TEMPLATE % locals()).rstrip() + "  # wrong-arg-types"
    self.InferWithErrors(code)

  def test_list_match(self):
    self._test_match("[1, 2, 3]", "typing.List")
    self._test_match("[1, 2, 3]", "typing.List[int]")
    self._test_match("[1, 2, 3.1]", "typing.List[typing.Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "typing.List[int]")

  def test_sequence_match(self):
    self._test_match("[1, 2, 3]", "typing.Sequence")
    self._test_match("[1, 2, 3]", "typing.Sequence[int]")
    self._test_match("(1, 2, 3.1)", "typing.Sequence[typing.Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "typing.Sequence[int]")

  def test_generator(self):
    self.Check("""
      from typing import Generator
      def f() -> Generator[int, None, None]:
        for i in range(3):
          yield i
    """)

  def test_type(self):
    ty, errors = self.InferWithErrors("""
      from typing import Type
      class Foo:
        x = 1
      def f1(foo: Type[Foo]):
        return foo.x
      def f2(foo: Type[Foo]):
        return foo.y  # attribute-error[e]
      def f3(foo: Type[Foo]):
        return foo.mro()
      def f4(foo: Type[Foo]):
        return foo()
      v1 = f1(Foo)
      v2 = f2(Foo)
      v3 = f3(Foo)
      v4 = f4(Foo)
    """)
    self.assertErrorRegexes(errors, {"e": r"y.*Foo"})
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type
      class Foo:
        x = ...  # type: int
      def f1(foo: Type[Foo]) -> int: ...
      def f2(foo: Type[Foo]) -> Any: ...
      def f3(foo: Type[Foo]) -> list: ...
      def f4(foo: Type[Foo]) -> Foo: ...
      v1 = ...  # type: int
      v2 = ...  # type: Any
      v3 = ...  # type: list
      v4 = ...  # type: Foo
    """)

  def test_type_union(self):
    _, errors = self.InferWithErrors("""
      from typing import Type, Union
      class Foo:
        bar = ...  # type: int
      def f1(x: Type[Union[int, Foo]]):
        # Currently not an error, since attributes on Unions are retrieved
        # differently.  See get_attribute() in attribute.py.
        x.bar
      def f2(x: Union[Type[int], Type[Foo]]):
        x.bar  # attribute-error[e]
        f1(x)
      def f3(x: Type[Union[int, Foo]]):
        f1(x)
        f2(x)
    """)
    self.assertErrorRegexes(errors, {"e": r"bar.*int"})

  def test_use_type_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List
        MyType = List[str]
      """)
      self.Check("""
        import foo
        def f(x: foo.MyType):
          pass
        f([""])
      """, pythonpath=[d.path])

  def test_callable(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable
        def f() -> Callable: ...
      """)
      self.Check("""
        from typing import Callable
        import foo
        def f() -> Callable:
          return foo.f()
        def g() -> Callable:
          return int
      """, pythonpath=[d.path])

  def test_callable_parameters(self):
    ty, errors = self.InferWithErrors("""
      from typing import Any, Callable

      # The below are all valid.
      def f1(x: Callable[[int, str], bool]): ...
      def f2(x: Callable[..., bool]): ...
      def f3(x: Callable[[], bool]): ...

      def g1(x: Callable[int, bool]): ...  # _ARGS not a list  # invalid-annotation[e1]
      lst = [int] if __random__ else [str]
      def g2(x: Callable[lst, bool]): ...  # _ARGS ambiguous  # invalid-annotation[e2]  # invalid-annotation[e3]
      # bad: _RET ambiguous
      def g3(x: Callable[[], bool if __random__ else str]): ...  # invalid-annotation[e4]
      # bad: _ARGS[0] ambiguous
      def g4(x: Callable[[int if __random__ else str], bool]): ...  # invalid-annotation[e5]
      lst = None  # type: list[int]
      def g5(x: Callable[lst, bool]): ...  # _ARGS not a constant  # invalid-annotation[e6]
      def g6(x: Callable[[42], bool]): ...  # _ARGS[0] not a type  # invalid-annotation[e7]
      def g7(x: Callable[[], bool, int]): ...  # Too many params  # invalid-annotation[e8]
      def g8(x: Callable[Any, bool]): ...  # Any is not allowed  # invalid-annotation[e9]
      def g9(x: Callable[[]]) -> None: ...  # invalid-annotation[e10]
    """)
    self.assertTypesMatchPytd(ty, """
       from typing import Any, Callable, List, Type

       lst = ...  # type: List[int]

       def f1(x: Callable[[int, str], bool]) -> None: ...
       def f2(x: Callable[Any, bool]) -> None: ...
       def f3(x: Callable[[], bool]) -> None: ...
       def g1(x: Callable[Any, bool]) -> None: ...
       def g2(x: Callable[Any, bool]) -> None: ...
       def g3(x: Callable[[], Any]) -> None: ...
       def g4(x: Callable[[Any], bool]) -> None: ...
       def g5(x: Callable[Any, bool]) -> None: ...
       def g6(x: Callable[[Any], bool]) -> None: ...
       def g7(x: Callable[[], bool]) -> None: ...
       def g8(x: Callable[Any, bool]) -> None: ...
       def g9(x: Callable[[], Any]) -> None: ...
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"'int'.*must be a list of argument types or ellipsis",
        "e2": r"\[int\] or \[str\].*Must be constant",
        "e3": r"'Any'.*must be a list of argument types or ellipsis",
        "e4": r"bool or str.*Must be constant",
        "e5": r"int or str.*Must be constant",
        "e6": r"instance of List\[int\].*Must be constant",
        "e7": r"instance of int",
        "e8": r"Callable.*Expected 2.*got 3",
        "e9": r"'Any'.*must be a list of argument types or ellipsis",
        "e10": r"Callable\[_ARGS, _RET].*2.*1"})

  def test_callable_bad_args(self):
    ty, errors = self.InferWithErrors("""
      from typing import Callable
      lst1 = [str]
      lst1[0] = int
      def g1(x: Callable[lst1, bool]): ...  # invalid-annotation[e1]
      lst2 = [str]
      while __random__:
        lst2.append(int)
      def g2(x: Callable[lst2, bool]): ...  # invalid-annotation[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, List, Type, Union
      lst1 = ...  # type: List[Type[Union[int, str]]]
      lst2 = ...  # type: List[Type[Union[int, str]]]
      def g1(x: Callable[..., bool]) -> None: ...
      def g2(x: Callable[..., bool]) -> None: ...
    """)
    # For the first error, it would be more precise to say [str or int], since
    # the mutation is simple enough that we could keep track of the change to
    # the constant, but we don't do that yet.
    self.assertErrorRegexes(errors, {
        "e1": (r"instance of List\[Type\[Union\[int, str\]\]\].*"
               r"Must be constant"),
        "e2": r"instance of List\[Type\[Union\[int, str\]\]\].*Must be constant"
    })

  def test_generics(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Dict
        K = TypeVar("K")
        V = TypeVar("V")
        class CustomDict(Dict[K, V]): ...
      """)
      self.Check("""
        import typing
        import foo
        def f(x: typing.Callable[..., int]): pass
        def f(x: typing.Iterator[int]): pass
        def f(x: typing.Iterable[int]): pass
        def f(x: typing.Container[int]): pass
        def f(x: typing.Sequence[int]): pass
        def f(x: typing.Tuple[int, str]): pass
        def f(x: typing.MutableSequence[int]): pass
        def f(x: typing.List[int]): pass
        def f(x: typing.Deque[int]): pass
        def f(x: typing.IO[str]): pass
        def f(x: typing.Collection[str]): pass
        def f(x: typing.Mapping[int, str]): pass
        def f(x: typing.MutableMapping[int, str]): pass
        def f(x: typing.Dict[int, str]): pass
        def f(x: typing.AbstractSet[int]): pass
        def f(x: typing.FrozenSet[int]): pass
        def f(x: typing.MutableSet[int]): pass
        def f(x: typing.Set[int]): pass
        def f(x: typing.Reversible[int]): pass
        def f(x: typing.SupportsAbs[int]): pass
        def f(x: typing.Optional[int]): pass
        def f(x: typing.Generator[int, None, None]): pass
        def f(x: typing.Type[int]): pass
        def f(x: typing.Pattern[str]): pass
        def f(x: typing.Match[str]): pass
        def f(x: foo.CustomDict[int, str]): pass
      """, pythonpath=[d.path])

  def test_generator_iterator_match(self):
    self.Check("""
      from typing import Iterator
      def f(x: Iterator[int]):
        pass
      f(x for x in [42])
    """)

  def test_name_conflict(self):
    ty = self.Infer("""
      import typing
      def f() -> typing.Any:
        pass
      class Any(object):
        pass
      def g() -> Any:
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      import __future__
      typing = ...  # type: module
      def f() -> typing.Any: ...
      def g() -> Any: ...
      class Any(object):
          pass
    """)

  def test_callable_call(self):
    ty, errors = self.InferWithErrors("""
      from typing import Callable
      f = ...  # type: Callable[[int], str]
      v1 = f()  # wrong-arg-count[e1]
      v2 = f(True)  # ok
      v3 = f(42.0)  # wrong-arg-types[e2]
      v4 = f(1, 2)  # wrong-arg-count[e3]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      f = ...  # type: Callable[[int], str]
      v1 = ...  # type: Any
      v2 = ...  # type: str
      v3 = ...  # type: Any
      v4 = ...  # type: Any
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"1.*0", "e2": r"int.*float", "e3": r"1.*2"})

  def test_callable_call_with_type_parameters(self):
    ty, errors = self.InferWithErrors("""
      from typing import Callable, TypeVar
      T = TypeVar("T")
      def f(g: Callable[[T, T], T], y, z):
        return g(y, z)  # wrong-arg-types[e]
      v1 = f(__any_object__, 42, 3.14)  # ok
      v2 = f(__any_object__, 42, "hello world")
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, TypeVar, Union
      T = TypeVar("T")
      def f(g: Callable[[T, T], T], y, z): ...
      v1 = ...  # type: Union[int, float]
      v2 = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_callable_call_with_return_only(self):
    ty = self.Infer("""
      from typing import Callable
      f = ...  # type: Callable[..., int]
      v = f()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      f = ...  # type: Callable[..., int]
      v = ...  # type: int
    """)

  def test_callable_call_with_varargs_and_kwargs(self):
    _, errors = self.InferWithErrors("""
      from typing import Callable
      f = ...  # type: Callable[[], int]
      f(x=3)  # wrong-keyword-args[e1]
      f(*(42,))  # wrong-arg-count[e2]
      f(**{"x": "hello", "y": "world"})  # wrong-keyword-args[e3]
      f(*(42,), **{"hello": "world"})  # wrong-keyword-args[e4]
    """)
    self.assertErrorRegexes(errors, {"e1": r"x", "e2": r"0.*1", "e3": r"x, y",
                                     "e4": r"hello"})

  def test_callable_attribute(self):
    self.Check("""
      from typing import Any, Callable
      def foo(fn: Callable[[Any], Any]):
        fn.foo # pytype: disable=attribute-error
    """)

  def test_items_view(self):
    self.Check("""
      from typing import ItemsView
      def f(x: ItemsView[str, int]): ...
    """)

  def test_new_type(self):
    ty = self.Infer("""
      from typing import NewType
      MyInt = NewType('MyInt', int)
      class A(object):
        pass
      MyA = NewType('MyA', A)
      MySpecialA = NewType('MySpecialA', MyA)
      MyStr1 = NewType(*('MyStr1', str))
      MyStr2 = NewType(**{'tp':str, 'name':'MyStr2'})
      MyAnyType = NewType('MyAnyType', tp=str if __random__ else int)
      MyFunnyNameType = NewType('Foo' if __random__ else 'Bar', tp=str)
      def func1(i: MyInt) -> MyInt:
        return i
      def func2(i: MyInt) -> int:
        return i
      def func3(a: MyA) -> MyA:
        return a
      def func4(a: MyA) -> A:
        return a
      def func5(a: MySpecialA) -> MySpecialA:
        return a
      def func6(a: MySpecialA) -> MyA:
        return a
      def func7(a: MySpecialA) -> A:
        return a
      v = 123
      func1(MyInt(v))
      func2(MyInt(v))
      my_a = MyA(A())
      func3(my_a)
      func4(my_a)
      my_special_a = MySpecialA(my_a)
      func5(my_special_a)
      func6(my_special_a)
      func7(my_special_a)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        pass
      class MyInt(int):
        def __init__(self, val: int): ...
      class MyA(A):
        def __init__(self, val: A): ...
      class MySpecialA(MyA):
        def __init__(self, val: MyA): ...
      class MyStr1(str):
        def __init__(self, val: str): ...
      class MyStr2(str):
        def __init__(self, val: str): ...
      MyAnyType = ... # type: Any
      class MyFunnyNameType(str):
        def __init__(self, val:str): ...
      def func1(i: MyInt) -> MyInt: ...
      def func2(i: MyInt) -> int: ...
      def func3(a: MyA) -> MyA: ...
      def func4(a: MyA) -> A: ...
      def func5(a: MySpecialA) -> MySpecialA: ...
      def func6(a: MySpecialA) -> MyA: ...
      def func7(a: MySpecialA) -> A: ...
      v = ...  # type: int
      my_a = ...  # type: MyA
      my_special_a = ...  # type: MySpecialA
    """)

  def test_new_type_error(self):
    _, errors = self.InferWithErrors("""
      from typing import NewType
      MyInt = NewType('MyInt', int)
      MyStr = NewType('MyStr', str)
      def func1(i: MyInt) -> MyInt:
        return i
      def func2(i: int) -> MyInt:
        return i  # bad-return-type[e1]
      def func3(s: MyStr) -> MyStr:
        return s
      func1(123)  # wrong-arg-types[e2]
      func3(MyStr(123))  # wrong-arg-types[e3]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Expected: MyInt\nActually returned: int",
        "e2": r".*Expected: \(i: MyInt\)\nActually passed: \(i: int\)",
        "e3": r".*Expected:.*val: str\)\nActually passed:.*val: int\)"})

  def test_maybe_return(self):
    self.Check("""
      def f() -> int:
        if __random__:
          return 42
        else:
          raise ValueError()
    """)

  def test_no_return_against_str(self):
    ty = self.Infer("""
      def f() -> str:
        raise ValueError()
      def g():
        return f()
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> str: ...
      def g() -> str: ...
    """)

  def test_called_no_return_against_str(self):
    self.Check("""
      def f():
        raise ValueError()
      def g() -> str:
        return f()
    """)

  def test_union_ellipsis(self):
    errors = self.CheckWithErrors("""
      from typing import Union
      MyUnion = Union[int, ...]  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Ellipsis.*index 1.*Union"})

  def test_list_ellipsis(self):
    errors = self.CheckWithErrors("""
      from typing import List
      MyList = List[int, ...]  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Ellipsis.*index 1.*List"})

  def test_multiple_ellipses(self):
    errors = self.CheckWithErrors("""
      from typing import Union
      MyUnion = Union[..., int, ..., str, ...]  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Ellipsis.*indices 0, 2, 4.*Union"})

  def test_bad_tuple_ellipsis(self):
    errors = self.CheckWithErrors("""
      from typing import Tuple
      MyTuple1 = Tuple[..., ...]  # invalid-annotation[e1]
      MyTuple2 = Tuple[...]  # invalid-annotation[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Ellipsis.*index 0.*Tuple",
                                     "e2": r"Ellipsis.*index 0.*Tuple"})

  def test_bad_callable_ellipsis(self):
    errors = self.CheckWithErrors("""
      from typing import Callable
      MyCallable1 = Callable[..., ...]  # invalid-annotation[e1]
      MyCallable2 = Callable[[int], ...]  # invalid-annotation[e2]
      MyCallable3 = Callable[[...], int]  # invalid-annotation[e3]
      MyCallable4 = Callable[[int], int, int]  # invalid-annotation[e4]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Ellipsis.*index 1.*Callable",
        "e2": r"Ellipsis.*index 1.*Callable",
        "e3": r"Ellipsis.*index 0.*list",
        "e4": r"Callable\[_ARGS, _RET].*2.*3"})

  def test_optional_parameters(self):
    errors = self.CheckWithErrors("""
      from typing import Optional

      def func1(x: Optional[int]):
        pass

      def func2(x: Optional):  # invalid-annotation[e1]
        pass

      def func3(x: Optional[int, float, str]):  # invalid-annotation[e2]
        pass
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Not a type",
                 "e2": r"typing\.Optional can only contain one type parameter"})

  def test_noreturn_parameters(self):
    errors = self.CheckWithErrors("""
      from typing import NoReturn, List

      def func0() -> NoReturn:
        raise ValueError()

      def func1() -> List[NoReturn]:  # invalid-annotation[e1]
        raise ValueError()

      def func2(x) -> NoReturn:
        if x > 1:
          raise ValueError()  # bad-return-type[e2]

      def func3(x: NoReturn):  # invalid-annotation[e3]
        pass

      def func4(x: List[NoReturn]):  # invalid-annotation[e4]
        pass

      bad = None  # type: NoReturn  # invalid-annotation[e5]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"NoReturn is not allowed", "e2": r"NoReturn.*None",
        "e3": r"NoReturn is not allowed", "e4": r"NoReturn is not allowed",
        "e5": r"NoReturn is not allowed"})

  def test_SupportsComplex(self):
    self.Check("""
      from typing import SupportsComplex
      def foo(x: SupportsComplex):
        pass
      foo(1j)
    """)

  def test_mutable_set_sub(self):
    self.Check("""
      from typing import MutableSet
      def f(x: MutableSet) -> MutableSet:
        return x - {0}
    """)

  def test_union_of_classes(self):
    ty = self.Infer("""
      from typing import Type, Union

      class Foo(object):
        def __getitem__(self, x) -> int:
          return 0
      class Bar(object):
        def __getitem__(self, x) -> str:
          return ''

      def f(x: Union[Type[Foo], Type[Bar]]):
        return x.__getitem__
      def g(x: Type[Union[Foo, Bar]]):
        return x.__getitem__
    """)
    # The inferred return type of `g` is technically incorrect: it is inferred
    # from the type of abstract.Union.getitem_slot, which is a NativeFunction,
    # so its type defaults to a plain Callable. We should instead look up
    # Foo.__getitem__ and Bar.__getitem__ as we do for `f`, but it is currently
    # not possible to distinguish between using Union.getitem_slot and accessing
    # the actual __getitem__ method on a union's options. Inferring `Callable`
    # should generally be safe, since __getitem__ is a method by convention.
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, Type, Union

      class Foo:
        def __getitem__(self, x) -> int: ...
      class Bar:
        def __getitem__(self, x) -> str: ...

      def f(x: Type[Union[Foo, Bar]]) -> Callable[[Any, Any], Union[int, str]]: ...
      def g(x: Type[Union[Foo, Bar]]) -> Callable: ...
    """)

  def test_bytestring(self):
    self.Check("""
      from typing import ByteString, Union
      def f(x: Union[bytes, bytearray, memoryview]):
        pass
      x = None  # type: ByteString
      f(x)
    """)


class CounterTest(test_base.TargetPython3BasicTest):
  """Tests for typing.Counter."""

  def test_counter_generic(self):
    ty, _ = self.InferWithErrors("""
      import collections
      import typing
      def freqs(s: str) -> typing.Counter[str]:
        return collections.Counter(s)
      x = freqs("")
      y = freqs("")
      z = collections.Counter()  # type: typing.Counter[int]
      x - y
      x + y
      x | y
      x & y
      x - z  # unsupported-operands
      x.most_common(1, 2, 3)  # wrong-arg-count
      a = x.most_common()
      b = x.most_common(1)
      c = x.elements()
      d = z.elements()
      e = x.copy()
      f = x | z
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Counter, Iterable, List, Tuple, Union
      collections: module
      typing: module

      a: List[Tuple[str, int]]
      b: List[Tuple[str, int]]
      c: Iterable[str]
      d: Iterable[int]
      e: Counter[str]
      f: Counter[Union[int, str]]

      x: Counter[str]
      y: Counter[str]
      z: Counter[int]

      def freqs(s: str) -> Counter[str]: ...
    """)


class TypingTestPython3Feature(test_base.TargetPython3FeatureTest):
  """Typing tests (Python 3)."""

  def test_namedtuple_item(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        def f() -> NamedTuple("ret", [("x", int), ("y", str)]): ...
      """)
      ty = self.Infer("""
        import foo
        w = foo.f()[-1]
        x = foo.f()[0]
        y = foo.f()[1]
        z = foo.f()[2]  # out of bounds, fall back to the combined element type
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        foo: module
        w: str
        x: int
        y: str
        z: Union[int, str]
      """)

  def test_import_all(self):
    python = [
        "from typing import *  # pytype: disable=not-supported-yet",
    ] + pep484.PEP484_NAMES
    ty = self.Infer("\n".join(python), deep=False)
    self.assertTypesMatchPytd(ty, "")

  def test_callable_func_name(self):
    self.Check("""
      from typing import Any, Callable
      def foo(fn: Callable[[Any], Any]) -> str:
        return fn.__qualname__
    """)

  def test_classvar(self):
    ty = self.Infer("""
      from typing import ClassVar
      class A(object):
        x: ClassVar[int] = 5
      print(A.x + 3)  # make sure using a ClassVar[int] as an int works
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x: int
    """)

  def test_uninitialized_classvar(self):
    ty = self.Infer("""
      from typing import ClassVar
      class A:
        x: ClassVar[int]
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x: int
    """)

  @test_utils.skipBeforePy((3, 7), "typing.OrderedDict is new in 3.7")
  def test_ordered_dict(self):
    self.Check("""
      import collections
      from typing import OrderedDict
      def f(x: OrderedDict[str, int]): ...
      f(collections.OrderedDict(a=0))
    """)

  def test_typed_dict(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing_extensions import TypedDict
        X = TypedDict('X', {'a': int})
      """)
      self.CheckWithErrors("""
        import foo
        from typing import Dict

        def f1(x: Dict[str, int]):
          pass
        def f2(x: Dict[int, str]):
          pass
        def f3(x: foo.X):
          pass

        x = None  # type: foo.X

        f1(x)  # okay
        f2(x)  # wrong-arg-types
        f3({'a': 0})  # okay
        f3({0: 'a'})  # wrong-arg-types
      """, pythonpath=[d.path])


class LiteralTest(test_base.TargetPython3FeatureTest):
  """Tests for typing.Literal in source code."""

  def test_basic(self):
    ty = self.Infer("""
      from typing_extensions import Literal
      x1: Literal["hello"]
      x2: Literal[b"hello"]
      x3: Literal[u"hello"]
      x4: Literal[0]
      x5: Literal[True]
      x6: Literal[None]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Literal
      x1: Literal['hello']
      x2: Literal[b'hello']
      x3: Literal['hello']
      x4: Literal[0]
      x5: Literal[True]
      x6: None
    """)

  def test_union(self):
    ty = self.Infer("""
      from typing_extensions import Literal
      def f(x: Literal["x", "y"]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Literal, Union
      def f(x: Literal['x', 'y']) -> None: ...
    """)

  def test_unnest(self):
    ty = self.Infer("""
      from typing_extensions import Literal
      X = Literal["X"]
      def f(x: Literal[X, Literal[None], Literal[Literal["Y"]]]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Literal, Optional, Union
      X = Literal['X']
      def f(x: Optional[Literal['X', 'Y']]) -> None: ...
    """)

  def test_invalid(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Literal
      x1: Literal[0, ...]  # invalid-annotation[e1]
      x2: Literal[str, 4.2]  # invalid-annotation[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Bad parameter '...' at index 1",
        "e2": (r"Bad parameter 'str' at index 0\n"
               r"\s*Bad parameter 'float' at index 1"),
    })

  def test_variable(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Literal
      x: Literal[0] = 0
      y: Literal[0] = 1  # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"Annotation: Literal\[0\].*Assignment: Literal\[1\]"
    })

  def test_parameter(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Literal
      def f(x: Literal[True]):
        pass
      f(True)
      f(False)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"Expected.*Literal\[True\].*Actual.*Literal\[False\]"
    })

  def test_union_parameter(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Literal
      def f(x: Literal["x", "z"]):
        pass
      f("x")
      f("y")  # wrong-arg-types[e]
      f("z")
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"Expected.*Literal\['x', 'z'\].*Actual.*Literal\['y'\]")
    })

  def test_return(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Literal
      def f() -> Literal["hello"]:
        if __random__:
          return "hello"
        else:
          return "goodbye"  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"Expected.*Literal\['hello'\].*Actual.*Literal\['goodbye'\]"
    })

  def test_match_non_literal(self):
    self.CheckWithErrors("""
      from typing_extensions import Literal
      x: Literal["x"]
      def f(x: str):
        pass
      def g(x: int):
        pass
      f(x)
      g(x)  # wrong-arg-types
    """)

  def test_iterate(self):
    self.Check("""
      from typing_extensions import Literal
      def f(x: Literal["x", "y"]):
        pass
      for x in ["x", "y"]:
        f(x)
    """)


test_base.main(globals(), __name__ == "__main__")
