"""Tests for if-splitting."""

from pytype.tests import test_base


class SplitTest(test_base.BaseTest):
  """Tests for if-splitting."""

  def test_hasattr(self):
    ty = self.Infer("""
      class Foo():
        def bar(self):
          pass
      class Baz(Foo):
        def quux(self):
          pass
      def d1(x: Foo): return "y" if hasattr(x, "bar") else 0
      def d2(x: Foo): return "y" if hasattr(x, "unknown") else 0
      def d3(x: Baz): return "y" if hasattr(x, "quux") else 0
      def d4(x: Baz): return "y" if hasattr(x, "bar") else 0
      def a1(x): return "y" if hasattr(x, "bar") else 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Baz(Foo):
        def quux(self) -> None: ...
      class Foo:
        def bar(self) -> None: ...
      def d1(x: Foo) -> str: ...
      def d2(x: Foo) -> int: ...
      def d3(x: Baz) -> str: ...
      def d4(x: Baz) -> str: ...
      def a1(x) -> Union[int, str]: ...
    """)

  def test_union(self):
    self.Check("""
      from typing import Union
      def f(data: str):
        pass
      def as_my_string(data: Union[str, int]):
        if isinstance(data, str):
          f(data)
    """)

  def test_union2(self):
    self.Check("""
      from typing import Union
      class MyString:
        def __init__(self, arg: str):
          self.arg = arg
      def as_my_string(data: Union[str, MyString]) -> MyString:
        if isinstance(data, str):
          result = MyString(data)
        else:
          # data has type MyString
          result = data
        return result
    """)

  def test_load_attr(self):
    self.Check("""
      class A:
        def __init__(self):
          self.initialized = False
          self.data = None
        def f1(self, x: int):
          self.initialized = True
          self.data = x
        def f2(self) -> int:
          if self.initialized:
            return self.data
          else:
            return 0
    """)

  def test_guarding_is(self):
    """Assert that conditions are remembered for is."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is None:
          x = ''
        return x
      """)

  def test_conditions_are_ordered(self):
    """Assert that multiple conditions on a path work."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[NoneType]) -> int:
        if x is not None:
          x = None
        if x is None:
          x = 1  # type: int
        return x
      """)

  def test_guarding_is_not(self):
    """Assert that conditions are remembered for is not."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is not None:
          x = None
        return x
      """)

  def test_guarding_is_not_else(self):
    """Assert that conditions are remembered for else if."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> int:
        if x is None:
          x = 1  # type: int
        else:
          x = 1  # type: int
        return x
      """)

  def test_simple_or(self):
    self.Check("""
      from typing import Optional
      def f(self, x: Optional[str] = None) -> str:
        return x or "foo"
    """)

  def test_or(self):
    self.Check("""
      from typing import Optional
      def f(foo: Optional[int] = None) -> int:
        if foo is None:
          return 1
        return foo
      def g(foo: Optional[int] = None) -> int:
        return foo or 1
      def h(foo: Optional[int] = None) -> int:
        foo = foo or 1
        return foo
      def j(foo: Optional[int] = None) -> int:
        if foo is None:
          foo = 1
        return foo
    """)

  def test_hidden_conflict(self):
    self.Check("""
      import typing
      def f(obj: typing.Union[int, dict, list, float, str, complex]):
        if isinstance(obj, int):
          return
        if isinstance(obj, dict):
          obj.values
    """)

  def test_isinstance_list(self):
    self.Check("""
      from typing import List
      def f(x: List[float]):
        if not isinstance(x, list):
          return float(x)
    """)

  def test_long_signature(self):
    self.Check("""
      from typing import Optional

      class Foo:

        def __init__(
            self, x1: Optional[str] = None, x2: Optional[str] = None,
            x3: Optional[str] = None, x4: Optional[str] = None,
            x5: Optional[str] = None, x6: Optional[str] = None,
            x7: Optional[str] = None, x8: Optional[str] = None,
            x9: Optional[str] = None, credentials: Optional[str] = None):
          if not credentials:
            credentials = ""
          self.credentials = credentials.upper()
    """)

  def test_create_list(self):
    self.Check("""
      from typing import List, Optional
      def _CreateList(opt: Optional[str]) -> List[str]:
        if opt is not None:
          return [opt]
        return ["foo"]
    """)

  def test_create_tuple(self):
    self.Check("""
      from typing import Optional, Tuple
      def _CreateTuple(opt: Optional[str]) -> Tuple[str]:
        if opt is not None:
          return (opt,)
        return ("foo",)
    """)

  def test_closure(self):
    self.Check("""
      from typing import Optional
      def foo(arg: Optional[str]):
        if arg is None:
          raise TypeError()
        def nested():
          print(arg.upper())
    """)

  def test_annotated_closure(self):
    self.Check("""
      from typing import Optional
      def foo(arg: Optional[str]):
        if arg is None:
          raise TypeError()
        def nested() -> None:
          print(arg.upper())
    """)

  def test_iterable_truthiness(self):
    ty = self.Infer("""
      from typing import Iterable
      def f(x: Iterable[int]):
        return 0 if x else ''
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Union
      def f(x: Iterable[int]) -> Union[int, str]: ...
    """)

  def test_custom_container_truthiness(self):
    ty = self.Infer("""
      from typing import Iterable, TypeVar
      T = TypeVar('T')
      class MyIterable(Iterable[T]):
        pass
      def f(x: MyIterable[int]):
        return 0 if x else ''
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, TypeVar, Union
      T = TypeVar('T')
      class MyIterable(Iterable[T]): ...
      def f(x: MyIterable[int]) -> Union[int, str]: ...
    """)

  def test_str_none_eq(self):
    self.Check("""
      from typing import Optional
      def f(x: str, y: Optional[str]) -> str:
        if x == y:
          return y
        return x
    """)

  def test_annotation_class(self):
    ty = self.Infer("""
      from typing import Sequence, Union
      def f(x: Union[int, Sequence[int]]):
        if isinstance(x, Sequence):
          return x[0]
        else:
          return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Sequence, Union
      def f(x: Union[int, Sequence[int]]) -> int: ...
    """)

  def test_isinstance_tuple(self):
    self.Check("""
      from typing import AbstractSet, Sequence, Union

      def yo(collection: Union[AbstractSet[int], Sequence[int]]):
        if isinstance(collection, (Sequence,)):
          return collection.index(5)
        else:
          return len(collection)
    """)

  def test_ordered_dict_value(self):
    self.Check("""
      import collections
      from typing import Iterator, Optional, Tuple

      _DEFINITIONS = {'a': 'b'}

      class Foo:
        def __init__(self):
          self.d = collections.OrderedDict()
        def add(self, k: str, v: Optional[str]):
          if v is None:
            v = _DEFINITIONS[k]
          self.d[k] = v
        def generate(self) -> Iterator[Tuple[str, str]]:
          for k, v in self.d.items():
            yield k, v
    """)


class SplitTestPy3(test_base.BaseTest):
  """Tests for if-splitting in Python 3."""

  def test_isinstance_multiple(self):
    ty = self.Infer("""
      from typing import Union
      def UpperIfString(value: Union[bytes, str, int]):
        if isinstance(value, (bytes, str)):
          return value.upper()
      def ReturnIfNumeric(value: Union[str, int]):
        if isinstance(value, (int, (float, complex))):
          return value
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      def UpperIfString(value: Union[bytes, int, str]) -> Optional[Union[bytes, str]]: ...
      def ReturnIfNumeric(value: Union[str, int]) -> Optional[int]: ...
    """)

  def test_isinstance_aliased(self):
    # Like the previous test, but with isinstance aliased to myisinstance.
    ty = self.Infer("""
      from typing import Union
      myisinstance = isinstance
      def UpperIfString(value: Union[bytes, str, int]):
        if myisinstance(value, (bytes, str)):
          return value.upper()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Optional, Tuple, Union
      def myisinstance(object, class_or_type_or_tuple: Union[Tuple[Union[Tuple[type, ...], type], ...], type]) -> bool: ...
      def UpperIfString(value: Union[bytes, int, str]) -> Optional[Union[bytes, str]]: ...
    """)

  def test_shadow_none(self):
    self.Check("""
      from typing import Optional, Union
      def f(x: Optional[Union[str, bytes]]):
        if x is None:
          x = ''
        return x.upper()
    """)

  def test_override_bool(self):
    ty = self.Infer("""
      class A:
        def __bool__(self):
          return __random__

      x = A() and True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A:
        def __bool__(self) -> bool: ...
      x: Union[A, bool]
    """)

  def test_ordered_dict_list_value(self):
    self.Check("""
      import collections
      from typing import List, Optional

      class A:
        def __init__(self):
          self._arg_dict = collections.OrderedDict()
        def Set(self, arg_name: str, arg_value: Optional[str] = None):
          if arg_value is not None:
            self._arg_dict[arg_name] = [arg_value]
        def Get(self) -> List[str]:
          arg_list: List[str] = []
          for key, value in self._arg_dict.items():
            arg_list.append(key)
            if __random__:
              arg_list.append('')
            else:
              arg_list.extend(value)
          return arg_list
        def __str__(self) -> str:
          return ''.join(self.Get())

      class B:
        def Build(self) -> List[str]:
          a = A()
          return a.Get()
    """)


if __name__ == "__main__":
  test_base.main()
