"""Tests for the typing.NamedTuple overlay."""

from pytype.pytd import pytd
from pytype.tests import test_base


class NamedTupleTest(test_base.TargetPython3BasicTest):
  """Tests for the typing.NamedTuple overlay."""

  def test_make(self):
    errors = self.CheckWithErrors("""\
        import typing
        A = typing.NamedTuple("A", [("b", str), ("c", str)])
        a = A._make(["hello", "world"])
        b = A._make(["hello", "world"], len=len)
        c = A._make([1, 2])  # Should fail
        d = A._make(A)  # Should fail
        def f(e: A) -> None: pass
        f(a)
        """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types"),
        (6, "wrong-arg-types")])

  def test_subclass(self):
    errors = self.CheckWithErrors("""\
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
        take_b(A("", 0))  # Should fail
        B()  # Should fail
        # _make and _replace should return instances of the subclass.
        take_b(B._make(["hello", 0]))
        take_b(y._replace(b="world"))
        """)
    self.assertErrorLogIs(errors, [
        (13, "wrong-arg-types"),
        (14, "missing-parameter")])

  def test_callable_attribute(self):
    ty = self.Infer("""
      from typing import Callable, NamedTuple
      X = NamedTuple("X", [("f", Callable)])
      def foo(x: X):
        return x.f
    """)
    self.assertMultiLineEqual(pytd.Print(ty.Lookup("foo")),
                              "def foo(x: X) -> Callable: ...")

  def test_bare_union_attribute(self):
    ty, errors = self.InferWithErrors("""\
      from typing import NamedTuple, Union
      X = NamedTuple("X", [("x", Union)])
      def foo(x: X):
        return x.x
    """)
    self.assertMultiLineEqual(pytd.Print(ty.Lookup("foo")),
                              "def foo(x: X) -> Any: ...")
    self.assertErrorLogIs(errors, [(2, "invalid-annotation", r"Union.*x")])


class NamedTupleTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for the typing.NamedTuple overlay in Python 3.6."""

  def test_basic_namedtuple(self):
    ty = self.Infer("""\
      import typing
      X = typing.NamedTuple("X", [("a", int), ("b", str)])
      x = X(1, "hello")
      a = x.a
      b = x.b
      """)
    self.assertTypesMatchPytd(
        ty,
        """\
        import collections
        from typing import Callable, Iterable, Sized, Tuple, Type, TypeVar, Union
        typing = ...  # type: module
        x = ...  # type: X
        a = ...  # type: int
        b = ...  # type: str
        _TX = TypeVar('_TX', bound=X)
        class X(tuple):
          __slots__ = ["a", "b"]
          __annotations__ = ...  # type: collections.OrderedDict[str, type]
          __dict__ = ...  # type: collections.OrderedDict[str, Union[int, str]]
          _field_defaults = ...  # type: collections.OrderedDict[str, Union[int,
            str]]
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
    self.assertMultiLineEqual(pytd.Print(ty.Lookup("foo")),
                              "def foo(x: X) -> Union[bytes, str]: ...")


test_base.main(globals(), __name__ == "__main__")
