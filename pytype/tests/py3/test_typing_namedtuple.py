"""Tests for the typing.NamedTuple overlay."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class NamedTupleTest(test_base.TargetPython3BasicTest):
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


class NamedTupleTestPy3(test_base.TargetPython3FeatureTest):
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
        from typing import Callable, Iterable, Sized, Tuple, Type, TypeVar, Union
        typing = ...  # type: module
        x = ...  # type: X
        a = ...  # type: int
        b = ...  # type: str
        _TX = TypeVar('_TX', bound=X)
        class X(tuple):
          __slots__ = ["a", "b"]
          __dict__ = ...  # type: collections.OrderedDict[str, Union[int, str]]
          _field_defaults = ...  # type: collections.OrderedDict[str, Union[int, str]]
          _field_types = ...  # type: collections.OrderedDict[str, type]
          _fields = ...  # type: Tuple[str, str]
          a = ...  # type: int
          b = ...  # type: str
          def __getnewargs__(self) -> Tuple[int, str]: ...
          def __getstate__(self) -> None: ...
          def __init__(self, *args, **kwargs) -> None: ...
          def __new__(cls: Type[_TX], a: int, b: str) -> _TX: ...
          def _asdict(self) -> collections.OrderedDict[str,
            Union[int, str]]: ...
          @classmethod
          def _make(cls: Type[_TX], iterable: Iterable[Union[int, str]],
            new = ..., len: Callable[[Sized], int] = ...) -> _TX: ...
          def _replace(self: _TX, **kwds: Union[int, str]) -> _TX: ...
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

      class baseClass(object):
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

        _TSubNamedTuple = TypeVar('_TSubNamedTuple', bound=SubNamedTuple)

        class SubNamedTuple(tuple):
            __slots__ = ["a"]
            __dict__ = ...  # type: collections.OrderedDict[str, int]
            _field_defaults = ...  # type: collections.OrderedDict[str, int]
            _field_types = ...  # type: collections.OrderedDict[str, type]
            _fields = ...  # type: Tuple[str]
            a = ...  # type: int
            def __getnewargs__(self) -> Tuple[int]: ...
            def __getstate__(self) -> None: ...
            def __init__(self, *args, **kwargs) -> None: ...
            def __new__(cls: Type[_TSubNamedTuple], a: int) -> _TSubNamedTuple:
              ...
            def _asdict(self) -> collections.OrderedDict[str, int]: ...
            @classmethod
            def _make(cls: Type[_TSubNamedTuple],
                      iterable: Iterable[int], new = ...,
                      len: Callable[[Sized], int] = ...) -> _TSubNamedTuple: ...
            def _replace(self: _TSubNamedTuple,
                         **kwds: int) -> _TSubNamedTuple: ...

        class baseClass(object):
            x = ...  # type: int
            y = ...  # type: int
        """)

  def test_namedtuple_class_pyi(self):
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
      """)
    self.assertTypesMatchPytd(
        ty,
        """
        import collections
        from typing import Callable, Iterable, Sized, Tuple, Type, TypeVar, Union

        X: SubNamedTuple
        a: int
        b: str
        c: int

        _TSubNamedTuple = TypeVar('_TSubNamedTuple', bound=SubNamedTuple)

        class SubNamedTuple(tuple):
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
            def __new__(cls: Type[_TSubNamedTuple], a: int, b: str = ...,
              c: int = ...) -> _TSubNamedTuple: ...
            def __repr__(self) -> str: ...
            def _asdict(self) -> collections.OrderedDict[str, Union[int, str]]:
              ...
            @classmethod
            def _make(cls: Type[_TSubNamedTuple],
                      iterable: Iterable[Union[int, str]], new = ...,
                      len: Callable[[Sized], int] = ...) -> _TSubNamedTuple: ...
            def _replace(self: _TSubNamedTuple,
                         **kwds: Union[int, str]) -> _TSubNamedTuple: ...
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


test_base.main(globals(), __name__ == "__main__")
