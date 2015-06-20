"""Test match.py."""

import textwrap
import unittest

from pytype import convert_structural
from pytype.pytd import pytd
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser
from pytype.tests import test_inference
import unittest


class MatchTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.builtins_pytd = builtins.GetBuiltinsPyTD()

  def parse(self, src):
    return parser.parse_string(textwrap.dedent(src))

  def parse_and_solve(self, src):
    types, _ = convert_structural.solve(self.parse(src),
                                        builtins_pytd=self.builtins_pytd)
    return types

  def test_simple(self):
    mapping = self.parse_and_solve("""
      class `~unknown2`:
        pass
      class `~unknown1`:
        def __add__(self, other: `~unknown2`) -> int
    """)
    self.assertItemsEqual(["int", "bool"], mapping["~unknown1"])
    self.assertItemsEqual(["int", "bool"], mapping["~unknown2"])

  def test_float_and_bytearray(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def __add__(self, y: int) -> float
        def __add__(self, y: float) -> float
      class `~unknown2`:
        def __add__(self, y: str) -> bytearray
        def __add__(self, y: bytearray) -> bytearray
      """)
    self.assertItemsEqual(["float"], mapping["~unknown1"])
    self.assertItemsEqual(["bytearray"], mapping["~unknown2"])

  def test_float_and_bytearray2(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def __add__(self, y: int or float) -> float
      class `~unknown2`:
        def __add__(self, y: bytearray) -> bytearray
      """)
    self.assertItemsEqual(["float"], mapping["~unknown1"])
    self.assertItemsEqual(["bytearray"], mapping["~unknown2"])

  def test_append(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def append(self, v: int) -> NoneType
    """)
    self.assertItemsEqual(["list", "bytearray"], mapping["~unknown1"])

  def test_single_list(self):
    # Differs from test_append in that append(float) doesn't match bytearray
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def append(self, v: float) -> NoneType
    """)
    convert_structural.log_info_mapping(mapping)
    self.assertItemsEqual(["list"], mapping["~unknown1"])
    self.assertItemsEqual(["float"], mapping["~unknown1.list.T"])

  def test_list(self):
    mapping = self.parse_and_solve("""
      class `~unknown2`:
        def append(self, v: `~unknown1`) -> NoneType
        def __getitem__(self, i: ?) -> `~unknown1`

      class `~unknown1`:
        def __add__(self: float, y: int) -> float
        def __add__(self: float, y: float) -> float
      """)
    convert_structural.log_info_mapping(mapping)
    self.assertItemsEqual(["float"], mapping["~unknown1"])
    self.assertItemsEqual(["list"], mapping["~unknown2"])
    self.assertItemsEqual(["float"], mapping["~unknown2.list.T"])

  def test_float_list(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def append(self, v: ?) -> NoneType
        def __getitem__(self, i: int) -> float
      """)
    convert_structural.log_info_mapping(mapping)
    self.assertItemsEqual(["list"], mapping["~unknown1"])
    self.assertItemsEqual(["float"], mapping["~unknown1.list.T"])

  def test_two_lists(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def append(self: list, v: NoneType) -> NoneType
      class `~unknown2`:
        def remove(self: list, v: float) -> NoneType
      """)
    self.assertItemsEqual(["list"], mapping["~unknown1"])
    self.assertItemsEqual(["list"], mapping["~unknown2"])
    self.assertItemsEqual(["NoneType"], mapping["~unknown1.list.T"])
    self.assertItemsEqual(["float"], mapping["~unknown2.list.T"])

  def test_float(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def __add__(self, v: int) -> float
    """)
    self.assertItemsEqual(["float"], mapping["~unknown1"])

  def test_or(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def join(self, iterable: unicode) -> str or unicode
        def join(self, iterable: iterator) -> str or unicode
    """)
    self.assertItemsEqual(["str"], mapping["~unknown1"])

  def test_multiple(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def __add__(self, y: int) -> float
        def __add__(self, y: float) -> float
      class `~unknown2`:
        def __add__(self, y: str) -> bytearray
        def __add__(self, y: bytearray) -> bytearray
      class `~unknown3`:
        def join(self, iterable) -> str
        def join(self, iterable: unicode) -> str or unicode
        def join(self, iterable: iterator) -> str or unicode
      class `~unknown4`:
        def append(self, v: NoneType) -> NoneType
    """)
    self.assertItemsEqual(["float"], mapping["~unknown1"])
    self.assertItemsEqual(["bytearray"], mapping["~unknown2"])
    self.assertItemsEqual(["str"], mapping["~unknown3"])
    self.assertItemsEqual(["list"], mapping["~unknown4"])
    self.assertItemsEqual(["NoneType"], mapping["~unknown4.list.T"])

  def test_union(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def __add__(self, x:int or float) -> float
      class `~unknown2`:
        def __add__(self, x:bytearray) -> bytearray
    """)
    self.assertItemsEqual(["float"], mapping["~unknown1"])
    self.assertItemsEqual(["bytearray"], mapping["~unknown2"])

  def test_containers(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def foo(self, x: list<bool>) -> int
      class A(object):
        def foo(self, x: list<int>) -> int
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])

  def test_type_parameters(self):
    mapping = self.parse_and_solve("""
      class A<T>:
        def foo(self) -> ?
        def bar(self, x: T) -> ?
      class `~unknown1`:
        def foo(self) -> ?
        def bar(self, x: int) -> ?
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual(["int"], mapping["~unknown1.A.T"])

  def test_generic_against_generic(self):
    mapping = self.parse_and_solve("""
      class A(nothing):
        def f(self, x: list<int>) -> ?
        def g(self, x: list<float>) -> ?
      class B(nothing):
        def f(self, x: set<int>) -> ?
        def g(self, x: list<int>) -> ?
      class `~unknown1`:
        def f(self, x: list<int>) -> ?
      class `~unknown2`:
        def g(self, x: list<int>) -> ?
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual(["B"], mapping["~unknown2"])

  def test_unknown_against_generic(self):
    mapping = self.parse_and_solve("""
      def f(A: `~unknown0`) -> list<`~unknown8`>
      class `~unknown0`(nothing):
        def values(self) -> `~unknown2`
      class `~unknown2`(nothing):
        def __iter__(self) -> `~unknown4`
      class `~unknown4`(nothing):
        def next(self) -> `~unknown6`
      class `~unknown6`(nothing):
        def __sub__(self, _1: float) -> `~unknown8`
      class `~unknown8`(nothing):
        pass
    """)
    self.assertItemsEqual(["dict"], mapping["~unknown0"])
    self.assertContainsSubset(["complex", "float"], mapping["~unknown0.dict.V"])
    self.assertItemsEqual(["list"], mapping["~unknown2"])
    self.assertItemsEqual(["listiterator"], mapping["~unknown4"])
    self.assertContainsSubset(["complex", "float"], mapping["~unknown6"])
    self.assertContainsSubset(["complex", "float"], mapping["~unknown8"])

  def test_subclass_of_elements(self):
    mapping = self.parse_and_solve("""
      class A(nothing):
        def f(self, x: list<int>) -> list<int>
      class `~unknown1`:
        def f(self, x: list<bool>) -> ?
      class `~unknown2`:
        def f(self, x: ?) -> list<object>
      class `~unknown3`:
        def f(self, x: list<object>) -> ?
      class `~unknown4`:
        def f(self, x: ?) -> list<bool>
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual([], mapping["~unknown2"])
    self.assertItemsEqual([], mapping["~unknown3"])
    self.assertItemsEqual(["A"], mapping["~unknown4"])

  def test_subclass(self):
    mapping = self.parse_and_solve("""
      class A(nothing):
        pass
      class B(A):
        pass
      class AA:
        def foo(self, x: A) -> A
      class AB:
        def foo(self, x: A) -> B
      class BA:
        def foo(self, x: B) -> A
      class BB:
        def foo(self, x: B) -> B
      class `~unknown1`:
        def foo(self, x: A) -> A
      class `~unknown2`:
        def foo(self, x: A) -> B
      class `~unknown3`:
        def foo(self, x: B) -> A
      class `~unknown4`:
        def foo(self, x: B) -> B
    """)
    self.assertItemsEqual(["AA"], mapping["~unknown1"])
    self.assertItemsEqual(["AA", "AB"], mapping["~unknown2"])
    self.assertItemsEqual(["AA", "BA"], mapping["~unknown3"])
    self.assertItemsEqual(["AA", "AB", "BA", "BB"], mapping["~unknown4"])

  def test_odd_superclass(self):
    mapping = self.parse_and_solve("""
      class A(nothing, nothing):
        def foobar(self) -> ?
      class B(?):
        def foobar(self) -> ?
      class C(A or B):
        def foobar(self) -> ?
      class D(list<int>):
        def foobar(self) -> ?
      class E<T>(T):
        def foobar(self) -> ?
      class `~unknown1`:
        def foobar(self) -> ?
    """)
    self.assertContainsSubset(["A", "B", "C", "D", "E"], mapping["~unknown1"])

  @unittest.skip("not implemented")
  def test_unknown_superclass(self):
    # E.g. "class A(x): def foobar(self): pass" with (unknown) x = type(3)
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        def __add__(self, _1: int) -> int
      class `~A`(`~unknown1`):
        def foobar(self) -> NoneType
      class `~unknown2`:
        def __add__(self, _1: int) -> int
        def __sub__(self, _1: int) -> int
        def foobar(self) -> NoneType
    """)
    self.assertItemsEqual(["int"], mapping["~unknown1"])
    self.assertItemsEqual(["A"], mapping["~unknown2"])

  def test_nothing(self):
    mapping = self.parse_and_solve("""
      class A(nothing):
        def f(self, x:nothing) -> nothing
      class B(nothing):
        def f(self, x:int) -> nothing
      class C(nothing):
        def f(self, x:nothing) -> int
      class D(nothing):
        def f(self, x:int) -> int
      class `~unknown1`:
        def f(self, x:nothing) -> nothing
      class `~unknown2`:
        def f(self, x:int) -> nothing
      class `~unknown3`:
        def f(self, x:nothing) -> int
      class `~unknown4`:
        def f(self, x:int) -> int
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual(["B"], mapping["~unknown2"])
    self.assertItemsEqual(["C"], mapping["~unknown3"])
    self.assertItemsEqual(["D"], mapping["~unknown4"])

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
      class `~unknown1`:
        def f(self, x:?) -> ?
        def f(self, x:int) -> ?
        def f(self, x:?) -> int
        def f(self, x:int) -> int
    """)
    convert_structural.log_info_mapping(mapping)
    self.assertItemsEqual(["A", "B", "C", "D"], mapping["~unknown1"])

  def test_union_left_right(self):
    mapping = self.parse_and_solve("""
      class A:
        def f(self, x:int) -> int
      class B:
        def f(self, x:int) -> int or float
      class C:
        def f(self, x:int or float) -> int
      class D:
        def f(self, x:int or float) -> int or float
      class `~unknown1`:
        def f(self, x:int) -> int
      class `~unknown2`:
        def f(self, x:int or float) -> int
      class `~unknown3`:
        def f(self, x:int) -> int or float
    """)
    self.assertItemsEqual(["A", "B", "C", "D"], mapping["~unknown1"])
    self.assertItemsEqual(["C", "D"], mapping["~unknown2"])
    self.assertItemsEqual(["B", "D"], mapping["~unknown3"])

  def test_different_lengths(self):
    mapping = self.parse_and_solve("""
      class A:
        def f(self) -> ?
      class B:
        def f(self, x) -> ?
      class C:
        def f(self, x, y) -> ?
      class `~unknown1`:
        def f(self) -> ?
      class `~unknown2`:
        def f(self, x) -> ?
      class `~unknown3`:
        def f(self, x, y) -> ?
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual(["B"], mapping["~unknown2"])
    self.assertItemsEqual(["C"], mapping["~unknown3"])

  def test_filter(self):
    mapping = self.parse_and_solve("""
      class A:
        def f(self, x: int or bytearray) -> ?
      class `~unknown1`:
        def f(self, _1: `~unknown2`) -> ?
      class `~unknown2`:
        def capitalize(self) -> ?
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual(["bytearray"], mapping["~unknown2"])

  def test_partial(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        pass
      class `~bool`:
        def __and__(self, _1: `~unknown1`) -> bool
        def __and__(self, _1: `~unknown2`) -> bool
      class `~unknown2`:
        pass
    """)
    self.assertItemsEqual(["bool", "int"], mapping["~unknown1"])
    self.assertItemsEqual(["bool", "int"], mapping["~unknown2"])

  def test_optional_parameters(self):
    mapping = self.parse_and_solve("""
      class A:
        def f(self, ...) -> ?
      class B:
        def f(self, x, ...) -> ?
      class C:
        def f(self, x, y, ...) -> ?
      class `~unknown1`:
        def f(self) -> ?
      class `~unknown2`:
        def f(self, x) -> ?
      class `~unknown3`:
        def f(self, x, y) -> ?
      class `~unknown4`:
        def f(self, x, y, z) -> ?
    """)
    self.assertItemsEqual(["A"], mapping["~unknown1"])
    self.assertItemsEqual(["A", "B"], mapping["~unknown2"])
    self.assertItemsEqual(["A", "B", "C"], mapping["~unknown3"])

  def test_listiterator(self):
    self.parse_and_solve("""
      class `~unknown1`:
        pass
      class `~listiterator`:
          def next(self) -> `~unknown1`
          def next(self) -> tuple<nothing>
    """)

  def test_enumerate(self):
    self.parse_and_solve("""
      class `~unknown1`:
        pass
      class `~enumerate`:
          def __init__(self, iterable: list<`~unknown1`>) -> NoneType
          def next(self) -> tuple<?>
    """)

  @unittest.skip("not implemented")
  def test_call_builtin(self):
    mapping = self.parse_and_solve("""
      class `~unknown1`:
        pass
      class `~unknown2`:
        pass
      def round(number: `~unknown1`) -> `~unknown2`
    """)
    self.assertIn("float", mapping["~unknown1"])
    self.assertNotIn("str", mapping["~unknown1"])

  def test_fibonacci(self):
    mapping = self.parse_and_solve("""
      def fib(n: `~unknown4`) -> int or `~unknown12`
      def fib(n: `~unknown8` or int) -> int
      def foo(x: `~unknown1`) -> `~unknown3` or int

      class `~int`:  # TODO(kramm): Make pytype add the ~
          def __rmul__(self, y: `~unknown4`) -> int
          def __eq__(self, y: int) -> `~unknown10` or bool
          def __radd__(self, y: `~unknown1`) -> int
          def __rsub__(self, y: `~unknown4`) -> int

      class `~unknown1`(nothing):
          def __add__(self, _1: int) -> `~unknown3`

      class `~unknown3`(nothing):
          pass

      class `~unknown4`(nothing):
          def __eq__(self, _1: int) -> `~unknown6`
          def __sub__(self, _1: int) -> `~unknown8`
          def __mul__(self, _1: int) -> `~unknown12`

      class `~unknown6`(nothing):
          pass

      class `~unknown8`(nothing):
          def __eq__(self, _1: int) -> `~unknown10`

      class `~unknown10`(nothing):
          pass

      class `~unknown12`(nothing):
          pass
    """)
    self.assertItemsEqual(["int"], mapping["~unknown4"])

  def test_add(self):
    mapping = self.parse_and_solve("""
      def f(self, x: `~unknown4`) -> `~unknown6`

      class `~unknown4`(nothing):
          def __add__(self, _1: int) -> `~unknown6`

      class `~unknown6`(nothing):
          pass
    """)
    # TODO(pludemann): remove "bool" from list when we do the
    # more strict definition of return (that is, not allowing
    # "bool" just because it's a subclass of "int" in __builtin__.pytd
    numbers = ["int", "complex", "float", "long", "bool"]
    self.assertItemsEqual(numbers, mapping["~unknown4"])
    self.assertItemsEqual(numbers, mapping["~unknown6"])

  def test_subclasses(self):
    mapping = self.parse_and_solve("""
      class Foo:
        def foo(self) -> Bar1

      class Bar1:
        def bar(self) -> complex

      class Bar2(Bar1):
        def bar(self) -> float

      class `~unknown1`:
        def foo(self) -> `~unknown2`

      class `~unknown2`:
        def bar(self) -> `~unknown3`

      class `~unknown3`:
        pass
    """)
    self.assertItemsEqual(["complex", "float"], mapping["~unknown3"])

  def test_match_builtin_function(self):
    mapping = self.parse_and_solve("""
      def baz(int) -> float
      def baz(complex) -> complex
      def `~baz`(`~unknown3`) -> `~unknown4`

      class `~unknown3`:
        pass

      class `~unknown4`:
        pass
    """)
    self.assertItemsEqual(["complex", "float"], mapping["~unknown4"])

  def test_subclasses2(self):
    mapping = self.parse_and_solve("""
      class Foo:
        def foo(self) -> Bar1

      class Bar1:
        def bar(self) -> Bar1

      class Bar2(Bar1):
        def bar(self) -> Bar2

      def baz(Bar1) -> complex
      def baz(Bar2) -> float
      def `~baz`(`~unknown3`) -> `~unknown4`

      class `~unknown1`:
        def foo(self) -> `~unknown2`

      class `~unknown2`:
        def bar(self) -> `~unknown3`

      class `~unknown3`:
        pass

      class `~unknown4`:
        pass
    """)
    self.assertItemsEqual(["complex", "float"], mapping["~unknown4"])

  def test_convert(self):
    sourcecode = textwrap.dedent("""
      class A:
          def foo(self, x: `~unknown1`) -> ?
          def foobaz(self, x: int) -> int
      class `~unknown1`:
          def foobaz(self, x: int) -> int
    """)
    expected = textwrap.dedent("""
      class A:
          def foo(self, x: A) -> ?
          def foobaz(self, x: int) -> int
    """).lstrip()
    ast = parser.parse_string(sourcecode)
    ast = convert_structural.convert_pytd(ast, self.builtins_pytd)
    self.assertMultiLineEqual(pytd.Print(ast), expected)

  def test_convert_with_type_params(self):
    sourcecode = textwrap.dedent("""
      class A:
          def foo(self, x: `~unknown1`) -> bool

      class `~unknown1`(nothing):
          def __setitem__(self, _1: str, _2: `~unknown2`) -> ?
          def update(self, _1: NoneType or dict<nothing, nothing>) -> ?

      class `~unknown2`(nothing):
          def append(self, v:NoneType) -> NoneType
    """)
    expected = textwrap.dedent("""
      class A:
          def foo(self, x: dict<str, list<?>>) -> bool
    """).lstrip()
    ast = parser.parse_string(sourcecode)
    ast = convert_structural.convert_pytd(ast, self.builtins_pytd)
    self.assertMultiLineEqual(pytd.Print(ast), expected)

if __name__ == "__main__":
  test_inference.main(debugging=False)
