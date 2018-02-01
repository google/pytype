"""Tests for the typing.NamedTuple overlay."""


from pytype.tests import test_base


class NamedTupleTest(test_base.BaseTest):
  """Tests for the typing.NamedTuple overlay."""

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
          def _replace(self, **kwds: Union[int, str]) -> _TX: ...
          """)

  def test_basic_calls(self):
    errors = self.CheckWithErrors("""\
      import typing
      Basic = typing.NamedTuple("Basic", [('a', str)])
      ex = Basic("hello world")
      ea = ex.a
      ey = Basic()  # Should fail
      ez = Basic("a", "b")  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "missing-parameter"),
        (6, "wrong-arg-count")])

  def test_optional_field_type(self):
    errors = self.CheckWithErrors("""\
      import typing
      X = typing.NamedTuple("X", [('a', str), ('b', typing.Optional[int])])
      xa = X('hello', None)
      xb = X('world', 2)
      xc = X('nope', '2')  # Should fail
      xd = X()  # Should fail
      xe = X(1, "nope")  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types"),
        (6, "missing-parameter"),
        (7, "wrong-arg-types")])

  def test_class_field_type(self):
    errors = self.CheckWithErrors("""\
      import typing
      class Foo(object):
        pass
      Y = typing.NamedTuple("Y", [('a', str), ('b', Foo)])
      ya = Y('a', Foo())
      yb = Y('a', 1)  # Should fail
      yc = Y(Foo())  # Should fail
      yd = Y(1)  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (6, "wrong-arg-types"),
        (7, "missing-parameter"),
        (8, "missing-parameter")])

  def test_nested_containers(self):
    errors = self.CheckWithErrors("""\
      import typing
      Z = typing.NamedTuple("Z", [('a', typing.List[typing.Optional[int]])])
      za = Z([1])
      zb = Z([None, 2])
      zc = Z(1)  # Should fail

      import typing
      A = typing.NamedTuple("A", [('a', typing.Dict[int, str]), ('b', typing.Tuple[int, int])])
      aa = A({1: '1'}, (1, 2))
      ab = A({}, (1, 2))
      ac = A(1, 2)  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "wrong-arg-types"),
        (11, "wrong-arg-types")])

  def test_pytd_field(self):
    errors = self.CheckWithErrors("""\
      import typing
      import datetime
      B = typing.NamedTuple("B", [('a', datetime.date)])
      ba = B(datetime.date(1,2,3))
      bb = B()  # Should fail
      bc = B(1)  # Should fail
      """)
    self.assertErrorLogIs(errors, [
        (5, "missing-parameter"),
        (6, "wrong-arg-types")])

  def test_make(self):
    errors = self.CheckWithErrors("""\
        from __future__ import google_type_annotations
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
        (6, "wrong-arg-types"),
        (7, "wrong-arg-types")])

  def test_subclass(self):
    errors = self.CheckWithErrors("""\
        from __future__ import google_type_annotations
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
        (14, "wrong-arg-types"),
        (15, "missing-parameter")])

  def test_bad_calls(self):
    _, errorlog = self.InferWithErrors("""\
        import typing
        typing.NamedTuple("_", ["abc", "def", "ghi"])
        # "def" is a keyword, so the call on the next line fails.
        typing.NamedTuple("_", [("abc", int), ("def", int), ("ghi", int)])
        typing.NamedTuple("_", [("abc", "int")])
        typing.NamedTuple("1", [("a", int)])
        """)
    self.assertErrorLogIs(errorlog,
                          [(2, "wrong-arg-types"),
                           (4, "invalid-namedtuple-arg"),
                           (5, "not-supported-yet"),
                           (6, "invalid-namedtuple-arg")])

  def test_empty_args(self):
    self.Check(
        """
        from __future__ import google_type_annotations
        import typing
        X = typing.NamedTuple("X", [])
        """)

if __name__ == "__main__":
  test_base.main()
