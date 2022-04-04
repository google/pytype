"""Tests for the typing.NamedTuple overlay."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class NamedTupleTest(test_base.BaseTest):
  """Tests for the typing.NamedTuple overlay."""

  def test_make(self):
    self.CheckWithErrors("""
        import typing
        A = typing.NamedTuple("A", [("b", str), ("c", str)])
        a = A._make(["hello", "world"])
        b = A._make(["hello", "world"], len=len)
        c = A._make([1, 2])  # wrong-arg-types
        d = A._make(A)  # wrong-arg-types
        def f(e: A) -> None: pass
        f(a)
        """)

  def test_subclass(self):
    self.CheckWithErrors("""
        import typing
        A = typing.NamedTuple("A", [("b", str), ("c", int)])
        class B(A):
          def __new__(cls, b: str, c: int=1):
            return super(B, cls).__new__(cls, b, c)
        x = B("hello", 2)
        y = B("world")
        def take_a(a: A) -> None: pass
        def take_b(b: B) -> None: pass
        take_a(x)
        take_b(x)
        take_b(y)
        take_b(A("", 0))  # wrong-arg-types
        B()  # missing-parameter
        # _make and _replace should return instances of the subclass.
        take_b(B._make(["hello", 0]))
        take_b(y._replace(b="world"))
        """)

  def test_callable_attribute(self):
    ty = self.Infer("""
      from typing import Callable, NamedTuple
      X = NamedTuple("X", [("f", Callable)])
      def foo(x: X):
        return x.f
    """)
    self.assertMultiLineEqual(pytd_utils.Print(ty.Lookup("foo")),
                              "def foo(x: X) -> Callable: ...")

  def test_bare_union_attribute(self):
    ty, errors = self.InferWithErrors("""
      from typing import NamedTuple, Union
      X = NamedTuple("X", [("x", Union)])  # invalid-annotation[e]
      def foo(x: X):
        return x.x
    """)
    self.assertMultiLineEqual(pytd_utils.Print(ty.Lookup("foo")),
                              "def foo(x: X) -> Any: ...")
    self.assertErrorRegexes(errors, {"e": r"Union.*x"})


class NamedTupleTestPy3(test_base.BaseTest):
  """Tests for the typing.NamedTuple overlay in Python 3."""

  def test_basic_namedtuple(self):
    ty = self.Infer("""
      import typing
      X = typing.NamedTuple("X", [("a", int), ("b", str)])
      x = X(1, "hello")
      a = x.a
      b = x.b
      """)
    self.assertTypesMatchPytd(
        ty,
        """
        import collections
        import typing
        from typing import Callable, Iterable, Sized, Tuple, Type, TypeVar, Union
        x = ...  # type: X
        a = ...  # type: int
        b = ...  # type: str
        _Tnamedtuple_X_a_b = TypeVar('_Tnamedtuple_X_a_b', bound=X)
        class X(Tuple[int, str]):
          __slots__ = ["a", "b"]
          __dict__: collections.OrderedDict[str, Union[int, str]]
          _field_defaults: collections.OrderedDict[str, Union[int, str]]
          _field_types: collections.OrderedDict[str, type]
          _fields: Tuple[str, str]
          a: int
          b: str
          def __getnewargs__(self) -> Tuple[int, str]: ...
          def __getstate__(self) -> None: ...
          def __init__(self, *args, **kwargs) -> None: ...
          def __new__(
              cls: Type[_Tnamedtuple_X_a_b], a: int, b: str
          ) -> _Tnamedtuple_X_a_b: ...
          def _asdict(self) -> collections.OrderedDict[str,
            Union[int, str]]: ...
          @classmethod
          def _make(
              cls: Type[_Tnamedtuple_X_a_b],
              iterable: Iterable[Union[int, str]], new = ...,
              len: Callable[[Sized], int] = ...) -> _Tnamedtuple_X_a_b: ...
          def _replace(
              self: _Tnamedtuple_X_a_b, **kwds: Union[int, str]
          ) -> _Tnamedtuple_X_a_b: ...
          """)

  def test_union_attribute(self):
    ty = self.Infer("""
      from typing import NamedTuple, Union
      X = NamedTuple("X", [("x", Union[bytes, str])])
      def foo(x: X):
        return x.x
    """)
    self.assertMultiLineEqual(pytd_utils.Print(ty.Lookup("foo")),
                              "def foo(x: X) -> Union[bytes, str]: ...")

  @test_utils.skipFromPy((3, 8), "error line number changed in 3.8")
  def test_bad_call_pre_38(self):
    _, errorlog = self.InferWithErrors("""
        from typing import NamedTuple
        E2 = NamedTuple('Employee2', [('name', str), ('id', int)],
                        birth=str, gender=bool)  # invalid-namedtuple-arg[e1]  # wrong-keyword-args[e2]
    """)
    self.assertErrorRegexes(errorlog, {
        "e1": r"Either list of fields or keywords.*",
        "e2": r".*(birth, gender).*NamedTuple"})

  @test_utils.skipBeforePy((3, 8), "error line number changed in 3.8")
  def test_bad_call(self):
    _, errorlog = self.InferWithErrors("""
        from typing import NamedTuple
        E2 = NamedTuple('Employee2', [('name', str), ('id', int)],  # invalid-namedtuple-arg[e1]  # wrong-keyword-args[e2]
                        birth=str, gender=bool)
    """)
    self.assertErrorRegexes(errorlog, {
        "e1": r"Either list of fields or keywords.*",
        "e2": r".*(birth, gender).*NamedTuple"})

  def test_bad_attribute(self):
    _, errorlog = self.InferWithErrors("""
        from typing import NamedTuple

        class SubCls(NamedTuple):  # not-writable[e]
          def __init__(self):
            pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r".*'__init__'.*[SubCls]"})

  def test_bad_arg_count(self):
    _, errorlog = self.InferWithErrors("""
        from typing import NamedTuple

        class SubCls(NamedTuple):
          a: int
          b: int

        cls1 = SubCls(5)  # missing-parameter[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Missing.*'b'.*__new__"})

  def test_bad_arg_name(self):
    self.InferWithErrors("""
        from typing import NamedTuple

        class SubCls(NamedTuple):  # invalid-namedtuple-arg
          _a: int
          b: int

        cls1 = SubCls(5)
    """)

  def test_namedtuple_class(self):
    self.Check("""
      from typing import NamedTuple

      class SubNamedTuple(NamedTuple):
        a: int
        b: str ="123"
        c: int = 123

        def __repr__(self) -> str:
          return "__repr__"

        def func():
          pass

      tuple1 = SubNamedTuple(5)
      tuple2 = SubNamedTuple(5, "123")
      tuple3 = SubNamedTuple(5, "123", 123)

      E1 = NamedTuple('Employee1', name=str, id=int)
      E2 = NamedTuple('Employee2', [('name', str), ('id', int)])
      """)

  def test_baseclass(self):
    ty = self.Infer("""
      from typing import NamedTuple

      class baseClass:
        x=5
        y=6

      class SubNamedTuple(baseClass, NamedTuple):
        a: int
      """)
    self.assertTypesMatchPytd(
        ty,
        """
        import collections
        from typing import Callable, Iterable, Sized, Tuple, Type, TypeVar

        _Tnamedtuple_SubNamedTuple_a = TypeVar(
            '_Tnamedtuple_SubNamedTuple_a', bound=SubNamedTuple)

        class SubNamedTuple(baseClass, Tuple[int]):
            __slots__ = ["a"]
            __dict__ = ...  # type: collections.OrderedDict[str, int]
            _field_defaults = ...  # type: collections.OrderedDict[str, int]
            _field_types = ...  # type: collections.OrderedDict[str, type]
            _fields = ...  # type: Tuple[str]
            a = ...  # type: int
            def __getnewargs__(self) -> Tuple[int]: ...
            def __getstate__(self) -> None: ...
            def __init__(self, *args, **kwargs) -> None: ...
            def __new__(
                cls: Type[_Tnamedtuple_SubNamedTuple_a], a: int
            ) -> _Tnamedtuple_SubNamedTuple_a: ...
            def _asdict(self) -> collections.OrderedDict[str, int]: ...
            @classmethod
            def _make(
                cls: Type[_Tnamedtuple_SubNamedTuple_a],
                iterable: Iterable[int], new = ...,
                len: Callable[[Sized], int] = ...
            ) -> _Tnamedtuple_SubNamedTuple_a: ...
            def _replace(self: _Tnamedtuple_SubNamedTuple_a,
                         **kwds: int) -> _Tnamedtuple_SubNamedTuple_a: ...

        class baseClass:
            x = ...  # type: int
            y = ...  # type: int
        """)

  def test_fields(self):
    self.Check("""
      from typing import NamedTuple
      class X(NamedTuple):
        a: str
        b: int

      v = X("answer", 42)
      a = v.a  # type: str
      b = v.b  # type: int
      """)

  def test_field_wrong_type(self):
    self.CheckWithErrors("""
      from typing import NamedTuple
      class X(NamedTuple):
        a: str
        b: int

      v = X("answer", 42)
      a_int = v.a  # type: int  # annotation-type-mismatch
      """)

  def test_unpacking(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        class X(NamedTuple):
          a: str
          b: int
      """)
      ty, unused_errorlog = self.InferWithErrors("""
        import foo
        v = None  # type: foo.X
        a, b = v
      """, deep=False, pythonpath=[d.path])

      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        v = ...  # type: foo.X
        a = ...  # type: str
        b = ...  # type: int
      """)

  def test_bad_unpacking(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        class X(NamedTuple):
          a: str
          b: int
      """)
      self.CheckWithErrors("""
        import foo
        v = None  # type: foo.X
        _, _, too_many = v  # bad-unpacking
        too_few, = v  # bad-unpacking
        a: float
        b: str
        a, b = v  # annotation-type-mismatch # annotation-type-mismatch
      """, deep=False, pythonpath=[d.path])

  def test_is_tuple_type_and_superclasses(self):
    """Test that a NamedTuple (function syntax) behaves like a tuple."""
    self.Check("""
      from typing import MutableSequence, NamedTuple, Sequence, Tuple, Union
      class X(NamedTuple):
        a: int
        b: str

      a = X(1, "2")
      a_tuple = a  # type: tuple
      a_typing_tuple = a  # type: Tuple[int, str]
      a_typing_tuple_elipses = a  # type: Tuple[Union[int, str], ...]
      a_sequence = a  # type: Sequence[Union[int, str]]
      a_iter = iter(a)  # type: tupleiterator[Union[int, str]]

      a_first = a[0]  # type: int
      a_second = a[1]  # type: str
      a_first_next = next(iter(a))  # We don't know the type through the iter() function
    """)

  def test_is_not_incorrect_types(self):
    self.CheckWithErrors("""
      from typing import MutableSequence, NamedTuple, Sequence, Tuple, Union
      class X(NamedTuple):
        a: int
        b: str

      x = X(1, "2")

      x_wrong_tuple_types = x  # type: Tuple[str, str]  # annotation-type-mismatch
      x_not_a_list = x  # type: list  # annotation-type-mismatch
      x_not_a_mutable_seq = x  # type: MutableSequence[Union[int, str]]  # annotation-type-mismatch
      x_first_wrong_element_type = x[0]  # type: str  # annotation-type-mismatch
    """)

  def test_meets_protocol(self):
    self.Check("""
      from typing import NamedTuple, Protocol
      class X(NamedTuple):
        a: int
        b: str

      class IntAndStrHolderVars(Protocol):
        a: int
        b: str

      class IntAndStrHolderProperty(Protocol):
        @property
        def a(self) -> int:
          ...

        @property
        def b(self) -> str:
          ...

      a = X(1, "2")
      a_vars_protocol: IntAndStrHolderVars = a
      a_property_protocol: IntAndStrHolderProperty = a
    """)

  def test_does_not_meet_mismatching_protocol(self):
    self.CheckWithErrors("""
      from typing import NamedTuple, Protocol
      class X(NamedTuple):
        a: int
        b: str

      class DualStrHolder(Protocol):
        a: str
        b: str

      class IntAndStrHolderVars_Alt(Protocol):
        the_number: int
        the_string: str

      class IntStrIntHolder(Protocol):
        a: int
        b: str
        c: int

      a = X(1, "2")
      a_wrong_types: DualStrHolder = a  # annotation-type-mismatch
      a_wrong_names: IntAndStrHolderVars_Alt = a  # annotation-type-mismatch
      a_too_many: IntStrIntHolder = a  # annotation-type-mismatch
    """)

  def test_generated_members(self):
    ty = self.Infer("""
      from typing import NamedTuple
      class X(NamedTuple):
        a: int
        b: str
      """)
    self.assertTypesMatchPytd(ty, (
        """
        import collections
        from typing import (
            Callable, Iterable, Sized, Tuple, Type, TypeVar, Union)

        _Tnamedtuple_X_a_b = TypeVar('_Tnamedtuple_X_a_b', bound=X)

        class X(Tuple[int, str]):
            __slots__ = ["a", "b"]
            __dict__: collections.OrderedDict[str, Union[int, str]]
            _field_defaults: collections.OrderedDict[str, Union[int, str]]
            _field_types: collections.OrderedDict[str, type]
            _fields: Tuple[str, str]
            a: int
            b: str
            def __getnewargs__(self) -> Tuple[int, str]: ...
            def __getstate__(self) -> None: ...
            def __init__(self, *args, **kwargs) -> None: ...
            def __new__(
                cls: Type[_Tnamedtuple_X_a_b], a: int, b: str
            ) -> _Tnamedtuple_X_a_b: ...
            def _asdict(
                self) -> collections.OrderedDict[str, Union[int, str]]: ...
            @classmethod
            def _make(
                cls: Type[_Tnamedtuple_X_a_b],
                iterable: Iterable[Union[int, str]], new = ...,
                len: Callable[[Sized], int] = ...) -> _Tnamedtuple_X_a_b: ...
            def _replace(
                self: _Tnamedtuple_X_a_b, **kwds: Union[int, str]
            ) -> _Tnamedtuple_X_a_b: ...
        """))

  def test_namedtuple_with_defaults(self):
    ty = self.Infer("""
      from typing import NamedTuple

      class SubNamedTuple(NamedTuple):
        a: int
        b: str ="123"
        c: int = 123

        def __repr__(self) -> str:
          return "__repr__"

        def func():
          pass

      X = SubNamedTuple(1, "aaa", 222)
      a = X.a
      b = X.b
      c = X.c
      f = X.func

      Y = SubNamedTuple(1)
      a2 = Y.a
      b2 = Y.b
      c2 = Y.c
      """)
    self.assertTypesMatchPytd(
        ty,
        """
        import collections
        from typing import (
            Callable, Iterable, Sized, Tuple, Type, TypeVar, Union)

        X: SubNamedTuple
        a: int
        b: str
        c: int

        Y: SubNamedTuple
        a2: int
        b2: str
        c2: int

        _Tnamedtuple_SubNamedTuple_a_b_c = TypeVar(
            '_Tnamedtuple_SubNamedTuple_a_b_c', bound=SubNamedTuple)

        class SubNamedTuple(Tuple[int, str, int]):
            __slots__ = ["a", "b", "c"]
            __dict__: collections.OrderedDict[str, Union[int, str]]
            _field_defaults: collections.OrderedDict[str, Union[int, str]]
            _field_types: collections.OrderedDict[str, type]
            _fields: Tuple[str, str, str]
            a: int
            b: str
            c: int
            def __getnewargs__(self) -> Tuple[int, str, int]: ...
            def __getstate__(self) -> None: ...
            def __init__(self, *args, **kwargs) -> None: ...
            def __new__(
                cls: Type[_Tnamedtuple_SubNamedTuple_a_b_c], a: int,
                b: str = ..., c: int = ...
            ) -> _Tnamedtuple_SubNamedTuple_a_b_c: ...
            def __repr__(self) -> str: ...
            def _asdict(self) -> collections.OrderedDict[str, Union[int, str]]:
              ...
            @classmethod
            def _make(
                cls: Type[_Tnamedtuple_SubNamedTuple_a_b_c],
                iterable: Iterable[Union[int, str]], new = ...,
                len: Callable[[Sized], int] = ...
            ) -> _Tnamedtuple_SubNamedTuple_a_b_c: ...
            def _replace(
                self: _Tnamedtuple_SubNamedTuple_a_b_c, **kwds: Union[int, str]
            ) -> _Tnamedtuple_SubNamedTuple_a_b_c: ...
            def func() -> None: ...

        def f() -> None: ...
        """)

  def test_bad_default(self):
    errors = self.CheckWithErrors("""
      from typing import NamedTuple
      class Foo(NamedTuple):
        x: str = 0  # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: str.*Assignment: int"})

  def test_nested_namedtuple(self):
    # Guard against a crash when hitting max depth (b/162619036)
    self.assertNoCrash(self.Check, """
      from typing import NamedTuple

      def foo() -> None:
        class A(NamedTuple):
          x: int

      def bar():
        foo()
    """)

  def test_generic_namedtuple(self):
    ty = self.Infer("""
      from typing import Callable, Generic, NamedTuple, TypeVar

      def _int_identity(x: int) -> int:
        return x

      T = TypeVar('T')

      class Foo(NamedTuple, Generic[T]):
        x: T
        y: Callable[[T], T]
      foo_int = Foo(x=0, y=_int_identity)
      x_out = foo_int.x
      y_out = foo_int.y
      y_call_out = foo_int.y(2)
      foo_str: Foo[str] = Foo(x="hi", y=__any_object__)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
        from typing import (Any, Callable, Generic, Iterable, Sized, Tuple,
                            Type, TypeVar, Union)


        def _int_identity(x: int) -> int: ...

        T = TypeVar("T")

        foo_int = ...  # type: Foo[int]
        x_out = ...  # type: int
        y_out = ...  # type: Callable[[int], int]
        y_call_out = ...  # type: int
        foo_str = ...  # type: Foo[str]

        _Tnamedtuple_Foo_x_y = TypeVar('_Tnamedtuple_Foo_x_y', bound=Foo)

        class Foo(Tuple[T, Callable[[T], T]], Generic[T]):
          __slots__ = ["x", "y"]
          # TODO(csyoung): Figure out why these two fields' value types are
          # being collapsed to Any.
          # The Union of field types is preserved elsewhere.
          # This only seems to happen when Generic gets involved;
          # without Generic, these get typed correctly.
          __dict__: collections.OrderedDict[str, Any]
          _field_defaults: collections.OrderedDict[str, Any]
          _field_types: collections.OrderedDict[str, type]
          _fields: Tuple[str, str]
          x: T
          y: Callable[[T], T]
          def __getnewargs__(self) -> Tuple[T, Callable[[T], T]]: ...
          def __getstate__(self) -> None: ...
          def __init__(self, *args, **kwargs) -> None: ...
          def __new__(
              cls: Type[_Tnamedtuple_Foo_x_y], x: T, y: Callable[[T], T]
          ) -> _Tnamedtuple_Foo_x_y: ...
          def _asdict(
              self
          ) -> collections.OrderedDict[str, Union[Callable[[T], T], T]]: ...
          @classmethod
          def _make(
              cls: Type[_Tnamedtuple_Foo_x_y],
              iterable: Iterable[Union[Callable[[T], T], T]],
              new = ..., len: Callable[[Sized], int] = ...
          ) -> _Tnamedtuple_Foo_x_y: ...
          def _replace(
              self: _Tnamedtuple_Foo_x_y, **kwds: Union[Callable[[T], T], T]
          ) -> _Tnamedtuple_Foo_x_y: ...
      """)

  def test_bad_typevar(self):
    self.CheckWithErrors("""
      from typing import Generic, NamedTuple, TypeVar
      T = TypeVar('T')
      class Foo(NamedTuple):
        x: T  # invalid-annotation
    """)

  def test_generic_callable(self):
    self.Check("""
      from typing import Callable, NamedTuple, TypeVar
      T = TypeVar('T')
      class Foo(NamedTuple):
        f: Callable[[T], T]
      assert_type(Foo(f=__any_object__).f(''), str)
    """)

  def test_reingest(self):
    foo_ty = self.Infer("""
      from typing import Callable, Generic, NamedTuple, TypeVar
      T = TypeVar('T')
      class Foo(NamedTuple, Generic[T]):
        x: T
      class Bar(NamedTuple):
        x: Callable[[T], T]
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.Check("""
        import foo
        assert_type(foo.Foo(x=0).x, int)
        assert_type(foo.Bar(x=__any_object__).x(0), int)
      """, pythonpath=[d.path])

  def test_recursive_tuple(self):
    """Regression test for a recursive tuple containing a namedtuple."""
    # See b/227506303 for details
    self.Check("""
      from typing import Any, NamedTuple

      A = NamedTuple("A", [("x", Any), ("y", Any)])

      def decorator(fn):
        def wrapper(*args, **kwargs):
          return fn(*args, **kwargs)
        return wrapper

      @decorator
      def g(x, y):
        nt = A(1, 2)
        x = x, nt
        y = y, nt
        def h():
          max(x, y)
    """)


if __name__ == "__main__":
  test_base.main()
