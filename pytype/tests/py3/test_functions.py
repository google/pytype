"""Test functions."""

from pytype import file_utils
from pytype.tests import test_base


class TestClosures(test_base.TargetPython3BasicTest):
  """Tests for closures."""

  def test_error(self):
    errors = self.CheckWithErrors("""
      def f(x: int):
        def g():
          return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})


class TestClosuresPy3(test_base.TargetPython3FeatureTest):
  """Tests for closures in Python 3."""

  def test_if_split_delete_deref(self):
    ty = self.Infer("""
      def f(a: int):
        x = "hello"
        def g():
          nonlocal x
          x = 42
        if a:
          g()
        else:
          return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      def f(a: int) -> Optional[str]: ...
    """)

  def test_closures_delete_deref(self):
    self.InferWithErrors("""
      def f():
        x = "hello"
        def g():
          nonlocal x  # force x to be stored in a closure cell
          x = 10
        del x
        return x  # name-error
    """)

  def test_nonlocal(self):
    ty = self.Infer("""
      def f():
        x = "hello"
        def g():
          nonlocal x
          x = 10
        g()
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_nonlocal_delete_deref(self):
    self.InferWithErrors("""
      def f():
        x = True
        def g():
          nonlocal x
          del x
        g()
        return x  # name-error
    """)

  def test_reuse_after_delete_deref(self):
    ty = self.Infer("""
      def f():
        x = True
        def g():
          nonlocal x
          del x
        g()
        x = 42
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_closure_annotations(self):
    errors = self.CheckWithErrors("""
      def f():
        a = 1
        def g(x: int) -> int:
          a  # makes sure g is a closure
          return "hello"  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_filter_before_delete(self):
    # TODO(b/117463644): Remove the disable on line 7.
    self.CheckWithErrors("""
      from typing import Optional
      def f(x: Optional[str]):
        if x is None:
          raise TypeError()
        def nested():
          nonlocal x
          print(x.upper())  # pytype: disable=name-error
          del x
        nested()
        return x  # name-error
    """)


class PreciseReturnTest(test_base.TargetPython3BasicTest):
  """Tests for --precise-return."""

  def setUp(self):
    super(PreciseReturnTest, self).setUp()
    self.options.tweak(precise_return=True)

  def test_interpreter_return(self):
    ty, errors = self.InferWithErrors("""
      def f(x: str) -> str:
        return x
      x = f(0)  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: str) -> str: ...
      x: str
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_interpreter_unknown_return(self):
    ty, errors = self.InferWithErrors("""
      def f(x: str):
        return x
      x = f(0)  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x: str) -> str: ...
      x: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_interpreter_overload(self):
    ty, errors = self.InferWithErrors("""
      from typing import overload
      @overload
      def f(x: str) -> str: ...
      def f(x):
        return x
      x = f(0)  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f(x: str) -> str: ...
      x: str
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})


class TestCheckDefaults(test_base.TargetPython3FeatureTest):
  """Tests for checking parameter defaults against annotations."""

  def test_basic(self):
    errors = self.CheckWithErrors("""
      def f(x: int = ''):  # annotation-type-mismatch[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_typevar(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar('T')
      def f(x: T = 0, y: T = ''):  # annotation-type-mismatch[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_instance_method(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def f(self, x: int = ''):  # annotation-type-mismatch[e]
          pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_kwonly_arg(self):
    errors = self.CheckWithErrors("""
      def f(*, x: int = ''):  # annotation-type-mismatch[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_multiple_errors(self):
    errors = self.CheckWithErrors("""
      def f(x: int = '', y: str = 0):  # annotation-type-mismatch[e1]  # annotation-type-mismatch[e2]
        pass
    """)
    self.assertErrorRegexes(errors, {"e1": r"Annotation: int.*Assignment: str",
                                     "e2": r"Annotation: str.*Assignment: int"})

  def test_ellipsis(self):
    self.CheckWithErrors("""
      def f(x: int = ...):  # annotation-type-mismatch
        return x
    """)

  def test_overload_ellipsis(self):
    self.Check("""
      from typing import overload

      @overload
      def f(x: int = ...): ...
      @overload
      def f(x: str = ...): ...

      def f(x):
        return x
    """)


class TestCheckParameterAssignment(test_base.TargetPython3BasicTest):
  """Tests for checking assignments to annotated parameters."""

  def test_basic(self):
    errors = self.CheckWithErrors("""
      def f(x: int):
        x = ''  # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_typevar(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar('T')
      def f(x: T, y: T):
        x = 0  # annotation-type-mismatch[e]
      f('', '')
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Annotation: str.*Assignment: int.*Called from.*line 5"})


class TestFunctions(test_base.TargetPython3BasicTest):
  """Tests for functions."""

  def test_function_to_callable(self):
    ty = self.Infer("""
      def f():
        def g1(x: int, y: bool) -> str:
          return "hello world"
        def g2() -> int:
          return 42
        return g1, g2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Tuple
      def f() -> Tuple[Callable[[int, bool], str], Callable[[], int]]: ...
    """)

  def test_function_to_callable_return_only(self):
    ty = self.Infer("""
      def f():
        def g1(x=None) -> int:
          return 42
        def g2(*args) -> str:
          return "hello world"
        return g1, g2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Tuple
      def f() -> Tuple[Callable[..., int], Callable[..., str]]: ...
    """)

  def test_fake_arguments(self):
    self.Check("""

      class Foo(object):
        def __init__(self, x: int):
          self.y = __any_object__

      foo = Foo("foo")  # pytype: disable=wrong-arg-types
      foo.y  # if __init__ fails, this line throws an error
      """)

  def test_argument_name_conflict(self):
    ty, _ = self.InferWithErrors("""
      from typing import Dict
      def f(x: Dict[str, int]):
        x[""] = ""  # container-type-mismatch
        return x
      def g(x: Dict[str, int]):
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      def f(x: Dict[str, int]) -> Dict[str, Union[str, int]]: ...
      def g(x: Dict[str, int]) -> Dict[str, int]: ...
    """)

  def test_argument_type_conflict(self):
    ty, _ = self.InferWithErrors("""
      from typing import Dict
      def f(x: Dict[str, int], y: Dict[str, int]):
        x[""] = ""  # container-type-mismatch
        return x, y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Tuple, Union
      def f(
        x: Dict[str, int], y: Dict[str, int]
      ) -> Tuple[Dict[str, Union[str, int]], Dict[str, int]]: ...
    """)

  def test_typecheck_varargs(self):
    self.CheckWithErrors("""
      def f(*args: int) -> int:
        return args[0]
      f(*['value'])  # wrong-arg-types
      f(1, 'hello', 'world')  # wrong-arg-types
      """)

  def test_typecheck_kwargs(self):
    self.CheckWithErrors("""
      def f(**kwargs: int) -> int:
        return len(kwargs.values())
      f(**{'arg': 'value'})  # wrong-arg-types
      f(arg='value', arg2=3)  # wrong-arg-types
    """)

  def test_pass_func_to_complex_func(self):
    # This test gets an unsolvable binding added to the variable containing the
    # lambda by making the call to 'f' trigger a TooComplexError.
    self.Check("""
      from typing import Optional
      def f(x1, x2: Optional[str], x3, x4, x5, x6, x7, x8, x9, xA, xB):
        pass
      def g(x2: Optional[str] = None, x3: Optional[str] = None,
            x4: Optional[str] = None, x5: Optional[str] = None,
            x6: Optional[str] = None, x7: Optional[str] = None,
            x8: Optional[str] = None, x9: Optional[str] = None,
            xA: Optional[str] = None, xB: Optional[str] = None):
        f(lambda: None, x2, x3, x4, x5, x6, x7, x8, x9, xA, xB)
    """)

  def test_type_param_args(self):
    ty = self.Infer("""
      from typing import Any, Type, TypeVar
      T = TypeVar('T')
      def cast(typ: Type[T], val: Any) -> T:
        return val
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar

      T = TypeVar('T')

      def cast(typ: Type[T], val) -> T: ...
    """)

  def test_varargs(self):
    self.Check("""
      def foo(x: str, y: bytes, *z: int):
        pass
      foo('abc', b'def', 123)
      foo('abc', b'def', 123, 456, 789)
      foo('abc', b'def', *[123, 456, 789])
      foo('abc', *[b'def', 123, 456, 789])
      foo(*['abc', b'def', 123, 456, 789])
      def bar(*y: int):
        foo('abc', b'def', *y)
    """)

  def text_varargs_errors(self):
    errors = self.CheckWithErrors("""
      def foo(x: str, *y: int):
        pass
      foo(*[1, 2, 3])  # wrong-arg-types[e1]
      def bar(*z: int):
        foo(*z)  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"str.*int", "e2": r"str.*int"})

  def test_varargs_in_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: int, *args): ...
      """)
      self.Check("""
        import foo
        def g(*args):
          foo.f(42, *args)
      """, pythonpath=[d.path])

  def test_varargs_in_pyi_error(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: int, *args): ...
      """)
      errors = self.CheckWithErrors("""
        import foo
        def g(*args):
          foo.f("", *args)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_function_type(self):
    self.Check("""
      import types
      def f(x: types.FunctionType):
        pass
      f(lambda: None)
    """)

  def test_bad_function_match(self):
    # Tests matching a function against abstract.Empty.
    self.CheckWithErrors("""
      def f():
        pass
      def g(x: [][0]):
        pass
      g(f)  # wrong-arg-types
    """)

  def test_noreturn(self):
    self.Check("""
      from typing import Any, Callable, NoReturn

      def f(x: int) -> NoReturn:
        raise NotImplementedError()

      def g(x: Callable[[int], Any]):
        pass

      g(f)
    """)


class TestFunctionsPython3Feature(test_base.TargetPython3FeatureTest):
  """Tests for functions."""

  def test_make_function(self):
    src = """
      def uses_annotations(x: int) -> int:
        i, j = 3, 4
        return i

      def uses_pos_defaults(x, y=1):
        i, j = 3, 4
        return __any_object__

      def uses_kw_defaults(x, *myargs, y=1):
        i, j = 3, 4
        return __any_object__

      def uses_kwargs(x, **mykwargs):
        i, j = 3, 4
        return __any_object__
    """
    output = """
      from typing import Any
      def uses_annotations(x: int) -> int: ...
      def uses_pos_defaults(x, y=...) -> Any: ...
      def uses_kw_defaults(x, *myargs, y=...) -> Any: ...
      def uses_kwargs(x, **mykwargs) -> Any: ...
    """
    self.assertTypesMatchPytd(
        self.Infer(src, deep=False), output)
    self.assertTypesMatchPytd(
        self.Infer(src, deep=True), output)

  def test_make_function2(self):
    ty = self.Infer("""
      def f(x, *myargs, y):
        return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x, *myargs, y) -> Any: ...
    """)

  def test_make_function3(self):
    ty = self.Infer("""
      def f(a = 2, *args, b:int = 1, **kwargs):
        x = 0
        def g(i:int = 3) -> int:
          print(x)
        return g

      y = f(2)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable

      def f(a: int = ..., *args, b: int = ..., **kwargs) -> Callable[Any, int]: ...
      def y(i: int = ...) -> int: ...
    """)

  def test_make_function_deep(self):
    ty = self.Infer("""
      def f(a = 2, *args, b:int = 1, **kwargs):
        x = 0
        def g(i:int = 3) -> int:
          return x + i
        return g

      y = f(2)
    """)
    # Does not infer a:int when deep=True.
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable

      def f(a = ..., *args, b: int = ..., **kwargs) -> Callable[Any, int]: ...
      def y(i: int = ...) -> int: ...
    """)

  def test_defaults(self):
    ty = self.Infer("""
      def foo(a, b, c, d=0, e=0, f=0, g=0, *myargs,
              u, v, x, y=0, z=0, **mykwargs):
        return 3
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(a, b, c, d=..., e=..., f=..., g=..., *myargs,
              u, v, x, y=..., z=..., **mykwargs): ...
    """)

  def test_defaults_and_annotations(self):
    ty = self.Infer("""
      def foo(a, b, c:int, d=0, e=0, f=0, g=0, *myargs,
              u:str, v, x:float=0, y=0, z=0, **mykwargs):
        return 3
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(a, b, c:int, d=..., e=..., f=..., g=..., *myargs,
              u:str, v, x:float=..., y=..., z=..., **mykwargs): ...
    """)

  def test_namedtuple_defaults(self):
    self.Check("""
      from typing import NamedTuple
      class Foo(NamedTuple):
        field: int
      Foo.__new__.__defaults__ = ((),) * len(Foo._fields)
   """)

  def test_matching_functions(self):
    ty = self.Infer("""
      def f():
        return 3

      class Foo(object):
        def match_method(self):
          return map(self.method, [])
        def match_function(self):
          return map(f, [])
        def match_pytd_function(self):
          return map(map, [])
        def match_bound_pytd_function(self):
          return map({}.keys, [])
        def method(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      def f() -> int: ...
      class Foo(object):
        def match_method(self) -> Iterator[nothing, ...]: ...
        def match_function(self) -> Iterator[nothing, ...]: ...
        def match_pytd_function(self) -> Iterator[nothing, ...]: ...
        def match_bound_pytd_function(self) -> Iterator[nothing, ...]: ...
        def method(self) -> NoneType: ...
    """)

  def test_build_with_unpack(self):
    ty = self.Infer("""
      a = [1,2,3,4]
      b = [1,2,3,4]
      c = {'1':2, '3':4}
      d = {'5':6, '7':8}
      e = {'9':10, 'B':12}
      # Test merging two dicts into an args dict for k
      x = {'a': 1, 'c': 2}
      y = {'b': 1, 'd': 2}

      def f(**kwargs):
        print(kwargs)

      def g(*args):
        print(args)

      def h(*args, **kwargs):
        print(args, kwargs)

      def j(a=1, b=2, c=3):
        print(a, b,c)

      def k(a, b, c, d, **kwargs):
        print(a, b, c, d, kwargs)

      p = [*a, *b]  # BUILD_LIST_UNPACK
      q = {*a, *b}  # BUILD_SET_UNPACK
      r = (*a, *b)  # BUILD_TUPLE_UNPACK
      s = {**c, **d}  # BUILD_MAP_UNPACK
      f(**c, **d, **e)  # BUILD_MAP_UNPACK_WITH_CALL
      g(*a, *b)  # BUILD_TUPLE_UNPACK_WITH_CALL
      h(*a, *b, **c, **d)
      j(**{'a': 1, 'b': 2})  # BUILD_CONST_KEY_MAP
      k(**x, **y, **e)  # BUILD_MAP_UNPACK_WITH_CALL
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Set, Tuple

      a = ...  # type: List[int]
      b = ...  # type: List[int]
      c = ...  # type: Dict[str, int]
      d = ...  # type: Dict[str, int]
      e = ...  # type: Dict[str, int]
      p = ...  # type: List[int]
      q = ...  # type: Set[int]
      r = ...  # type: Tuple[int, int, int, int, int, int, int, int]
      s = ...  # type: Dict[str, int]
      x = ...  # type: Dict[str, int]
      y = ...  # type: Dict[str, int]

      def f(**kwargs) -> None: ...
      def g(*args) -> None: ...
      def h(*args, **kwargs) -> None: ...
      def j(a = ..., b = ..., c = ...) -> None: ...
      def k(a, b, c, d, **kwargs) -> None: ...
    """)

  def test_unpack_str(self):
    ty = self.Infer("""
      s1 = "abc"
      s2 = "def"
      tup = (*s1, *s2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      s1 = ...  # type: str
      s2 = ...  # type: str
      tup = ...  # type: Tuple[str, str, str, str, str, str]
    """)

  def test_unpack_nonliteral(self):
    ty = self.Infer("""
      def f(x, **kwargs):
        return kwargs['y']
      def g(**kwargs):
        return f(x=10, **kwargs)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any

      def f(x, **kwargs) -> Any: ...
      def g(**kwargs) -> Any: ...
    """)

  def test_unpack_multiple_bindings(self):
    ty = self.Infer("""
      if __random__:
        x = {'a': 1, 'c': 2}
      else:
        x = {'a': '1', 'c': '2'}
      if __random__:
        y = {'b': 1, 'd': 2}
      else:
        y = {'b': b'1', 'd': b'2'}
      z = {**x, **y}
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, TypeVar, Union

      x = ...  # type: Dict[str, Union[str, int]]
      y = ...  # type: Dict[str, Union[bytes, int]]
      z = ...  # type: Dict[str, Union[bytes, int, str]]
    """)

  def test_kwonly(self):
    self.Check("""
      from typing import Optional
      def foo(x: int, *, z: Optional[int] = None) -> None:
        pass

      foo(1, z=5)
    """)

  def test_varargs_with_kwonly(self):
    self.Check("""
      def foo(x: int, *args: int, z: int) -> None:
        pass

      foo(1, 2, z=5)
    """)

  def test_varargs_with_missing_kwonly(self):
    errors = self.CheckWithErrors("""
      def foo(x: int, *args: int, z: int) -> None:
        pass

      foo(1, 2, 5)  # missing-parameter[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"\bz\b"})

  def test_multiple_varargs_packs(self):
    self.Check("""
      from typing import Tuple
      def foo1(*x: int):
        pass
      def foo2(x: str, y: bytes, *z: int):
        pass
      foo1(*[1, 2, 3], *[4, 5, 6])
      foo2('abc', b'def', *[1, 2, 3], *[4, 5, 6])
      def bar(y: Tuple[int], *z: int):
        foo1(*y, *z)
        foo2('abc', b'def', *y, *z)
    """)

  def text_multiple_varargs_packs_errors(self):
    errors = self.CheckWithErrors("""
      def foo(x: str, *y: int):
        pass
      foo(*[1, 2, 3], *[4, 5, 6])  # wrong-arg-types[e1]
      def bar(*z: int):
        foo(*z, *z)  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"str.*int", "e2": r"str.*int"})


test_base.main(globals(), __name__ == "__main__")
