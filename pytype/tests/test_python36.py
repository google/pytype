"""Python 3.6 tests for Byterun."""

from pytype.tests import test_base


class TestPython36(test_base.BaseTest):
  """Tests for Python 3.6 compatiblity."""

  PYTHON_VERSION = (3, 6)

  def test_variable_annotations(self):
    ty = self.Infer("""
      a : int = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Type

      __annotations__ = ...  # type: Dict[str, Type[int]]
      a = ...  # type: int
    """)

  def test_make_function(self):
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
          print(x)
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

  def test_make_class(self):
    ty = self.Infer("""
      class Thing(tuple):
        def __init__(self, x):
          self.x = x
      def f():
        x = Thing(1)
        x.y = 3
        return x
    """)

    self.assertTypesMatchPytd(ty, """
    from typing import Any
    class Thing(tuple):
      x = ...  # type: Any
      y = ...  # type: int
      def __init__(self, x) -> NoneType: ...
    def f() -> Thing: ...
    """)

  def test_exceptions(self):
    ty = self.Infer("""
      def f():
        try:
          raise ValueError()  # exercise byte_RAISE_VARARGS
        except ValueError as e:
          x = "s"
        finally:  # exercise byte_POP_EXCEPT
          x = 3
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int
    """)

  def test_byte_unpack_ex(self):
    ty = self.Infer("""
      from typing import List
      a, *b, c, d = 1, 2, 3, 4, 5, 6, 7
      e, f, *g, h = "hello world"
      i, *j = 1, 2, 3, "4"
      *k, l = 4, 5, 6
      m, *n, o = [4, 5, "6", None, 7, 8]
      p, *q, r = 4, 5, "6", None, 7, 8
      vars = None # type : List[int]
      s, *t, u = vars
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Optional, Union
      a = ... # type: int
      b = ... # type: List[int]
      c = ... # type: int
      d = ... # type: int
      e = ... # type: str
      f = ... # type: str
      g = ... # type: List[str]
      h = ... # type: str
      i = ... # type: int
      j = ... # type: List[Union[int, str]]
      k = ... # type: List[int]
      l = ... # type: int
      m = ... # type: int
      n = ... # type: List[Optional[Union[int, str]]]
      o = ... # type: int
      p = ... # type: int
      q = ... # type: List[Optional[Union[int, str]]]
      r = ... # type: int
      s = ...  # type: int
      t = ...  # type: List[int]
      u = ...  # type: int
      vars = ...  # type: List[int]
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

  def test_async(self):
    """Test various asyncio features."""
    ty = self.Infer("""
      import asyncio
      def log(x: str):
        return x
      class AsyncContextManager:
        async def __aenter__(self):
          await log("entering context")
        async def __aexit__(self, exc_type, exc, tb):
          await log("exiting context")
      async def my_coroutine(seconds_to_sleep=0.4):
          await asyncio.sleep(seconds_to_sleep)
      async def test_with(x):
        try:
          async with x as y:
            pass
        finally:
          pass
      event_loop = asyncio.get_event_loop()
      try:
        event_loop.run_until_complete(my_coroutine())
      finally:
        event_loop.close()
    """)
    self.assertTypesMatchPytd(ty, """
      import asyncio.events
      asyncio = ...  # type: module
      event_loop = ...  # type: asyncio.events.AbstractEventLoop
      class AsyncContextManager:
          def __aenter__(self) -> None: ...
          def __aexit__(self, exc_type, exc, tb) -> None: ...
      def log(x: str) -> str: ...
      def my_coroutine(seconds_to_sleep = ...) -> None: ...
      def test_with(x) -> None: ...
    """)

  def test_async_iter(self):
    ty = self.Infer("""
      import asyncio
      class AsyncIterable:
        def __aiter__(self):
          return self
        async def __anext__(self):
          data = await self.fetch_data()
          if data:
            return data
          else:
            raise StopAsyncIteration
        async def fetch_data(self):
          pass
      async def iterate(x):
        async for i in x:
          pass
        else:
          pass
      iterate(AsyncIterable())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn, TypeVar
      asyncio = ...  # type: module
      _TAsyncIterable = TypeVar('_TAsyncIterable', bound=AsyncIterable)
      class AsyncIterable:
          def __aiter__(self: _TAsyncIterable) -> _TAsyncIterable: ...
          def __anext__(self) -> NoReturn: ...
          def fetch_data(self) -> None: ...
      def iterate(x) -> None: ...
    """)

  def test_import_shadowed(self):
    """Test that we import modules from pytd/ rather than typeshed."""
    # We can't import the following modules from typeshed; this tests that we
    # import them correctly from our internal pytd/ versions.
    for module in [
        "importlib",
        "re",
        "signal"
    ]:
      ty = self.Infer("import %s" % module)
      expected = "  %s = ...  # type: module" % module
      self.assertTypesMatchPytd(ty, expected)

  def test_iter(self):
    ty = self.Infer("""
      a = next(iter([1, 2, 3]))
      b = next(iter([1, 2, 3]), default = 4)
      c = next(iter([1, 2, 3]), "hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: Union[int, str]
    """)

  def test_create_str(self):
    self.Check("""
      str(b"foo", "utf-8")
    """)

  def test_bytes_constant(self):
    ty = self.Infer("v = b'foo'")
    self.assertTypesMatchPytd(ty, "v = ...  # type: bytes")

  def test_unicode_constant(self):
    ty = self.Infer("v = 'foo\\u00e4'")
    self.assertTypesMatchPytd(ty, "v = ...  # type: str")

  def test_memoryview(self):
    self.Check("""
      v = memoryview(b'abc')
      v.format
      v.itemsize
      v.shape
      v.strides
      v.suboffsets
      v.readonly
      v.ndim
      v[1]
      v[1:]
      98 in v
      [x for x in v]
      len(v)
      v[1] = 98
      v[1:] = b'bc'
    """)

  def test_memoryview_methods(self):
    ty = self.Infer("""
      v1 = memoryview(b'abc')
      v2 = v1.tobytes()
      v3 = v1.tolist()
      v4 = v1.hex()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      v1 = ...  # type: memoryview
      v2 = ...  # type: bytes
      v3 = ...  # type: List[int]
      v4 = ...  # type: str
    """)

  def test_memoryview_contextmanager(self):
    ty = self.Infer("""
      with memoryview(b'abc') as v:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: memoryview
    """)

  def test_super_without_args(self):
    ty = self.Infer("""
      from typing import Callable
      class A(object):
        def m_a(self, x: int, y: int) -> int:
          return x + y
      class B(A):
        def m_b(self, x: int, y: int) -> int:
          return super().m_a(x, y)
      b = B()
      i = b.m_b(1, 2)
      class C(A):
        def m_c(self, x: int, y: int) -> Callable[["C"], int]:
          def f(this: "C") -> int:
            return super().m_a(x, y)
          return f
      def call_m_c(c: C, x: int, y: int) -> int:
        f = c.m_c(x, y)
        return f(c)
      i = call_m_c(C(), i, i + 1)
      def make_my_c() -> C:
        class MyC(C):
          def m_c(self, x: int, y: int) -> Callable[[C], int]:
            def f(this: C) -> int:
              super_f = super().m_c(x, y)
              return super_f(self)
            return f
        return MyC()
      def call_my_c(x: int, y: int) -> int:
        c = make_my_c()
        f = c.m_c(x, y)
        return f(c)
      i = call_my_c(i, i + 2)
      class Outer(object):
        class InnerA(A):
          def m_a(self, x: int, y: int) -> int:
            return 2 * super().m_a(x, y)
      def call_inner(a: Outer.InnerA) -> int:
        return a.m_a(1, 2)
      i = call_inner(Outer.InnerA())
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Callable
    class A(object):
      def m_a(self, x: int, y: int) -> int: ...
    class B(A):
      def m_b(self, x: int, y: int) -> int: ...
    class C(A):
      def m_c(self, x: int, y: int) -> Callable[[C], int]: ...
    def call_m_c(c: C, x: int, y: int) -> int: ...
    def make_my_c() -> C: ...
    def call_my_c(x: int, y: int) -> int: ...
    class Outer(object):
      InnerA = ...  # type: type
    def call_inner(a) -> int
    b = ...  # type: B
    i = ...  # type: int
    """)

  def test_super_without_args_error(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        def m(self):
          pass
      class B(A):
        def m(self):
          def f():
            super().m()
          f()
      def func(x: int):
        super().m()
      """)
    self.assertErrorLogIs(
        errors,
        [(8, "invalid-super-call",
          r".*Missing 'self' argument.*"),
         (11, "invalid-super-call",
          r".*Missing __class__ closure.*")])

  def test_exception_message(self):
    # This attribute was removed in Python 3.
    errors = self.CheckWithErrors("ValueError().message")
    self.assertErrorLogIs(errors, [(1, "attribute-error")])


if __name__ == "__main__":
  test_base.main()
