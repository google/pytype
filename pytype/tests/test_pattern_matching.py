"""Tests for structural pattern matching (PEP-634)."""

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy((3, 10), "New syntax in 3.10")
class MatchTest(test_base.BaseTest):
  """Test match statement for builtin datatypes."""

  def test_basic(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case 1:
            return 'a'
          case 2:
            return 10
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int | str | None: ...
    """)

  def test_default(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case 1:
            return 'a'
          case 2:
            return 10
          case _:
            return 20
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int | str: ...
    """)

  def test_sequence1(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case [a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x) -> Any: ...
    """)

  def test_sequence2(self):
    ty = self.Infer("""
      def f(x: int):
        match x:
          case [a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> None: ...
    """)

  def test_list1(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case [a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int | None: ...
    """)

  def test_list2(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case [a]:
            return a
          case [a, *rest]:
            return rest
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int | list[int] | None: ...
    """)

  @test_base.skip("Exhaustiveness checks not implemented")
  def test_list3(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case []:
            return 0
          case [a]:
            return a
          case [a, *rest]:
            return rest
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int | list[int]: ...
    """)

  def test_list4(self):
    ty = self.Infer("""
      def f(x: list[int]):
        match x:
          case [*all]:
            return 0
          case _:
            return '1'
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int]) -> int: ...
    """)

  def test_tuple(self):
    ty = self.Infer("""
      def f(x: tuple[int, str]):
        match x:
          case [a, b]:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: tuple[int, str]) -> str: ...
    """)

  def test_tuple2(self):
    ty = self.Infer("""
      def f(x: tuple[int, str]):
        match x:
          case [a, b, *rest]:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: tuple[int, str]) -> str: ...
    """)

  def test_map1(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case {'x': a}:
            return 0
          case {'y': b}:
            return '1'
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int | str | None : ...
    """)

  def test_map2(self):
    ty = self.Infer("""
      def f(x):
        match x:
          case {'x': a}:
            return a
          case {'y': b}:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x) -> Any: ...
    """)

  def test_map3(self):
    ty = self.Infer("""
      def f():
        x = {'x': 1, 'y': '2'}
        match x:
          case {'x': a}:
            return a
          case {'y': b}:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_map_starstar(self):
    ty = self.Infer("""
      def f():
        x = {'x': 1, 'y': '2'}
        match x:
          case {'x': a, **rest}:
            return rest
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> dict[str, str]: ...
    """)

  def test_map_annotation(self):
    ty = self.Infer("""
     def f(x: dict[str, int]):
        match x:
          case {'x': a}:
            return a
          case {'y': b}:
            return b
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: dict[str, int]) -> int | None: ...
    """)

  def test_overloaded_function(self):
    self.Check("""
      from typing import overload
      class A:
        pass
      class B:
        pass
      @overload
      def f(x: A) -> B: ...
      @overload
      def f(x: B) -> A: ...
      @overload
      def f(x: tuple[A, B]) -> B: ...
      def f(x):
        match x:
          case A():
            return B()
          case B():
            return A()
          case A() as a, B() as b:
            return f(a)
          case _:
            raise KeyError(key)
    """)

  def test_overloaded_function_kwargs_call(self):
    self.Check("""
      from typing import overload
      class A:
        pass
      class B:
        pass
      @overload
      def f(x: A) -> B: ...
      @overload
      def f(x: B) -> A: ...
      @overload
      def f(x: tuple[A, B]) -> B: ...
      def f(x):
        match x:
          case A():
            return B()
          case B():
            return A()
          case A() as a, B() as b:
            return f(**{'x': a})
          case _:
            raise KeyError(key)
    """)

  def test_overloaded_method(self):
    self.Check("""
      from typing import overload
      class A:
        pass
      class B:
        pass
      class C:
        @overload
        def f(self, x: A) -> B: ...
        @overload
        def f(self, x: B) -> A: ...
        @overload
        def f(self, x: tuple[A, B]) -> B: ...
        def f(self, x):
          match x:
            case A():
              return B()
            case B():
              return A()
            case A() as a, B() as b:
              return self.f(a)
            case _:
              raise KeyError(key)
    """)


@test_utils.skipBeforePy((3, 10), "New syntax in 3.10")
class MatchClassTest(test_base.BaseTest):
  """Test match statement for classes."""

  def test_unknown(self):
    ty = self.Infer("""
      class A:
        x: int = ...
        y: str = ...
      def f(x):
        match x:
          case A(x=a, y=b):
            return b
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x: int
        y: str

      def f(x) -> int | str: ...
    """)

  def test_annotated(self):
    ty = self.Infer("""
      class A:
        x: int = ...
        y: str = ...
      def f(x: A):
        match x:
          case A(x=a, y=b):
            return b
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x: int
        y: str

      def f(x: A) -> str: ...
    """)

  def test_instance1(self):
    ty = self.Infer("""
      class A:
        def __init__(self, x: int, y: str):
          self.x = x
          self.y = y

      def f():
        x = A(1, '2')
        match x:
          case A(x=a, y=b):
            return b
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x: int
        y: str
        def __init__(self, x: int, y: str) -> None: ...

      def f() -> str: ...
    """)

  def test_instance2(self):
    ty = self.Infer("""
      class A:
        def __init__(self, x):
          self.x = x
      def f(x):
        match x:
          case A(x=a):
            return a
          case _:
            return False
      a = f(A(10))
      b = f(A('20'))
      c = f('foo')
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A:
        x: Any
        def __init__(self, x) -> None: ...

      def f(x) -> Any: ...
      a: int
      b: str
      c: bool
    """)

  def test_type_narrowing(self):
    self.Check("""
      class A: pass
      class B: pass

      def f(x: A | B):
        match x:
          case A():
            assert_type(x, A)
          case B():
            assert_type(x, B)
          case _:
            # This branch will not be entered
            assert_type(1, str)
    """)

  def test_type_narrowing_union(self):
    self.Check("""
      class A: pass
      class B: pass
      class C: pass
      class D: pass

      def f(x: A | B | C | D):
        match x:
          case A() | B():
            assert_type(x, A | B)
          case C():
            assert_type(x, C)
          case _:
            assert_type(x, D)
    """)

  def test_type_narrowing_mixed(self):
    self.Check("""
      class A: pass
      class B: pass
      class C: pass
      class D: pass

      def f(x: A | B | C | int | bool):
        match x:
          case A():
            assert_type(x, A)
          case 1:
            # Note that we do not do positive type narrowing here
            assert_type(x, B | C | int | bool)
          case B():
            assert_type(x, B)
          case True:
            assert_type(x, C | int | bool)
          case C():
            assert_type(x, C)
          case D():
            # This branch will not be entered
            assert_type(1, str)
          case _:
            assert_type(x, int | bool)
    """)

  def test_posargs(self):
    ty = self.Infer("""
      class A:
        __match_args__ = ('x', 'y')
        x: int = ...
        y: str = ...
      def f(x: A):
        match x:
          case A(x, y):
            return y
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(
        ty, """
      class A:
        __match_args__: tuple[str, str]
        x: int
        y: str

      def f(x: A) -> str: ...
    """)

  def test_posargs_no_match_args(self):
    ty, err = self.InferWithErrors("""
      class A:
        x: int = ...
        y: str = ...
      def f(x: A):
        match x:
          case A(x, y):  # match-error[e]
            return y
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(
        ty, """
      class A:
        x: int
        y: str

      def f(x: A) -> int: ...
    """)
    self.assertErrorSequences(err, {"e": ["A()", "accepts 0", "2 given"]})

  def test_posargs_too_many_params(self):
    err = self.CheckWithErrors("""
      class A:
        __match_args__ = ('x', 'y')
        x: int = ...
        y: str = ...
      def f(x: A):
        match x:
          case A(x, y, z):  # match-error[e]
            return y
          case _:
            return 42
    """)
    self.assertErrorSequences(err, {"e": ["A()", "accepts 2", "3 given"]})

  def test_posargs_invalid_match_args_entry(self):
    ty = self.Infer("""
      class A:
        __match_args__ = ('x', 'a')
        x: int = ...
        y: str = ...
      def f(x: A):
        match x:
          case A(x, y):
            return y
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(
        ty, """
      class A:
        __match_args__: tuple[str, str]
        x: int
        y: str

      def f(x: A) -> int: ...
    """)

  def test_posargs_and_kwargs(self):
    ty = self.Infer("""
      class A:
        __match_args__ = ('x', 'y')
        x: int = ...
        y: str = ...
        z: bool = ...
      def f(x: A):
        match x:
          case A(x, y, z=z):
            return z
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(
        ty, """
      class A:
        __match_args__: tuple[str, str]
        x: int
        y: str
        z: bool

      def f(x: A) -> bool: ...
    """)

  def test_builtin(self):
    ty = self.Infer("""
      def f(x: str):
        match x:
          case str(y):
            return y
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: str) -> str: ...
    """)

  def test_builtin_with_union(self):
    ty = self.Infer("""
      def f(x: int | str):
        match x:
          case str(y):
            return y
          case int(y):
            return str(y)
          case dict(y):
            return y
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: int | str) -> str: ...
    """)

  def test_builtin_kwargs(self):
    ty = self.Infer("""
      def f(x: str):
        match x:
          case str(y, kwarg=z):
            return y
          case _:
            return 42
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: str) -> int: ...
    """)

  def test_builtin_too_many_params(self):
    err = self.CheckWithErrors("""
      def f(x: str):
        match x:
          case str(x, y):  # match-error[e]
            return y
          case _:
            return 42
    """)
    self.assertErrorSequences(err, {"e": ["str()", "accepts 1", "2 given"]})

  def test_collections_abc(self):
    self.Check("""
      from collections import abc

      def match_seq(obj):
        match obj:
          case abc.Sequence():
            return True
          case _:
            return None

      x = match_seq([1, 2])
      assert_type(x, bool)
      y = match_seq(1)
      assert_type(y, None)
    """)

  def test_collections_abc_posarg(self):
    self.CheckWithErrors("""
      from collections import abc

      def match_seq(obj):
        match obj:
          case abc.Sequence(x):  # match-error
            return True
          case _:
            return False
    """)

  def test_error(self):
    ty, _ = self.InferWithErrors("""
      def f(x):
        match x:
          case error():  # name-error
            return 0
          case _:
            return None
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int | None: ...
    """)

  def test_nested_function(self):
    ty = self.Infer("""
      class A:
        x: int
      class B:
        y: str
      class C:
        z: bytes
      def f(arg: A | B | C):
        def g():
          match arg:
            case A():
              return arg.x
            case B():
              return arg.y
            case _:
              return arg.z
        return g()
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x: int
      class B:
        y: str
      class C:
        z: bytes
      def f(arg: A | B | C) -> int | str | bytes: ...
    """)

  def test_instance_attribute(self):
    self.Check("""
      class Foo:
        def __init__(self):
          self.x = 42
        @property
        def y(self):
          return self.x - 1
      def f(x: Foo | str):
        match x:
          case Foo():
            return x.y
          case str():
            return int(x)
    """)


@test_utils.skipBeforePy((3, 10), "New syntax in 3.10")
class MatchFeaturesTest(test_base.BaseTest):
  """Test various pattern matching features."""

  def test_or_pattern(self):
    ty = self.Infer("""
      def f(x: tuple[int, str]):
        match x:
          case [a, 'x'] | [2, a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: tuple[int, str]) -> int | str | None: ...
    """)

  def test_as_pattern(self):
    ty = self.Infer("""
      def f(x: list[int | str]):
        match x:
          case [('x' | 1) as a]:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: list[int | str]) -> int | str | None: ...
    """)

  def test_guard_literal(self):
    ty = self.Infer("""
      def f():
        x = 5
        match x:
          case a if a > 0:
            return a
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_guard_type(self):
    ty = self.Infer("""
      def f(x: int | str):
        match x:
          case a if isinstance(a, int):
            return a
          case _:
            return 0
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: int | str) -> int: ...
    """)


@test_utils.skipBeforePy((3, 10), "New syntax in 3.10")
class MatchCoverageTest(test_base.BaseTest):
  """Test exhaustive coverage of enums."""

  def test_exhaustive(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color):
        match x:
          case Color.RED:
            return 10
          case (Color.GREEN |
              Color.BLUE):
            return 'a'
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color) -> int | str: ...
    """)

  def test_default(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color):
        match x:
          case Color.RED:
            return 10
          case _:
            return 'a'
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color) -> int | str: ...
    """)

  def test_default_with_capture(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color):
        match x:
          case Color.RED:
            return 10
          case _ as foo:
            return foo
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color) -> int | Color: ...
    """)

  def test_nonexhaustive(self):
    ty, err = self.InferWithErrors("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color):
        match x:  # incomplete-match[e]
          case Color.RED:
            return 10
          case Color.GREEN:
            return 'a'
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type, Union

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color) -> int | str | None: ...
    """)
    self.assertErrorSequences(err, {"e": ["missing", "cases", "Color.BLUE"]})

  def test_unused_after_exhaustive(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color):
        match x:
          case Color.RED:
            return 10
          case (Color.GREEN |
              Color.BLUE):
            return 20
          case _:
            return 'a'
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color) -> int: ...
    """)

  def test_nested(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color, y: Color):
        match x:
          case Color.RED:
            return 10
          case (Color.GREEN |
              Color.BLUE):
            match y:
              case Color.RED:
                return 10
              case Color.GREEN:
                return 'a'
              case _:
                return None
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color, y: Color) -> int | str | None: ...
    """)

  def test_multiple(self):
    ty, _ = self.InferWithErrors("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color, y: Color):
        match x:  # incomplete-match
          case Color.RED:
            return 10
          case Color.GREEN:
            return 20
        match y:
          case Color.RED:
            return 'a'
          case Color.GREEN | Color.BLUE:
            return 'b'
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color, y: Color) -> int | str: ...
    """)

  def test_enum_with_methods(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

        def red(self):
          return self.RED

      def f(x: Color):
        match x:
          case Color.RED:
            return 10
          case (Color.GREEN |
              Color.BLUE):
            return 'a'
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type, TypeVar

      Enum: Type[enum.Enum]
      _TColor = TypeVar('_TColor', bound=Color)

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

          def red(self: _TColor) -> _TColor: ...

      def f(x: Color) -> int | str: ...
    """)

  def test_redundant(self):
    ty, _ = self.InferWithErrors("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color, y: Color):
        match x:
          case Color.RED:
            return 10
          case Color.GREEN:
            return 20
          case Color.RED:  # redundant-match
            return '10'
          case Color.BLUE:
            return 20
    """)
    self.assertTypesMatchPytd(
        ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color, y: Color) -> int: ...
    """)

  def test_incomplete_and_redundant(self):
    ty, _ = self.InferWithErrors("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color, y: Color):
        match x:  # incomplete-match
          case Color.RED:
            return 10
          case Color.GREEN:
            return 20
          case Color.RED:  # redundant-match
            return '10'
    """)
    self.assertTypesMatchPytd(
        ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color, y: Color) -> int | None: ...
    """)

  def test_partially_redundant(self):
    err = self.CheckWithErrors("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color, y: Color):
        match x:
          case Color.RED:
            return 10
          case Color.GREEN:
            return 20
          case Color.RED | Color.BLUE:  # redundant-match[e]
            return '10'
    """)
    self.assertErrorSequences(err, {"e": ["already been covered", "Color.RED"]})

  def test_complete_match_no_caching(self):
    self.Check("""
      import enum
      @enum.unique
      class Coin(str, enum.Enum):
        HEADS: str = 'heads'
        TAILS: str = 'tails'
      class Foo:
        def foo(self, c: Coin) -> None:
          match c:
            case Coin.HEADS:
              self.bar()
            case Coin.TAILS:
              pass
        def bar(self) -> None:
          pass
    """, skip_repeat_calls=False)

  def test_pytd_enum_basic(self):
    with self.DepTree([("foo.pyi", """
      import enum

      class A(enum.Enum):
        BASIC = 1
        ADVANCED = 2
    """)]):
      self.Check("""
        import foo

        def f(v: foo.A):
          match v:
            case foo.A.BASIC:
              return 'basic'
            case foo.A.ADVANCED:
              return 'control'
            case _:
              return 'unknown'
      """)

  def test_pytd_enum_redundant(self):
    with self.DepTree([("foo.pyi", """
      import enum

      class A(enum.Enum):
        BASIC = 1
        ADVANCED = 2
    """)]):
      self.CheckWithErrors("""
        import foo

        def f(v: foo.A):
          match v:
            case foo.A.BASIC:
              return 'basic'
            case foo.A.BASIC:  # redundant-match
              return 'even more basic'
            case _:
              return 'unknown'
      """)

  def test_pytd_enum_incomplete(self):
    with self.DepTree([("foo.pyi", """
      import enum

      class A(enum.Enum):
        BASIC = 1
        ADVANCED = 2
    """)]):
      self.CheckWithErrors("""
        import foo

        def f(v: foo.A):
          match v:  # incomplete-match
            case foo.A.BASIC:
              return 'basic'
      """)

  def call_function_with_match(self):
    ty = self.Infer("""
      from enum import Enum
      class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def f(x: Color):
        match x:
          case Color.RED:
            return 10
          case (Color.GREEN |
              Color.BLUE):
            return 'a'

      a = f(Color.RED)
    """)
    self.assertTypesMatchPytd(ty, """
      import enum
      from typing import Type

      Enum: Type[enum.Enum]

      a: int | str

      class Color(enum.Enum):
          BLUE: int
          GREEN: int
          RED: int

      def f(x: Color) -> int | str: ...
    """)

  def call_method_from_init(self):
    """Regression test for a crash."""

    # Caused a crash when trying to access EnumTracker.default_value before it
    # had been set.

    self.Check("""
      import enum

      class A(enum.Enum):
        RED = 1
        BLUE = 2
        GREEN = 3


      class Foo:
        def __init__(self):
          self.a = self.f(A.RED)

        def f(self, x: A):
          match x:
            case A.RED:
              return 42
            case _:
              raise ValueError('foo')
    """)

  def test_optimized_bytecode_out_of_order(self):
    """Regression test for a bug resulting from compiler optimisations."""
    # Compier optimisations that inline code can put blocks out of order, which
    # could potentially interfere with our checks for the end of a match block.

    self.Check("""
      import enum

      class Color(enum.Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

      def test(color: Color):
        match color:
          case Color.RED:
            print("I see red!")
          case Color.GREEN:
            print("Grass is green")
          case Color.BLUE:
            print("I'm feeling the blues :(")
        # This line compiles to a return statement after every case branch.
        return color
    """)


if __name__ == "__main__":
  test_base.main()
