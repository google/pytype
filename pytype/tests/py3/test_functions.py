"""Test functions."""

from pytype.tests import test_base


class TestClosures(test_base.TargetPython3BasicTest):
  """Tests for closures."""

  def test_error(self):
    errors = self.CheckWithErrors("""\
            def f(x: int):
        def g():
          return x.upper()
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", "upper.*int")])


class TestClosuresPy3(test_base.TargetPython3FeatureTest):
  """Tests for closures in Python 3."""

  def test_if_split_delete_deref(self):
    ty = self.Infer("""\
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
      def f(a: int) -> Optional[str]
    """)

  def test_closures_delete_deref(self):
    _, errors = self.InferWithErrors("""\
      def f():
        x = "hello"
        def g():
          nonlocal x  # force x to be stored in a closure cell
          x = 10
        del x
        return x
    """)
    self.assertErrorLogIs(errors, [(7, "name-error")])

  def test_nonlocal(self):
    ty = self.Infer("""\
      def f():
        x = "hello"
        def g():
          nonlocal x
          x = 10
        g()
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int
    """)

  def test_nonlocal_delete_deref(self):
    _, errors = self.InferWithErrors("""\
      def f():
        x = True
        def g():
          nonlocal x
          del x
        g()
        return x
    """)
    self.assertErrorLogIs(errors, [(7, "name-error")])

  def test_reuse_after_delete_deref(self):
    ty = self.Infer("""\
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
      def f() -> int
    """)


class TestFunctions(test_base.TargetPython3BasicTest):
  """Tests for functions."""

  def test_function_to_callable(self):
    ty = self.Infer("""\
            def f():
        def g1(x: int, y: bool) -> str:
          return "hello world"
        def g2() -> int:
          return 42
        return g1, g2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Tuple
      def f() -> Tuple[Callable[[int, bool], str], Callable[[], int]]
    """)

  def test_function_to_callable_return_only(self):
    ty = self.Infer("""\
            def f():
        def g1(x=None) -> int:
          return 42
        def g2(*args) -> str:
          return "hello world"
        return g1, g2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Tuple
      def f() -> Tuple[Callable[..., int], Callable[..., str]]
    """)

  def test_fake_arguments(self):
    self.Check("""\
      
      class Foo(object):
        def __init__(self, x: int):
          self.y = __any_object__

      foo = Foo("foo")  # pytype: disable=wrong-arg-types
      foo.y  # if __init__ fails, this line throws an error
      """)

  def test_argument_name_conflict(self):
    ty = self.Infer("""
            from typing import Dict
      def f(x: Dict[str, int]):
        x[""] = ""
        return x
      def g(x: Dict[str, int]):
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      def f(x: Dict[str, int]) -> Dict[str, Union[str, int]]: ...
      def g(x: Dict[str, int]) -> Dict[str, int]
    """)

  def test_argument_type_conflict(self):
    ty = self.Infer("""
            from typing import Dict
      def f(x: Dict[str, int], y: Dict[str, int]):
        x[""] = ""
        return x, y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Tuple, Union
      def f(
        x: Dict[str, int], y: Dict[str, int]
      ) -> Tuple[Dict[str, Union[str, int]], Dict[str, int]]: ...
    """)

  def test_typecheck_varargs(self):
    errors = self.CheckWithErrors("""\
            def f(*args: int) -> int:
        return args[0]
      f(*['value'])
      f(1, 'hello', 'world')
      """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types"),
                                   (5, "wrong-arg-types")])

  def test_typecheck_kwargs(self):
    errors = self.CheckWithErrors("""\
            def f(**kwargs: int) -> int:
        return len(kwargs.values())
      f(**{'arg': 'value'})
      f(arg='value', arg2=3)
      """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types"),
                                   (5, "wrong-arg-types")])

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
      def uses_annotations(x: int) -> int
      def uses_pos_defaults(x, y=...) -> ?
      def uses_kw_defaults(x, *myargs, y=...) -> ?
      def uses_kwargs(x, **mykwargs) -> ?
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
      def f(x, *myargs, y) -> ?
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

      def f(a: int = ..., *args, b: int = ..., **kwargs) -> Callable[Any, int]
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

      def f(a = ..., *args, b: int = ..., **kwargs) -> Callable[Any, int]
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
              u, v, x, y=..., z=..., **mykwargs)
    """)

  def test_defaults_and_annotations(self):
    ty = self.Infer("""
      def foo(a, b, c:int, d=0, e=0, f=0, g=0, *myargs,
              u:str, v, x:float=0, y=0, z=0, **mykwargs):
        return 3
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def foo(a, b, c:int, d=..., e=..., f=..., g=..., *myargs,
              u:str, v, x:float=..., y=..., z=..., **mykwargs)
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
      def f() -> int
      class Foo(object):
        def match_method(self) -> Iterator[nothing, ...]
        def match_function(self) -> Iterator[nothing, ...]
        def match_pytd_function(self) -> Iterator[nothing, ...]
        def match_bound_pytd_function(self) -> Iterator[nothing, ...]
        def method(self) -> NoneType
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
      p = ...  # type: List[List[int]]
      q = ...  # type: Set[List[int]]
      r = ...  # type: Tuple[List[int], List[int]]
      s = ...  # type: Dict[str, int]
      x = ...  # type: Dict[str, int]
      y = ...  # type: Dict[str, int]

      def f(**kwargs) -> None: ...
      def g(*args) -> None: ...
      def h(*args, **kwargs) -> None: ...
      def j(a = ..., b = ..., c = ...) -> None: ...
      def k(a, b, c, d, **kwargs) -> None: ...
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


if __name__ == "__main__":
  test_base.main()
