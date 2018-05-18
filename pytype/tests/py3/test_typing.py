"""Tests for typing.py."""

from pytype import utils
from pytype.tests import test_base


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
    _, errors = self.InferWithErrors(self._TEMPLATE % locals())
    self.assertNotEqual(0, len(errors))

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
    self.Check("""\
            from typing import Generator
      def f() -> Generator[int]:
        for i in range(3):
          yield i
    """)

  def test_type(self):
    ty, errors = self.InferWithErrors("""\
            from typing import Type
      class Foo:
        x = 1
      def f1(foo: Type[Foo]):
        return foo.x
      def f2(foo: Type[Foo]):
        return foo.y  # bad
      def f3(foo: Type[Foo]):
        return foo.mro()
      def f4(foo: Type[Foo]):
        return foo()
      v1 = f1(Foo)
      v2 = f2(Foo)
      v3 = f3(Foo)
      v4 = f4(Foo)
    """)
    self.assertErrorLogIs(errors, [(8, "attribute-error", r"y.*Foo")])
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type
      class Foo:
        x = ...  # type: int
      def f1(foo: Type[Foo]) -> int
      def f2(foo: Type[Foo]) -> Any
      def f3(foo: Type[Foo]) -> list
      def f4(foo: Type[Foo]) -> Foo
      v1 = ...  # type: int
      v2 = ...  # type: Any
      v3 = ...  # type: list
      v4 = ...  # type: Foo
    """)

  def test_type_union(self):
    _, errors = self.InferWithErrors("""\
            from typing import Type, Union
      class Foo:
        bar = ...  # type: int
      def f1(x: Type[Union[int, Foo]]):
        # Currently not an error, since attributes on Unions are retrieved
        # differently.  See get_attribute() in attribute.py.
        x.bar
      def f2(x: Union[Type[int], Type[Foo]]):
        x.bar
        f1(x)
      def f3(x: Type[Union[int, Foo]]):
        f1(x)
        f2(x)
    """)
    self.assertErrorLogIs(errors, [(10, "attribute-error", "bar.*int")])

  def test_use_type_alias(self):
    with utils.Tempdir() as d:
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
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable
        def f() -> Callable
      """)
      self.Check("""\
                from typing import Callable
        import foo
        def f() -> Callable:
          return foo.f()
        def g() -> Callable:
          return int
      """, pythonpath=[d.path])

  def test_callable_parameters(self):
    ty, errors = self.InferWithErrors("""\
            from typing import Any, Callable

      # The below are all valid.
      def f1(x: Callable[[int, str], bool]): ...
      def f2(x: Callable[..., bool]): ...
      def f3(x: Callable[[], bool]): ...

      def g1(x: Callable[int, bool]): ...  # bad: _ARGS not a list
      lst = [int] if __random__ else [str]
      def g2(x: Callable[lst, bool]): ...  # bad: _ARGS ambiguous
      def g3(x: Callable[[], bool or str]): ...  # bad: _RET ambiguous
      def g4(x: Callable[[int or str], bool]): ...  # bad: _ARGS[0] ambiguous
      lst = None  # type: list[int]
      def g5(x: Callable[lst, bool]): ...  # bad: _ARGS not a constant
      def g6(x: Callable[[42], bool]): ...  # bad: _ARGS[0] not a type
      def g7(x: Callable[[], bool, int]): ...  # bad: Too many params
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
       def g6(x) -> None: ...
       def g7(x: Callable[[], bool]) -> None: ...
    """)
    self.assertErrorLogIs(errors, [
        (9, "invalid-annotation", r"'int'.*must be a list of argument types"),
        (11, "invalid-annotation", r"\[int\] or \[str\].*Must be constant"),
        (12, "invalid-annotation", r"bool or str.*Must be constant"),
        (13, "invalid-annotation", r"int or str.*Must be constant"),
        (15, "invalid-annotation",
         r"instance of List\[int\].*Must be constant"),
        (16, "invalid-annotation", r"instance of int"),
        (17, "invalid-annotation", r"Callable.*Expected 2.*got 3"),])

  def test_callable_bad_args(self):
    ty, errors = self.InferWithErrors("""\
            from typing import Callable
      lst1 = [str]
      lst1[0] = int
      def g1(x: Callable[lst1, bool]): ...  # line 5
      lst2 = [str]
      while __random__:
        lst2.append(int)
      def g2(x: Callable[lst2, bool]): ...  # line 9
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
    self.assertErrorLogIs(errors, [
        (5, "invalid-annotation",
         r"instance of List\[Type\[Union\[int, str\]\]\].*Must be constant"),
        (9, "invalid-annotation",
         r"instance of List\[Type\[Union\[int, str\]\]\].*Must be constant"),])

  def test_generics(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Dict
        K = TypeVar("K")
        V = TypeVar("V")
        class CustomDict(Dict[K, V]): ...
      """)
      self.Check("""\
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
        def f(x: typing.Generator[int]): pass
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
    ty, errors = self.InferWithErrors("""\
            from typing import Callable
      f = ...  # type: Callable[[int], str]
      v1 = f()
      v2 = f(True)  # ok
      v3 = f(42.0)
      v4 = f(1, 2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      f = ...  # type: Callable[[int], str]
      v1 = ...  # type: Any
      v2 = ...  # type: str
      v3 = ...  # type: Any
      v4 = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-count", "1.*0"),
                                   (6, "wrong-arg-types", "int.*float"),
                                   (7, "wrong-arg-count", "1.*2")])

  def test_callable_call_with_type_parameters(self):
    ty, errors = self.InferWithErrors("""\
            from typing import Callable, TypeVar
      T = TypeVar("T")
      def f(g: Callable[[T, T], T], y, z):
        return g(y, z)
      v1 = f(__any_object__, 42, 3.14)  # ok
      v2 = f(__any_object__, 42, "hello world")
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, TypeVar
      T = TypeVar("T")
      def f(g: Callable[[T, T], T], y, z): ...
      v1 = ...  # type: int or float
      v2 = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"int.*str")])

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
    _, errors = self.InferWithErrors("""\
            from typing import Callable
      f = ...  # type: Callable[[], int]
      f(x=3)
      f(*(42,))
      f(**{"x": "hello", "y": "world"})
      f(*(42,), **{"hello": "world"})
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-keyword-args", r"x"),
                                   (5, "wrong-arg-count", r"0.*1"),
                                   (6, "wrong-keyword-args", r"x, y"),
                                   (7, "wrong-keyword-args", r"hello")])

  def test_callable_attribute(self):
    self.Check("""\
            from typing import Any, Callable
      def foo(fn: Callable[[Any], Any]):
        fn.foo # pytype: disable=attribute-error
    """)

  def test_callable_func_name(self):
    self.Check("""\
            from typing import Any, Callable
      def foo(fn: Callable[[Any], Any]) -> str:
        return fn.func_name
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
      MyAnyType = ... # Any
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
        return i
      def func3(s: MyStr) -> MyStr:
        return s
      func1(123)
      func3(MyStr(123))
    """)
    self.assertErrorLogIs(
        errors,
        [(9, "bad-return-type",
          r"Expected: MyInt\nActually returned: int"),
         (12, "wrong-arg-types",
          r".*Expected: \(i: MyInt\)\nActually passed: \(i: int\)"),
         (13, "wrong-arg-types",
          r".*Expected:.*val: str\)\nActually passed:.*val: int\)"),])

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
    errors = self.CheckWithErrors("""\
            from typing import Union
      MyUnion = Union[int, ...]
    """)
    self.assertErrorLogIs(
        errors, [(3, "invalid-annotation", r"Ellipsis.*index 1.*Union")])

  def test_list_ellipsis(self):
    errors = self.CheckWithErrors("""\
            from typing import List
      MyList = List[int, ...]
    """)
    self.assertErrorLogIs(
        errors, [(3, "invalid-annotation", r"Ellipsis.*index 1.*List")])

  def test_multiple_ellipses(self):
    errors = self.CheckWithErrors("""\
            from typing import Union
      MyUnion = Union[..., int, ..., str, ...]
    """)
    self.assertErrorLogIs(errors, [
        (3, "invalid-annotation", r"Ellipsis.*indices 0, 2, 4.*Union")])

  def test_bad_tuple_ellipsis(self):
    errors = self.CheckWithErrors("""\
            from typing import Tuple
      MyTuple1 = Tuple[..., ...]
      MyTuple2 = Tuple[...]
    """)
    self.assertErrorLogIs(
        errors, [(3, "invalid-annotation", r"Ellipsis.*index 0.*Tuple"),
                 (4, "invalid-annotation", r"Ellipsis.*index 0.*Tuple")])

  def test_bad_callable_ellipsis(self):
    errors = self.CheckWithErrors("""\
            from typing import Callable
      MyCallable1 = Callable[..., ...]
      MyCallable2 = Callable[[int], ...]
      MyCallable3 = Callable[[...], int]
    """)
    self.assertErrorLogIs(
        errors, [(3, "invalid-annotation", r"Ellipsis.*index 1.*Callable"),
                 (4, "invalid-annotation", r"Ellipsis.*index 1.*Callable"),
                 (5, "invalid-annotation", r"Ellipsis.*index 0.*list")])


class TypingTestPython3Feature(test_base.TargetPython3FeatureTest):

  def test_namedtuple_item(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        def f() -> NamedTuple("ret", [("x", int), ("y", str)])
      """)
      ty = self.Infer("""
        import foo
        w = foo.f()[-1]
        x = foo.f()[0]
        y = foo.f()[1]
        z = foo.f()[2]  # out of bounds, fall back to the combined element type
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        w = ...  # type: str
        x = ...  # type: int
        y = ...  # type: str
        z = ...  # type: int or str
      """)


test_base.main(globals(), __name__ == "__main__")
