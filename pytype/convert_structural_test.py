"""Test match.py."""

import textwrap

from pytype import convert_structural
from pytype import load_pytd
from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import visitors
import six

import unittest


class MatchTest(unittest.TestCase):

  PYTHON_VERSION = (2, 7)

  @classmethod
  def setUpClass(cls):
    cls.loader = load_pytd.Loader("", cls.PYTHON_VERSION)
    cls.builtins_pytd = cls.loader.builtins

  def parse(self, src):
    ast = parser.parse_string(textwrap.dedent(src))
    ast = ast.Visit(visitors.LookupBuiltins(self.builtins_pytd))
    return ast

  def parse_and_solve(self, src):
    ast = self.parse(src)
    ast = ast.Visit(visitors.NamedTypeToClassType())
    ast = ast.Visit(visitors.AdjustTypeParameters())
    types, _ = convert_structural.solve(ast, builtins_pytd=self.builtins_pytd)
    # Drop "__builtin__" prefix, for more readable tests.
    return {k: {v.rpartition("__builtin__.")[2] for v in l}
            for k, l in types.items()}

  @unittest.skip("Moving to protocols")
  def test_simple(self):
    mapping = self.parse_and_solve("""
      class `~unknown2`(object):
        pass
      class `~unknown1`(object):
        def __add__(self, _1: `~unknown2`) -> int
    """)
    six.assertCountEqual(self, ["int", "bool"], mapping["~unknown1"])
    six.assertCountEqual(self, ["int", "bool"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_float_and_bytearray(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def __add__(self, _1: int) -> float
        def __add__(self, _1: float) -> float
      class `~unknown2`(object):
        def __add__(self, _1: str) -> bytearray
        def __add__(self, _1: bytearray) -> bytearray
      """)
    six.assertCountEqual(self, ["float"], mapping["~unknown1"])
    six.assertCountEqual(self, ["bytearray"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_float_and_bytearray2(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def __add__(self, _1: int or float) -> float
      class `~unknown2`(object):
        def __add__(self, _1: bytearray) -> bytearray
      """)
    six.assertCountEqual(self, ["float"], mapping["~unknown1"])
    six.assertCountEqual(self, ["str", "bytearray"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_append(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def append(self, _1: int) -> NoneType
    """)
    six.assertCountEqual(self,
                         ["list", "bytearray", "typing.List",
                          "typing.MutableSequence"],
                         mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_single_list(self):
    # Differs from test_append in that append(float) doesn't match bytearray
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def append(self, _1: float) -> NoneType
    """)
    convert_structural.log_info_mapping(mapping)
    six.assertCountEqual(self,
                         ["list", "typing.MutableSequence", "typing.List"],
                         mapping["~unknown1"])
    six.assertCountEqual(self,
                         ["float"], mapping["~unknown1.__builtin__.list._T"])

  @unittest.skip("Moving to protocols")
  def test_list(self):
    mapping = self.parse_and_solve("""
      class `~unknown2`(object):
        def append(self, _1: `~unknown1`) -> NoneType
        def __getitem__(self, _1: ?) -> `~unknown1`

      class `~unknown1`(object):
        def __add__(self: float, _1: int) -> float
        def __add__(self: float, _1: float) -> float
      """)
    convert_structural.log_info_mapping(mapping)
    six.assertCountEqual(self, ["float"], mapping["~unknown1"])
    six.assertCountEqual(self,
                         ["list", "typing.List", "typing.MutableSequence"],
                         mapping["~unknown2"])
    six.assertCountEqual(self,
                         ["float"], mapping["~unknown2.__builtin__.list._T"])

  @unittest.skip("Moving to protocols")
  def test_float_list(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def append(self, _1: ?) -> NoneType
        def __getitem__(self, _1: int) -> float
      """)
    convert_structural.log_info_mapping(mapping)
    six.assertCountEqual(self,
                         ["list", "typing.List", "typing.MutableSequence"],
                         mapping["~unknown1"])
    six.assertCountEqual(self,
                         ["float"],
                         mapping["~unknown1.__builtin__.list._T"])

  @unittest.skip("Moving to protocols")
  def test_two_lists(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def append(self: list, _1: NoneType) -> NoneType
      class `~unknown2`(object):
        def insert(self: list, _1: int, _2: float) -> NoneType
      """)
    six.assertCountEqual(self,
                         ["list", "typing.List", "typing.MutableSequence"],
                         mapping["~unknown1"])
    six.assertCountEqual(self,
                         ["list", "typing.List", "typing.MutableSequence"],
                         mapping["~unknown2"])
    six.assertCountEqual(self,
                         ["NoneType"], mapping["~unknown1.__builtin__.list._T"])
    six.assertCountEqual(self,
                         ["float"], mapping["~unknown2.__builtin__.list._T"])

  @unittest.skip("Moving to protocols")
  def test_float(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def __add__(self, _1: int) -> float
    """)
    six.assertCountEqual(self, ["float"], mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_or(self):
    mapping = self.parse_and_solve("""
      from typing import Iterator
      class `~unknown1`(object):
        def join(self, _1: unicode) -> unicode
        def join(self, _1: Iterator[str]) -> str
    """)
    six.assertCountEqual(self, ["str"], mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_multiple(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def __add__(self, _1: int) -> float
        def __add__(self, _1: float) -> float
      class `~unknown2`(object):
        def __add__(self, _1: str) -> bytearray
        def __add__(self, _1: bytearray) -> bytearray
      class `~unknown3`(object):
        def join(self, _1: str) -> str
        def join(self, _1: unicode) -> unicode
        def join(self, _1: iterator) -> str
      class `~unknown4`(object):
        def append(self, _1: NoneType) -> NoneType
    """)
    six.assertCountEqual(self, ["float"], mapping["~unknown1"])
    six.assertCountEqual(self, ["bytearray"], mapping["~unknown2"])
    six.assertCountEqual(self, ["str"], mapping["~unknown3"])
    six.assertCountEqual(self,
                         ["list", "typing.MutableSequence", "typing.List"],
                         mapping["~unknown4"])
    six.assertCountEqual(self,
                         ["NoneType"],
                         mapping["~unknown4.__builtin__.list._T"])

  @unittest.skip("Moving to protocols")
  def test_union(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def __add__(self, _1: int or float) -> float
      class `~unknown2`(object):
        def __add__(self, _1: bytearray) -> bytearray
    """)
    six.assertCountEqual(self, ["float"], mapping["~unknown1"])
    six.assertCountEqual(self, ["str", "bytearray"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_containers(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def foo(self, x: list[bool]) -> int
      class A(object):
        def foo(self, x: list[int]) -> int
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_type_parameters(self):
    mapping = self.parse_and_solve("""
      from typing import Generic
      T = TypeVar('T')
      class A(typing.Generic[T], object):
        def foo(self) -> ?
        def bar(self, x: T) -> ?
      class `~unknown1`(object):
        def foo(self) -> ?
        def bar(self, x: int) -> ?
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])
    six.assertCountEqual(self, ["int"], mapping["~unknown1.A.T"])

  @unittest.skip("Moving to protocols")
  def test_generic_against_generic(self):
    mapping = self.parse_and_solve("""
      class A():
        def f(self, x: list[int]) -> ?
        def g(self, x: list[float]) -> ?
      class B():
        def f(self, x: set[int]) -> ?
        def g(self, x: list[int]) -> ?
      class `~unknown1`(object):
        def f(self, x: list[int]) -> ?
      class `~unknown2`(object):
        def g(self, x: list[int]) -> ?
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])
    six.assertCountEqual(self, ["B"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_unknown_against_generic(self):
    mapping = self.parse_and_solve("""
      def f(A: `~unknown0`) -> list[`~unknown8`]
      class `~unknown0`():
        def has_key(self, _1: ?) -> ?
        def viewvalues(self) -> `~unknown2`
      class `~unknown2`():
        def __iter__(self) -> `~unknown4`
      class `~unknown4`():
        def next(self) -> `~unknown6`
      class `~unknown6`():
        def __sub__(self, _1: float) -> `~unknown8`
      class `~unknown8`():
        pass
    """)
    six.assertCountEqual(self, ["dict"], mapping["~unknown0"])
    self.assertContainsSubset(["complex", "float"],
                              mapping["~unknown0.__builtin__.dict._V"])
    six.assertCountEqual(self, ["dict_values"], mapping["~unknown2"])
    six.assertCountEqual(self,
                         ["dictionary-valueiterator"], mapping["~unknown4"])
    self.assertContainsSubset(["complex", "float"], mapping["~unknown6"])
    self.assertContainsSubset(["complex", "float"], mapping["~unknown8"])

  @unittest.skip("Moving to protocols")
  def test_subclass_of_elements(self):
    mapping = self.parse_and_solve("""
      class A():
        def f(self, x: list[int]) -> list[int]
      class `~unknown1`(object):
        def f(self, x: list[bool]) -> ?
      class `~unknown2`(object):
        def f(self, x: ?) -> list[object]
      class `~unknown3`(object):
        def f(self, x: list[object]) -> ?
      class `~unknown4`(object):
        def f(self, x: ?) -> list[bool]
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])
    six.assertCountEqual(self, [], mapping["~unknown2"])
    six.assertCountEqual(self, [], mapping["~unknown3"])
    six.assertCountEqual(self, ["A"], mapping["~unknown4"])

  @unittest.skip("Moving to protocols")
  def test_subclass(self):
    mapping = self.parse_and_solve("""
      class A():
        pass
      class B(A):
        pass
      class AA(object):
        def foo(self, x: A) -> A
      class AB(object):
        def foo(self, x: A) -> B
      class BA(object):
        def foo(self, x: B) -> A
      class BB(object):
        def foo(self, x: B) -> B
      class `~unknown1`(object):
        def foo(self, x: A) -> A
      class `~unknown2`(object):
        def foo(self, x: A) -> B
      class `~unknown3`(object):
        def foo(self, x: B) -> A
      class `~unknown4`(object):
        def foo(self, x: B) -> B
    """)
    six.assertCountEqual(self, ["AA"], mapping["~unknown1"])
    six.assertCountEqual(self, ["AA", "AB"], mapping["~unknown2"])
    six.assertCountEqual(self, ["AA", "BA"], mapping["~unknown3"])
    six.assertCountEqual(self, ["AA", "AB", "BA", "BB"], mapping["~unknown4"])

  @unittest.skip("Moving to protocols")
  def test_odd_superclass(self):
    mapping = self.parse_and_solve("""
      class A(nothing, nothing):
        def foobar(self) -> ?
      class B(?):
        def foobar(self) -> ?
      class C(A or B):
        def foobar(self) -> ?
      class D(list[int]):
        def foobar(self) -> ?
      T = TypeVar('T')
      class E(typing.Generic[T], T):
        def foobar(self) -> ?
      class `~unknown1`(object):
        def foobar(self) -> ?
    """)
    self.assertContainsSubset(["A", "B", "C", "D", "E"], mapping["~unknown1"])

  @unittest.skip("not implemented")
  def test_unknown_superclass(self):
    # E.g. "class A(x): def foobar(self): pass" with (unknown) x = type(3)
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        def __add__(self, _1: int) -> int
      class A(`~unknown1`):
        def foobar(self) -> NoneType
      class `~unknown2`(object):
        def __add__(self, _1: int) -> int
        def foobar(self) -> NoneType
    """)
    six.assertCountEqual(self, ["int", "bool"], mapping["~unknown1"])
    six.assertCountEqual(self, ["A"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_nothing(self):
    mapping = self.parse_and_solve("""
      class A():
        def f(self, x:nothing) -> nothing
      class B():
        def f(self, x:int) -> nothing
      class C():
        def f(self, x:nothing) -> int
      class D():
        def f(self, x:int) -> int
      class `~unknown1`(object):
        def f(self, x:nothing) -> nothing
      class `~unknown2`(object):
        def f(self, x:int) -> nothing
      class `~unknown3`(object):
        def f(self, x:nothing) -> int
      class `~unknown4`(object):
        def f(self, x:int) -> int
    """)
    six.assertCountEqual(self, ["A", "B", "C", "D"], mapping["~unknown1"])
    six.assertCountEqual(self, ["B", "D"], mapping["~unknown2"])
    six.assertCountEqual(self, ["C", "D"], mapping["~unknown3"])
    six.assertCountEqual(self, ["D"], mapping["~unknown4"])

  @unittest.skip("Moving to protocols")
  def test_unknown(self):
    mapping = self.parse_and_solve("""
      class A(?):
        def f(self, x:?) -> ?
      class B(?):
        def f(self, x:int) -> ?
      class C(?):
        def f(self, x:?) -> int
      class D(?):
        def f(self, x:int) -> int
      class `~unknown1`(object):
        def f(self, x:?) -> ?
        def f(self, x:int) -> ?
        def f(self, x:?) -> int
        def f(self, x:int) -> int
    """)
    convert_structural.log_info_mapping(mapping)
    six.assertCountEqual(self, ["A", "B", "C", "D"], mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_union_left_right(self):
    mapping = self.parse_and_solve("""
      class A(object):
        def f(self, x:int) -> int
      class B(object):
        def f(self, x:int) -> int or float
      class C(object):
        def f(self, x:int or float) -> int
      class D(object):
        def f(self, x:int or float) -> int or float
      class `~unknown1`(object):
        def f(self, x:int) -> int
      class `~unknown2`(object):
        def f(self, x:int or float) -> int
      class `~unknown3`(object):
        def f(self, x:int) -> int or float
    """)
    six.assertCountEqual(self, ["A", "B", "C", "D"], mapping["~unknown1"])
    six.assertCountEqual(self, ["C", "D"], mapping["~unknown2"])
    six.assertCountEqual(self, ["B", "D"], mapping["~unknown3"])

  @unittest.skip("Moving to protocols")
  def test_different_lengths(self):
    mapping = self.parse_and_solve("""
      class A(object):
        def f(self) -> ?
      class B(object):
        def f(self, x) -> ?
      class C(object):
        def f(self, x, y) -> ?
      class `~unknown1`(object):
        def f(self) -> ?
      class `~unknown2`(object):
        def f(self, x) -> ?
      class `~unknown3`(object):
        def f(self, x, y) -> ?
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])
    six.assertCountEqual(self, ["B"], mapping["~unknown2"])
    six.assertCountEqual(self, ["C"], mapping["~unknown3"])

  @unittest.skip("Moving to protocols")
  def test_filter(self):
    mapping = self.parse_and_solve("""
      class A(object):
        def f(self, x: int or bytearray) -> ?
      class `~unknown1`(object):
        def f(self, _1: `~unknown2`) -> ?
      class `~unknown2`(object):
        def capitalize(self) -> ?
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])
    six.assertCountEqual(self, ["bytearray"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_partial(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        pass
      class `~__builtin__~bool`(object):
        def __and__(self, _1: `~unknown1`) -> bool
        def __and__(self, _1: `~unknown2`) -> bool
      class `~unknown2`(object):
        pass
    """)
    six.assertCountEqual(self, ["bool", "int"], mapping["~unknown1"])
    six.assertCountEqual(self, ["bool", "int"], mapping["~unknown2"])

  @unittest.skip("Moving to protocols")
  def test_optional_parameters(self):
    mapping = self.parse_and_solve("""
      class A(object):
        def f(self, ...) -> ?
      class B(object):
        def f(self, x, ...) -> ?
      class C(object):
        def f(self, x, y, ...) -> ?
      class `~unknown1`(object):
        def f(self) -> ?
      class `~unknown2`(object):
        def f(self, x) -> ?
      class `~unknown3`(object):
        def f(self, x, y) -> ?
      class `~unknown4`(object):
        def f(self, x, y, z) -> ?
    """)
    six.assertCountEqual(self, ["A"], mapping["~unknown1"])
    six.assertCountEqual(self, ["A", "B"], mapping["~unknown2"])
    six.assertCountEqual(self, ["A", "B", "C"], mapping["~unknown3"])

  @unittest.skip("Moving to protocols")
  def test_listiterator(self):
    self.parse_and_solve("""
      class `~unknown1`(object):
        pass
      class `~__builtin__~listiterator`(object):
          def next(self) -> `~unknown1`
          def next(self) -> tuple[nothing, ...]
    """)

  @unittest.skip("Moving to protocols")
  def test_enumerate(self):
    self.parse_and_solve("""
      class `~unknown1`(object):
        pass
      class `~__builtin__~enumerate`(object):
          def __init__(self, iterable: list[`~unknown1`]) -> NoneType
          def next(self) -> tuple[?, ...]
    """)

  @unittest.skip("Moving to protocols")
  def test_call_builtin(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
        pass
      class `~unknown2`(object):
        pass
      def `~__builtin__~round`(number: `~unknown1`) -> `~unknown2`
    """)
    self.assertIn("float", mapping["~unknown1"])
    self.assertNotIn("str", mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_fibonacci(self):
    mapping = self.parse_and_solve("""
      def fib(n: `~unknown4`) -> int or `~unknown12`
      def fib(n: `~unknown8` or int) -> int
      def foo(x: `~unknown1`) -> `~unknown3` or int

      class `~__builtin__~int`(object):  # TODO(kramm): Make pytype add the ~
          def __xor__(self, y: int) -> `~unknown10`

      class `~unknown1`():
          def __add__(self, _1: int) -> `~unknown3`

      class `~unknown3`():
          pass

      class `~unknown4`():
          def __eq__(self, _1: int) -> `~unknown6`
          def __sub__(self, _1: int) -> `~unknown8`
          def __mul__(self, _1: int) -> `~unknown12`

      class `~unknown6`():
          pass

      class `~unknown8`():
          def __eq__(self, _1: int) -> `~unknown10`

      class `~unknown10`():
          pass

      class `~unknown12`():
          pass
    """)
    six.assertCountEqual(self,
                         ["int", "bool", "float", "complex"],
                         mapping["~unknown4"])

  @unittest.skip("Moving to protocols")
  def test_add(self):
    mapping = self.parse_and_solve("""
      def f(self, x: `~unknown4`) -> `~unknown6`

      class `~unknown4`():
          def __add__(self, _1: int) -> `~unknown6`

      class `~unknown6`():
          pass
    """)
    numbers = ["int", "complex", "float", "bool"]
    six.assertCountEqual(self, numbers, mapping["~unknown4"])
    six.assertCountEqual(self, numbers, mapping["~unknown6"])

  @unittest.skip("Moving to protocols")
  def test_subclasses(self):
    mapping = self.parse_and_solve("""
      class Foo(object):
        def foo(self) -> Bar1

      class Bar1(object):
        def bar(self) -> complex

      class Bar2(Bar1):
        def bar(self) -> float

      class `~unknown1`(object):
        def foo(self) -> `~unknown2`

      class `~unknown2`(object):
        def bar(self) -> `~unknown3`

      class `~unknown3`(object):
        pass
    """)
    six.assertCountEqual(self, ["complex", "float"], mapping["~unknown3"])

  @unittest.skip("Moving to protocols")
  def test_match_builtin_function(self):
    mapping = self.parse_and_solve("""
      def baz(int) -> float
      def baz(complex) -> complex
      def `~baz`(_1: `~unknown3`) -> `~unknown4`

      class `~unknown3`(object):
        pass

      class `~unknown4`(object):
        pass
    """)
    six.assertCountEqual(self, ["complex", "float"], mapping["~unknown4"])

  @unittest.skip("Moving to protocols")
  def test_match_builtin_class(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`(object):
          pass
      class `~unknown2`(object):
          pass

      T = TypeVar('T')
      N = TypeVar('N')
      class mylist(typing.Generic[T], object):
        def __setitem__(self, i: int, y: N) -> NoneType:
          self = mylist[T or N]

      class `~mylist`():
        def __setitem__(self, i: int, y: `~unknown2`) -> `~unknown1`
    """)
    six.assertCountEqual(self, ["NoneType"], mapping["~unknown1"])

  @unittest.skip("Moving to protocols")
  def test_subclasses2(self):
    mapping = self.parse_and_solve("""
      class Foo(object):
        def foo(self) -> Bar1

      class Bar1(object):
        def bar(self) -> Bar1

      class Bar2(Bar1):
        def bar(self) -> Bar2

      def baz(x: Bar1) -> complex
      def baz(x: Bar2) -> float
      def `~baz`(x: `~unknown3`) -> `~unknown4`

      class `~unknown1`(object):
        def foo(self) -> `~unknown2`

      class `~unknown2`(object):
        def bar(self) -> `~unknown3`

      class `~unknown3`(object):
        pass

      class `~unknown4`(object):
        pass
    """)
    six.assertCountEqual(self, ["complex", "float"], mapping["~unknown4"])

  @unittest.skip("Moving to protocols")
  def test_convert(self):
    ast = self.parse("""
      class A(object):
          def foo(self, x: `~unknown1`) -> ?
          def foobaz(self, x: int) -> int
      class `~unknown1`(object):
          def foobaz(self, x: int) -> int
    """)
    expected = textwrap.dedent("""
      from typing import Any

      class A(object):
          def foo(self, x: A) -> Any: ...
          def foobaz(self, x: int) -> int: ...
    """).lstrip()
    ast = convert_structural.convert_pytd(ast, self.builtins_pytd)
    self.assertMultiLineEqual(pytd.Print(ast), expected)

  @unittest.skip("Moving to protocols")
  def test_convert_with_type_params(self):
    ast = self.parse("""
      from typing import Dict
      class A(object):
          def foo(self, x: `~unknown1`) -> bool

      class `~unknown1`():
          def __setitem__(self, _1: str, _2: `~unknown2`) -> ?
          def update(self, _1: NoneType or Dict[nothing, nothing]) -> ?

      class `~unknown2`():
          def append(self, _1:NoneType) -> NoneType
    """)
    ast = convert_structural.convert_pytd(ast, self.builtins_pytd)
    x = ast.Lookup("A").Lookup("foo").signatures[0].params[1].type
    self.assertIn("MutableSequence", pytd.Print(x))

  @unittest.skip("Moving to protocols")
  def test_isinstance(self):
    ast = self.parse("""
      x = ...  # type: `~unknown1`
      def `~__builtin__~isinstance`(object: int, class_or_type_or_tuple: tuple[nothing, ...]) -> `~unknown1`
      class `~unknown1`(object):
        pass
    """)
    expected = textwrap.dedent("""
      x = ...  # type: bool
    """).strip()
    ast = convert_structural.convert_pytd(ast, self.builtins_pytd)
    self.assertMultiLineEqual(pytd.Print(ast), expected)

  @unittest.skip("Moving to protocols")
  def test_match_superclass(self):
    mapping = self.parse_and_solve("""
      class Base1():
        def f(self, x:Base1) -> Base2
      class Base2():
        def g(self) -> Base1
      class Foo(Base1, Base2):
        pass

      class `~unknown1`():
        def f(self, x:Base1) -> Base2
    """)
    six.assertCountEqual(self, ["Foo", "Base1"], mapping["~unknown1"])

if __name__ == "__main__":
  unittest.main()
