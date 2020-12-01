"""Tests for matching against protocols.

Based on PEP 544 https://www.python.org/dev/peps/pep-0544/.
"""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class ProtocolTest(test_base.TargetPython3BasicTest):
  """Tests for protocol implementation."""

  def test_check_protocol(self):
    self.Check("""
      import protocols
      from typing import Sized
      def f(x: protocols.Sized):
        return None
      def g(x: Sized):
        return None
      class Foo:
        def __len__(self):
          return 5
      f([])
      foo = Foo()
      f(foo)
      g([])
      g(foo)
    """)

  def test_check_protocol_error(self):
    _, errors = self.InferWithErrors("""
      import protocols

      def f(x: protocols.SupportsAbs):
        return x.__abs__()
      f(["foo"])  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\(x: SupportsAbs\).*\(x: List\[str\]\)"})

  def test_check_iterator_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Iterator
      def f(x: Iterator[int]):
        return None
      class Foo:
        def next(self) -> str:
          return ''
        def __iter__(self):
          return self
      f(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Iterator\[int\].*Foo"})

  def test_check_protocol_match_unknown(self):
    self.Check("""
      from typing import Sized
      def f(x: Sized):
        pass
      class Foo(object):
        pass
      def g(x):
        foo = Foo()
        foo.__class__ = x
        f(foo)
    """)

  def test_check_parameterized_protocol(self):
    self.Check("""
      from typing import Iterator, Iterable

      class Foo(object):
        def __iter__(self) -> Iterator[int]:
          return iter([])

      def f(x: Iterable[int]):
        pass

      foo = Foo()
      f(foo)
      f(iter([3]))
    """)

  def test_check_parameterized_protocol_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Iterator, Iterable

      class Foo(object):
        def __iter__(self) -> Iterator[str]:
          return iter([])

      def f(x: Iterable[int]):
        pass

      foo = Foo()
      f(foo)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\(x: Iterable\[int\]\).*\(x: Foo\)"})

  def test_check_parameterized_protocol_multi_signature(self):
    self.Check("""
      from typing import Sequence, Union

      class Foo(object):
        def __len__(self):
          return 0
        def __getitem__(self, x: Union[int, slice]) -> Union[int, Sequence[int]]:
          return 0

      def f(x: Sequence[int]):
        pass

      foo = Foo()
      f(foo)
    """)

  def test_check_parameterized_protocol_error_multi_signature(self):
    _, errors = self.InferWithErrors("""
      from typing import Sequence, Union

      class Foo(object):
        def __len__(self):
          return 0
        def __getitem__(self, x: int) -> int:
          return 0

      def f(x: Sequence[int]):
        pass

      foo = Foo()
      f(foo)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\(x: Sequence\[int\]\).*\(x: Foo\)"})

  def test_construct_dict_with_protocol(self):
    self.Check("""
      class Foo(object):
        def __iter__(self):
          pass
      def f(x: Foo):
        return dict(x)
    """)

  def test_method_on_superclass(self):
    self.Check("""
      class Foo(object):
        def __iter__(self):
          pass
      class Bar(Foo):
        pass
      def f(x: Bar):
        return iter(x)
    """)

  def test_method_on_parameterized_superclass(self):
    self.Check("""
      from typing import List
      class Bar(List[int]):
        pass
      def f(x: Bar):
        return iter(x)
    """)

  def test_any_superclass(self):
    self.Check("""
      class Bar(__any_object__):
        pass
      def f(x: Bar):
        return iter(x)
    """)

  def test_multiple_options(self):
    self.Check("""
      class Bar(object):
        if __random__:
          def __iter__(self): return 1
        else:
          def __iter__(self): return 2
      def f(x: Bar):
        return iter(x)
    """)

  def test_iterable_getitem(self):
    ty = self.Infer("""
      from typing import Iterable, Iterator, TypeVar
      T = TypeVar("T")
      class Bar(object):
        def __getitem__(self, i: T) -> T:
          if i > 10:
            raise IndexError()
          return i
      T2 = TypeVar("T2")
      def f(s: Iterable[T2]) -> Iterator[T2]:
        return iter(s)
      next(f(Bar()))
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Iterator, TypeVar
      T = TypeVar("T")
      class Bar(object):
        def __getitem__(self, i: T) -> T: ...
      T2 = TypeVar("T2")
      def f(s: Iterable[T2]) -> Iterator[T2]: ...
    """)

  def test_iterable_iter(self):
    ty = self.Infer("""
      from typing import Iterable, Iterator, TypeVar
      class Bar(object):
        def __iter__(self) -> Iterator:
          return iter([])
      T = TypeVar("T")
      def f(s: Iterable[T]) -> Iterator[T]:
        return iter(s)
      next(f(Bar()))
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Iterator, TypeVar
      class Bar(object):
        def __iter__(self) -> Iterator: ...
      T = TypeVar("T")
      def f(s: Iterable[T]) -> Iterator[T]: ...
    """)

  def test_pyi_iterable_getitem(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class Foo(object):
          def __getitem__(self, i: T) -> T: ...
      """)
      self.Check("""
        from typing import Iterable, TypeVar
        import foo
        T = TypeVar("T")
        def f(s: Iterable[T]) -> T: ...
        f(foo.Foo())
      """, pythonpath=[d.path])

  def test_pyi_iterable_iter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        class Foo(object):
          def __iter__(self) -> Any: ...
      """)
      self.Check("""
        from typing import Iterable, TypeVar
        import foo
        T = TypeVar("T")
        def f(s: Iterable[T]) -> T: ...
        f(foo.Foo())
      """, pythonpath=[d.path])

  def test_inherited_abstract_method_error(self):
    _, errors = self.InferWithErrors("""
      from typing import Iterator
      class Foo(object):
        def __iter__(self) -> Iterator[str]:
          return __any_object__
        def next(self):
          return __any_object__
      def f(x: Iterator[int]):
        pass
      f(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Iterator\[int\].*Foo"})

  def test_reversible(self):
    self.Check("""
      from typing import Reversible
      class Foo(object):
        def __reversed__(self):
          pass
      def f(x: Reversible):
        pass
      f(Foo())
    """)

  def test_collection(self):
    self.Check("""
      from typing import Collection
      class Foo(object):
        def __contains__(self, x):
          pass
        def __iter__(self):
          pass
        def __len__(self):
          pass
      def f(x: Collection):
        pass
      f(Foo())
    """)

  def test_list_against_collection(self):
    self.Check("""
      from typing import Collection
      def f() -> Collection[str]:
        return [""]
    """)

  def test_hashable(self):
    self.Check("""
      from typing import Hashable
      class Foo(object):
        def __hash__(self):
          pass
      def f(x: Hashable):
        pass
      f(Foo())
    """)

  def test_list_hash(self):
    errors = self.CheckWithErrors("""
      from typing import Hashable
      def f(x: Hashable):
        pass
      f([])  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Hashable.*List.*__hash__"})

  def test_hash_constant(self):
    errors = self.CheckWithErrors("""
      from typing import Hashable
      class Foo(object):
        __hash__ = None
      def f(x: Hashable):
        pass
      f(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Hashable.*Foo.*__hash__"})

  def test_hash_type(self):
    self.Check("""
      from typing import Hashable, Type
      def f(x: Hashable):
        pass
      def g(x: Type[int]):
        return f(x)
    """)

  def test_hash_module(self):
    self.Check("""
      import subprocess
      from typing import Hashable
      def f(x: Hashable):
        pass
      f(subprocess)
    """)

  def test_generic_callable(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]):
          def __init__(self, x: T):
            self = Foo[T]
          def __call__(self) -> T: ...
      """)
      self.Check("""
        from typing import Callable
        import foo
        def f() -> Callable:
          return foo.Foo("")
        def g() -> Callable[[], str]:
          return foo.Foo("")
      """, pythonpath=[d.path])

  def test_protocol_caching(self):
    self.Check("""
      import collections
      from typing import Text

      class _PortInterface(object):

        def __init__(self):
          self._flattened_ports = collections.OrderedDict()

        def PortBundle(self, prefix: Text, bundle):
          for name, port in bundle.ports.items():
            full_name = prefix + "_" + name
            self._flattened_ports[full_name] = port

        def _GetPortsWithDirection(self):
          return collections.OrderedDict(
              (name, port) for name, port in self._flattened_ports)
    """)

  def test_custom_protocol(self):
    self.Check("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self):
          pass
      class MyAppendable(object):
        def append(self):
          pass
      def f(x: Appendable):
        pass
      f([])
      f(MyAppendable())
    """)

  def test_custom_protocol_error(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self):
          pass
      class NotAppendable(object):
        pass
      def f(x: Appendable):
        pass
      f(42)  # wrong-arg-types[e1]
      f(NotAppendable())  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Appendable.*int.*append",
        "e2": r"Appendable.*NotAppendable.*append"})

  def test_reingest_custom_protocol(self):
    ty = self.Infer("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self) -> None:
          pass
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      self.Check("""
        import foo
        class MyAppendable(object):
          def append(self):
            pass
        def f(x: foo.Appendable):
          pass
        f([])
        f(MyAppendable())
      """, pythonpath=[d.path])

  def test_reingest_custom_protocol_error(self):
    ty = self.Infer("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self) -> None:
          pass
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      errors = self.CheckWithErrors("""
        import foo
        class NotAppendable(object):
          pass
        def f(x: foo.Appendable):
          pass
        f(42)  # wrong-arg-types[e1]
        f(NotAppendable())  # wrong-arg-types[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"Appendable.*int.*append",
          "e2": r"Appendable.*NotAppendable.*append"})

  def test_reingest_custom_protocol_inherit_method(self):
    ty = self.Infer("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self):
          pass
      class Mutable(Appendable, Protocol):
        def remove(self):
          pass
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      errors = self.CheckWithErrors("""
        from foo import Mutable
        class NotMutable(object):
          def remove(self):
            pass
        def f(x: Mutable):
          pass
        f([])  # ok
        f(NotMutable())  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"Mutable.*NotMutable.*append"})

  def test_reingest_custom_protocol_implement_method(self):
    ty = self.Infer("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self):
          pass
      class Mixin(object):
        def append(self):
          pass
      class Removable(Mixin, Appendable, Protocol):
        def remove(self):
          pass
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      self.Check("""
        from foo import Removable
        def f(x: Removable):
          pass
        class MyRemovable(object):
          def remove(self):
            pass
        f(MyRemovable())
      """, pythonpath=[d.path])

  def test_ignore_method_body(self):
    self.Check("""
      from typing_extensions import Protocol
      class Countable(Protocol):
        def count(self) -> int:
          ...
    """)

  def test_check_method_body(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Protocol
      class Countable(Protocol):
        def count(self) -> int:
          ...  # bad-return-type[e]
      class MyCountable(Countable):
        def count(self):
          return super(MyCountable, self).count()
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*None.*line 7"})

  def test_callback_protocol(self):
    self.CheckWithErrors("""
      from typing_extensions import Protocol
      class Foo(Protocol):
        def __call__(self) -> int:
          return 0

      def f1() -> int:
        return 0
      def f2(x) -> int:
        return x
      def f3() -> str:
        return ''

      def accepts_foo(f: Foo):
        pass

      accepts_foo(f1)
      accepts_foo(f2)  # wrong-arg-types
      accepts_foo(f3)  # wrong-arg-types
    """)

  def test_callback_protocol_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Protocol
        class Foo(Protocol):
          def __call__(self, x: str) -> str: ...
        def accepts_foo(f: Foo) -> None: ...
      """)
      self.CheckWithErrors("""
        import foo
        def f1(x: str) -> str:
          return x
        def f2() -> str:
          return ''
        def f3(x: int) -> str:
          return str(x)

        foo.accepts_foo(f1)
        foo.accepts_foo(f2)  # wrong-arg-types
        foo.accepts_foo(f3)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_class_matches_callback_protocol(self):
    self.CheckWithErrors("""
      from typing_extensions import Protocol
      class Foo(Protocol):
        def __call__(self) -> int:
          return 0
      def accepts_foo(f: Foo):
        pass

      accepts_foo(int)
      accepts_foo(str)  # wrong-arg-types
    """)

  def test_class_matches_callback_protocol_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Protocol
        class Foo(Protocol):
          def __call__(self) -> int: ...
        def accepts_foo(f: Foo) -> None: ...
      """)
      self.CheckWithErrors("""
        import foo
        foo.accepts_foo(int)
        foo.accepts_foo(str)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_classmethod(self):
    # TODO(rechen): An instance method shouldn't match a classmethod.
    self.CheckWithErrors("""
      from typing import Protocol
      class Foo(Protocol):
        @classmethod
        def f(cls):
          return cls()
      class Bar:
        @classmethod
        def f(cls):
          return cls()
      class Baz:
        def f(self):
          return type(self)
      class Qux:
        pass
      def f(x: Foo):
        pass
      f(Bar())
      f(Baz())
      f(Qux())  # wrong-arg-types
    """)

  def test_abstractmethod(self):
    self.CheckWithErrors("""
      import abc
      from typing import Protocol

      class Foo(Protocol):
        @abc.abstractmethod
        def f(self) -> int:
          pass

      class Bar:
        def f(self):
          pass

      class Baz:
        pass

      def f(x: Foo):
        pass

      f(Bar())
      f(Baz())  # wrong-arg-types
    """)


class ProtocolsTestPython3Feature(test_base.TargetPython3FeatureTest):
  """Tests for protocol implementation on a target using a Python 3 feature."""

  def test_check_iterator(self):
    self.Check("""
      from typing import Iterator
      def f(x: Iterator):
        return None
      class Foo:
        def __next__(self):
          return None
        def __iter__(self):
          return None
      foo = Foo()
      f(foo)
    """)

  def test_check_parameterized_iterator(self):
    self.Check("""
      from typing import Iterator
      def f(x: Iterator[int]):
        return None
      class Foo:
        def __next__(self):
          return 42
        def __iter__(self):
          return self
      f(Foo())
    """)

  def test_inherited_abstract_method(self):
    self.Check("""
      from typing import Iterator
      class Foo(object):
        def __iter__(self) -> Iterator[int]:
          return __any_object__
        def __next__(self):
          return __any_object__
      def f(x: Iterator[int]):
        pass
      f(Foo())
    """)

  def test_check_supports_bytes_protocol(self):
    self.Check("""
      import protocols
      from typing import SupportsBytes
      def f(x: protocols.SupportsBytes):
        return None
      def g(x: SupportsBytes):
        return None
      class Foo:
        def __bytes__(self):
          return b"foo"
      foo = Foo()
      f(foo)
      g(foo)
    """)


test_base.main(globals(), __name__ == "__main__")
