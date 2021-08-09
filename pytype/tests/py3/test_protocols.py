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
      class Foo:
        pass
      def g(x):
        foo = Foo()
        foo.__class__ = x
        f(foo)
    """)

  def test_check_parameterized_protocol(self):
    self.Check("""
      from typing import Iterator, Iterable

      class Foo:
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

      class Foo:
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

      class Foo:
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

      class Foo:
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
      class Foo:
        def __iter__(self):
          pass
      def f(x: Foo):
        return dict(x)
    """)

  def test_method_on_superclass(self):
    self.Check("""
      class Foo:
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
      class Bar:
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
      class Bar:
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
      class Bar:
        def __getitem__(self, i: T) -> T: ...
      T2 = TypeVar("T2")
      def f(s: Iterable[T2]) -> Iterator[T2]: ...
    """)

  def test_iterable_iter(self):
    ty = self.Infer("""
      from typing import Iterable, Iterator, TypeVar
      class Bar:
        def __iter__(self) -> Iterator:
          return iter([])
      T = TypeVar("T")
      def f(s: Iterable[T]) -> Iterator[T]:
        return iter(s)
      next(f(Bar()))
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Iterator, TypeVar
      class Bar:
        def __iter__(self) -> Iterator: ...
      T = TypeVar("T")
      def f(s: Iterable[T]) -> Iterator[T]: ...
    """)

  def test_pyi_iterable_getitem(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class Foo:
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
        class Foo:
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
      class Foo:
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
      class Foo:
        def __reversed__(self):
          pass
      def f(x: Reversible):
        pass
      f(Foo())
    """)

  def test_collection(self):
    self.Check("""
      from typing import Collection
      class Foo:
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
      class Foo:
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
      class Foo:
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

      class _PortInterface:

        def __init__(self):
          self._flattened_ports = collections.OrderedDict()

        def PortBundle(self, prefix: Text, bundle):
          for name, port in bundle.ports.items():
            full_name = prefix + "_" + name
            self._flattened_ports[full_name] = port

        def _GetPortsWithDirection(self):
          return collections.OrderedDict(
              (name, port) for name, port in self._flattened_ports.items())
    """)

  def test_custom_protocol(self):
    self.Check("""
      from typing_extensions import Protocol
      class Appendable(Protocol):
        def append(self):
          pass
      class MyAppendable:
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
      class NotAppendable:
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
        class MyAppendable:
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
        class NotAppendable:
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
        class NotMutable:
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
      class Mixin:
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
        class MyRemovable:
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

  def test_decorated_method(self):
    self.Check("""
      from typing import Callable
      from typing_extensions import Protocol
      class Foo(Protocol):
        def foo(self):
          pass
      def decorate(f: Callable) -> Callable:
        return f
      class Bar:
        @decorate
        def foo(self):
          pass
      def accept(foo: Foo):
        pass
      accept(Bar())
    """)

  def test_len(self):
    self.Check("""
      from typing import Generic, Protocol, TypeVar
      T = TypeVar('T')
      class SupportsLen(Generic[T], Protocol):
        def __len__(self) -> int: ...
      def f() -> SupportsLen[int]:
        return [1, 2, 3]
    """)

  def test_property(self):
    self.Check("""
      from typing_extensions import Protocol
      class Foo(Protocol):
        @property
        def name(self) -> str: ...
        def f(self) -> int: ...
    """)

  def test_has_dynamic_attributes(self):
    self.Check("""
      from typing import Protocol
      class Foo(Protocol):
        def f(self) -> int: ...
      class Bar:
        _HAS_DYNAMIC_ATTRIBUTES = True
      def f(x: Foo):
        pass
      f(Bar())
    """)

  def test_empty(self):
    self.Check("""
      from typing import Protocol
      class Foo(Protocol):
        pass
      class Bar:
        pass
      def f(foo: Foo):
        pass
      f(Bar())
    """)

  def test_deduplicate_error_message(self):
    # Tests that the 'Attributes not implemented' line appears only once in the
    # error message.
    errors = self.CheckWithErrors("""
      from typing import Callable, Iterable, Optional, Union

      DistanceFunctionsType = Iterable[Union[Callable[[str, str], float], str]]

      def f(x: DistanceFunctionsType) -> DistanceFunctionsType:
        return (x,)  # bad-return-type[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Actually returned[^\n]*\nAttributes[^\n]*$"})


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
      class Foo:
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

  def test_metaclass_abstractness(self):
    self.Check("""
      import abc
      from typing import Protocol
      class Meta1(type(Protocol)):
        pass
      class Meta2(Protocol.__class__):
        pass
      class Foo(metaclass=Meta1):
        @abc.abstractmethod
        def foo(self):
          pass
      class Bar(metaclass=Meta2):
        @abc.abstractmethod
        def bar(self):
          pass
    """)

  def test_module(self):
    foo_ty = self.Infer("""
      x: int
      def f() -> str:
        return 'hello world'
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      errors = self.CheckWithErrors("""
        import foo
        from typing import Protocol
        class ShouldMatch(Protocol):
          x: int
          def f(self) -> str: ...
        class ExtraAttribute(Protocol):
          x: int
          y: str
        class ExtraMethod(Protocol):
          def f(self) -> str: ...
          def g(self) -> int: ...
        class WrongType(Protocol):
          x: str
        def should_match(x: ShouldMatch):
          pass
        def extra_attribute(x: ExtraAttribute):
          pass
        def extra_method(x: ExtraMethod):
          pass
        def wrong_type(x: WrongType):
          pass
        should_match(foo)
        extra_attribute(foo)  # wrong-arg-types[e1]
        extra_method(foo)  # wrong-arg-types[e2]
        wrong_type(foo)  # wrong-arg-types[e3]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"not implemented on module: y",
          "e2": r"not implemented on module: g",
          "e3": r"x.*expected str, got int",
      })


class ProtocolAttributesTest(test_base.TargetPython3FeatureTest):
  """Tests for non-method protocol attributes."""

  def test_basic(self):
    errors = self.CheckWithErrors("""
      from typing import Protocol
      class Foo(Protocol):
        x: int
      class Bar:
        x: int
      class Baz:
        x: str
      def f(foo: Foo):
        pass
      f(Bar())
      f(Baz())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*expected int, got str"})

  def test_missing(self):
    errors = self.CheckWithErrors("""
      from typing import Protocol
      class Foo(Protocol):
        x: int
        y: str
      class Bar:
        y = ''
      def f(foo: Foo):
        pass
      f(Bar())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Foo.*Bar.*x"})

  def test_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Protocol
        class Foo(Protocol):
          x: int
      """)
      self.CheckWithErrors("""
        import foo
        class Bar:
          x = 0
        class Baz:
          x = '1'
        def f(x: foo.Foo):
          pass
        f(Bar())
        f(Baz())  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_pyi_inheritance(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo:
          x: int
      """)
      self.CheckWithErrors("""
        import foo
        from typing import Protocol
        class Bar(Protocol):
          x: int
        class Baz(Protocol):
          x: str
        class Foo2(foo.Foo):
          pass
        def f(bar: Bar):
          pass
        def g(baz: Baz):
          pass
        f(Foo2())
        g(Foo2())  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_instance_attribute(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class Foo(Protocol):
        x: int
      class Bar:
        def __init__(self):
          self.x = 0
      class Baz:
        def __init__(self):
          self.x = ''
      def f(foo: Foo):
        pass
      f(Bar())
      f(Baz())  # wrong-arg-types
    """)

  def test_property(self):
    errors = self.CheckWithErrors("""
      from typing import Protocol
      class Foo(Protocol):
        @property
        def x(self) -> int: ...
      class Bar:
        @property
        def x(self):
          return 0
      class Baz:
        @property
        def x(self):
          return ''
      def f(foo: Foo):
        pass
      f(Bar())
      f(Baz())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*expected int, got str"})

  def test_property_in_pyi_protocol(self):
    foo_ty = self.Infer("""
      from typing import Protocol
      class Foo(Protocol):
        @property
        def x(self) -> int: ...
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.CheckWithErrors("""
        import foo
        class Bar:
          @property
          def x(self):
            return 0
        class Baz:
          @property
          def x(self):
            return ''
        def f(x: foo.Foo):
          pass
        f(Bar())
        f(Baz())  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_inherit_property(self):
    foo_ty = self.Infer("""
      class Foo:
        @property
        def x(self):
          return 0
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.CheckWithErrors("""
        import foo
        from typing import Protocol
        class Protocol1(Protocol):
          @property
          def x(self) -> int: ...
        class Protocol2(Protocol):
          @property
          def x(self) -> str: ...
        class Bar(foo.Foo):
          pass
        def f1(x: Protocol1):
          pass
        def f2(x: Protocol2):
          pass
        f1(Bar())
        f2(Bar())  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_optional(self):
    errors = self.CheckWithErrors("""
      from typing import Optional, Protocol
      class Foo(Protocol):
        x: Optional[int]
      class Bar:
        x = 0
      class Baz:
        x = ''
      def f(x: Foo):
        pass
      f(Bar())
      f(Baz())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"expected Optional\[int\], got str"})

  def test_match_optional_to_optional(self):
    self.Check("""
      from typing import Optional, Protocol
      class Foo(Protocol):
        x: Optional[int]
      class Bar:
        def __init__(self, x: Optional[int]):
          self.x = x
      def f(x: Foo):
        pass
      f(Bar(0))
    """)

  def test_generic(self):
    errors = self.CheckWithErrors("""
      from typing import Generic, Protocol, Type, TypeVar

      T = TypeVar('T')
      class Foo(Protocol[T]):
        x: T

      T2 = TypeVar('T2', bound=Foo[int])
      def f(cls: Type[T2]) -> T2:
        return cls()

      class Bar:
        x = 0
      class Baz:
        x = ''

      f(Bar)  # ok
      f(Baz)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"expected int, got str"})

  def test_generic_from_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Protocol, TypeVar
        T = TypeVar('T')
        class Foo(Protocol[T]):
          x: T
      """)
      errors = self.CheckWithErrors("""
        from typing import Type, TypeVar
        import foo

        T = TypeVar('T', bound=foo.Foo[int])
        def f(cls: Type[T]) -> T:
          return cls()

        class Bar:
          x = 0
        class Baz:
          x = ''

        f(Bar)  # ok
        f(Baz)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"expected int, got str"})

  def test_generic_used_in_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("protocol.pyi", """
        from typing import Dict, List, Protocol, TypeVar
        T = TypeVar('T')
        class Foo(Protocol[T]):
          x: Dict[str, List[T]]
    """)
      d.create_file("util.pyi", """
        import protocol
        from typing import Type, TypeVar
        T = TypeVar('T', bound=protocol.Foo[int])
        def f(x: Type[T]) -> T: ...
      """)
      errors = self.CheckWithErrors("""
        from typing import Dict, List
        import util
        class Bar:
          x: Dict[str, List[int]]
        class Baz:
          x: Dict[str, List[str]]
        util.f(Bar)  # ok
        util.f(Baz)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e": (r"expected Dict\[str, List\[int\]\], "
                r"got Dict\[str, List\[str\]\]")})

  def test_match_multi_attributes_against_dataclass_protocol(self):
    errors = self.CheckWithErrors("""
      from typing import Dict, Protocol, TypeVar, Union
      import dataclasses
      T = TypeVar('T')
      class Dataclass(Protocol[T]):
        __dataclass_fields__: Dict[str, dataclasses.Field[T]]
      def f(x: Dataclass[int]):
        pass
      @dataclasses.dataclass
      class ShouldMatch:
        x: int
        y: int
      @dataclasses.dataclass
      class ShouldNotMatch:
        x: int
        y: str
      f(ShouldMatch(0, 0))
      f(ShouldNotMatch(0, ''))  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": (r"expected Dict\[str, dataclasses\.Field\[int\]\], "
              r"got Dict\[str, dataclasses\.Field\[Union\[int, str\]\]\]")})


test_base.main(globals(), __name__ == "__main__")
