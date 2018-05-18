"""Tests for the typing.NamedTuple overlay."""

from pytype.tests import test_base


class NamedTupleTest(test_base.TargetPython27FeatureTest):
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
          __annotations__ = ...  # type: collections.OrderedDict[
            Union[str, unicode], type]
          __dict__ = ...  # type: collections.OrderedDict[
            Union[str, unicode], Union[int, str]]
          _field_defaults = ...  # type: collections.OrderedDict[
            Union[str, unicode], Union[int, str]]
          _field_types = ...  # type: collections.OrderedDict[
            Union[str, unicode], type]
          _fields = ...  # type: Tuple[str, str]
          a = ...  # type: int
          b = ...  # type: str
          def __getnewargs__(self) -> Tuple[int, str]: ...
          def __getstate__(self) -> None: ...
          def __init__(self, *args, **kwargs) -> None: ...
          def __new__(cls: Type[_TX], a: int, b: str) -> _TX: ...
          def _asdict(self) -> collections.OrderedDict[
            Union[str, unicode], Union[int, str]]: ...
          @classmethod
          def _make(cls: Type[_TX], iterable: Iterable[Union[int, str]],
            new = ..., len: Callable[[Sized], int] = ...) -> _TX: ...
          def _replace(self: _TX, **kwds: Union[int, str]) -> _TX: ...
          """)


test_base.main(globals(), __name__ == "__main__")
