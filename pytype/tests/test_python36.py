"""Python 3.6 tests for Byterun."""

import os

from pytype.tests import test_inference


class TestPython36(test_inference.InferenceTest):
  """Tests for Python 3.6 compatiblity."""

  PYTHON_VERSION = (3, 6)

  def test_variable_annotations(self):
    ty = self.Infer("""
      a : int = 42
    """)
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
    """, deep=True)
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
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(a, b, c, d=..., e=..., f=..., g=..., *myargs,
              u, v, x, y=..., z=..., **mykwargs)
    """)

  def test_defaults_and_annotations(self):
    ty = self.Infer("""
      def foo(a, b, c:int, d=0, e=0, f=0, g=0, *myargs,
              u:str, v, x:float=0, y=0, z=0, **mykwargs):
        return 3
    """)
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
    """, deep=True)

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
    """, deep=True)
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
    """, deep=True)
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

      def f(**kwargs):
        print(kwargs)

      def g(*args):
        print(args)

      def h(*args, **kwargs):
        print(args, kwargs)

      def j(a=1, b=2, c=3):
        print(a, b,c)

      p = [*a, *b]  # BUILD_LIST_UNPACK
      q = {*a, *b}  # BUILD_SET_UNPACK
      r = (*a, *b)  # BUILD_TUPLE_UNPACK
      s = {**c, **d}  # BUILD_MAP_UNPACK
      f(**c, **d, **e)  # BUILD_MAP_UNPACK_WITH_CALL
      g(*a, *b)  # BUILD_TUPLE_UNPACK_WITH_CALL
      h(*a, *b, **c, **d)
      j(**{'a': 1, 'b': 2})  # BUILD_CONST_KEY_MAP
    """, deep=True)
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
      s = ...  # type: Dict[nothing, nothing]

      def f(**kwargs) -> None: ...
      def g(*args) -> None: ...
      def h(*args, **kwargs) -> None: ...
      def j(a = ..., b = ..., c = ...) -> None: ...
    """)

  def test_async(self):
    # TODO(mdemello): Add this test once we fix the typeshed issue:
    #   Couldn't import pyi for 'asyncio'
    #
    # See files under test_data/async*.py
    pass

  def test_reraise(self):
    # Test that we don't crash when trying to reraise a nonexistent exception.
    # (Causes a runtime error when actually run in python 3.6)
    self.assertNoCrash("""
      raise
    """)


if __name__ == "__main__":
  test_inference.main()
