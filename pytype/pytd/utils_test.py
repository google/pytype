# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import textwrap
import unittest
from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser_test_base
from pytype.pytd.parse import visitors


class TestUtils(parser_test_base.ParserTest):
  """Test pytype.pytd.utils."""

  def testUnpackUnion(self):
    """Test for UnpackUnion."""
    ast = self.Parse("""
      c1 = ...  # type: int or float
      c2 = ...  # type: int
      c3 = ...  # type: list[int or float]""")
    c1 = ast.Lookup("c1").type
    c2 = ast.Lookup("c2").type
    c3 = ast.Lookup("c3").type
    self.assertItemsEqual(utils.UnpackUnion(c1), c1.type_list)
    self.assertItemsEqual(utils.UnpackUnion(c2), [c2])
    self.assertItemsEqual(utils.UnpackUnion(c3), [c3])

  def testConcat(self):
    """Test for concatenating two pytd ASTs."""
    ast1 = self.Parse("""
      c1 = ...  # type: int

      def f1() -> int

      class Class1(object):
        pass
    """)
    ast2 = self.Parse("""
      c2 = ...  # type: int

      def f2() -> int

      class Class2(object):
        pass
    """)
    expected = textwrap.dedent("""
      c1 = ...  # type: int
      c2 = ...  # type: int

      def f1() -> int
      def f2() -> int

      class Class1(object):
          pass

      class Class2(object):
          pass
    """)
    combined = utils.Concat(ast1, ast2)
    self.AssertSourceEquals(combined, expected)

  def testConcat3(self):
    """Test for concatenating three pytd ASTs."""
    ast1 = self.Parse("""c1 = ...  # type: int""")
    ast2 = self.Parse("""c2 = ...  # type: float""")
    ast3 = self.Parse("""c3 = ...  # type: bool""")
    combined = utils.Concat(ast1, ast2, ast3)
    expected = textwrap.dedent("""
      c1 = ...  # type: int
      c2 = ...  # type: float
      c3 = ...  # type: bool
    """)
    self.AssertSourceEquals(combined, expected)

  def testConcatTypeParameters(self):
    """Test for concatenating ASTs with type parameters."""
    ast1 = self.Parse("""T = TypeVar("T")""", name="__builtin__")
    ast2 = self.Parse("""T = TypeVar("T")""")
    combined = utils.Concat(ast1, ast2)
    self.assertEquals(combined.Lookup("__builtin__.T"),
                      pytd.TypeParameter("T", scope="__builtin__"))
    self.assertEquals(combined.Lookup("T"), pytd.TypeParameter("T", scope=None))

  def testJoinTypes(self):
    """Test that JoinTypes() does recursive flattening."""
    n1, n2, n3, n4, n5, n6 = [pytd.NamedType("n%d" % i) for i in xrange(6)]
    # n1 or (n2 or (n3))
    nested1 = pytd.UnionType((n1, pytd.UnionType((n2, pytd.UnionType((n3,))))))
    # ((n4) or n5) or n6
    nested2 = pytd.UnionType((pytd.UnionType((pytd.UnionType((n4,)), n5)), n6))
    joined = utils.JoinTypes([nested1, nested2])
    self.assertEquals(joined.type_list,
                      (n1, n2, n3, n4, n5, n6))

  def testJoinSingleType(self):
    """Test that JoinTypes() returns single types as-is."""
    a = pytd.NamedType("a")
    self.assertEquals(utils.JoinTypes([a]), a)
    self.assertEquals(utils.JoinTypes([a, a]), a)

  def testJoinNothingType(self):
    """Test that JoinTypes() removes or collapses 'nothing'."""
    a = pytd.NamedType("a")
    nothing = pytd.NothingType()
    self.assertEquals(utils.JoinTypes([a, nothing]), a)
    self.assertEquals(utils.JoinTypes([nothing]), nothing)
    self.assertEquals(utils.JoinTypes([nothing, nothing]), nothing)

  def testJoinEmptyTypesToNothing(self):
    """Test that JoinTypes() simplifies empty unions to 'nothing'."""
    self.assertIsInstance(utils.JoinTypes([]), pytd.NothingType)

  def testJoinAnythingTypes(self):
    """Test that JoinTypes() simplifies unions containing '?'."""
    types = [pytd.AnythingType(), pytd.NamedType("a")]
    self.assertIsInstance(utils.JoinTypes(types), pytd.AnythingType)

  def testTypeMatcher(self):
    """Test for the TypeMatcher class."""

    class MyTypeMatcher(utils.TypeMatcher):

      def default_match(self, t1, t2, mykeyword):
        assert mykeyword == "foobar"
        return t1 == t2

      def match_Function_against_Function(self, f1, f2, mykeyword):
        assert mykeyword == "foobar"
        return all(self.match(sig1, sig2, mykeyword)
                   for sig1, sig2 in zip(f1.signatures, f2.signatures))

    s1 = pytd.Signature((), None, None, pytd.NothingType(), (), ())
    s2 = pytd.Signature((), None, None, pytd.AnythingType(), (), ())
    self.assertTrue(MyTypeMatcher().match(
        pytd.Function("f1", (s1, s2), pytd.METHOD),
        pytd.Function("f2", (s1, s2), pytd.METHOD),
        mykeyword="foobar"))
    self.assertFalse(MyTypeMatcher().match(
        pytd.Function("f1", (s1, s2), pytd.METHOD),
        pytd.Function("f2", (s2, s2), pytd.METHOD),
        mykeyword="foobar"))

  def testPrint(self):
    """Smoketest for printing pytd."""
    ast = self.Parse("""
      c1 = ...  # type: int
      T = TypeVar('T')
      class A(typing.Generic[T], object):
        bar = ...  # type: T
        def foo(self, x: list[int], y: T) -> list[T] or float:
          raise ValueError()
      X = TypeVar('X')
      Y = TypeVar('Y')
      def bar(x: X or Y) -> ?
    """)
    # TODO(kramm): Do more extensive testing.
    utils.Print(ast)

  def testNamedTypeWithModule(self):
    """Test NamedTypeWithModule()."""
    self.assertEquals(utils.NamedTypeWithModule("name"), pytd.NamedType("name"))
    self.assertEquals(utils.NamedTypeWithModule("name", None),
                      pytd.NamedType("name"))
    self.assertEquals(utils.NamedTypeWithModule("name", "package"),
                      pytd.NamedType("package.name"))

  def testOrderedSet(self):
    ordered_set = utils.OrderedSet(n/2 for n in range(10))
    ordered_set.add(-42)
    ordered_set.add(3)
    self.assertEquals(tuple(ordered_set), (0, 1, 2, 3, 4, -42))

  def testWrapTypeDeclUnit(self):
    """Test WrapTypeDeclUnit."""
    ast1 = self.Parse("""
      c = ...  # type: int
      def f(x: int) -> int
      def f(x: float) -> float
      class A(object):
        pass
    """)
    ast2 = self.Parse("""
      c = ...  # type: float
      d = ...  # type: int
      def f(x: complex) -> complex
      class B(object):
        pass
    """)
    w = utils.WrapTypeDeclUnit(
        "combined",
        ast1.classes + ast1.functions + ast1.constants +
        ast2.classes + ast2.functions + ast2.constants)
    expected = textwrap.dedent("""
      c = ...  # type: int or float
      d = ...  # type: int
      def f(x: int) -> int
      def f(x: float) -> float
      def f(x: complex) -> complex
      class A(object):
        pass
      class B(object):
        pass
    """)
    self.AssertSourceEquals(w, expected)

  def testWrapsDict(self):
    class A(utils.WrapsDict("m")):
      pass
    a = A()
    a.m = {}
    a.m = {"foo": 1, "bar": 2}
    self.assertEquals(a.get("x", "baz"), "baz")
    self.assertFalse("x" in a)
    self.assertEquals(a.get("foo"), 1)
    self.assertEquals(a["foo"], 1)
    self.assertTrue(a.has_key("foo"))
    self.assertTrue("foo" in a)
    self.assertTrue("bar" in a)
    self.assertEquals(a.copy(), a.m)
    self.assertItemsEqual(iter(a), ["foo", "bar"])
    self.assertItemsEqual(a.keys(), ["foo", "bar"])
    self.assertItemsEqual(a.viewkeys(), ["foo", "bar"])
    self.assertItemsEqual(a.iterkeys(), ["foo", "bar"])
    self.assertItemsEqual(a.values(), [1, 2])
    self.assertItemsEqual(a.viewvalues(), [1, 2])
    self.assertItemsEqual(a.itervalues(), [1, 2])
    self.assertItemsEqual(a.items(), [("foo", 1), ("bar", 2)])
    self.assertItemsEqual(a.viewitems(), [("foo", 1), ("bar", 2)])
    self.assertItemsEqual(a.iteritems(), [("foo", 1), ("bar", 2)])
    self.assertFalse(hasattr(a, "popitem"))

  def testWrapsWritableDict(self):
    class A(utils.WrapsDict("m", writable=True)):
      pass
    a = A()
    a.m = {}
    a.m = {"foo": 1, "bar": 2}
    self.assertTrue(a.has_key("foo"))
    self.assertTrue(a.has_key("bar"))
    del a["foo"]
    a["bar"] = 3
    self.assertFalse(a.has_key("foo"))
    self.assertTrue(a.has_key("bar"))
    value = a.pop("bar")
    self.assertEquals(3, value)
    self.assertFalse(a.has_key("bar"))
    a["new"] = 7
    item = a.popitem()
    self.assertEquals(item, ("new", 7))
    a["1"] = 1
    a.setdefault("1", 11)
    a.setdefault("2", 22)
    self.assertEquals(a["1"], 1)
    self.assertEquals(a["2"], 22)
    a.update({"3": 33})
    self.assertItemsEqual(a.items(), (("1", 1), ("2", 22), ("3", 33)))
    a.clear()
    self.assertItemsEqual(a.items(), ())

  def testWrapsDictWithLength(self):
    class A(utils.WrapsDict("m", implement_len=True)):
      pass
    a = A()
    a.m = {x: x for x in range(42)}
    self.assertEquals(42, len(a))

  def testDedup(self):
    self.assertEquals([], utils.Dedup([]))
    self.assertEquals([1], utils.Dedup([1]))
    self.assertEquals([1, 2], utils.Dedup([1, 2]))
    self.assertEquals([1, 2], utils.Dedup([1, 2, 1]))
    self.assertEquals([1, 2], utils.Dedup([1, 1, 2, 2]))
    self.assertEquals([3, 2, 1], utils.Dedup([3, 2, 1, 3]))

  def testMROMerge(self):
    self.assertEquals([], utils.MROMerge([[], []]))
    self.assertEquals([1], utils.MROMerge([[], [1]]))
    self.assertEquals([1], utils.MROMerge([[1], []]))
    self.assertEquals([1, 2], utils.MROMerge([[1], [2]]))
    self.assertEquals([1, 2], utils.MROMerge([[1, 2], [2]]))
    self.assertEquals([1, 2, 3, 4], utils.MROMerge([[1, 2, 3], [2, 4]]))
    self.assertEquals([1, 2, 3], utils.MROMerge([[1, 2], [1, 2, 3]]))
    self.assertEquals([1, 2], utils.MROMerge([[1, 1], [2, 2]]))
    self.assertEquals([1, 2, 3, 4, 5, 6],
                      utils.MROMerge([[1, 3, 5], [2, 3, 4], [4, 5, 6]]))
    self.assertEquals([1, 2, 3], utils.MROMerge([[1, 2, 1], [2, 3, 2]]))

  def testGetBasesInMRO(self):
    ast = parser.parse_string(textwrap.dedent("""
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class Foo(Generic[T]): pass
      class Bar(Foo[int]): pass
    """))
    b, t = builtins.GetBuiltinsAndTyping()
    ast = ast.Visit(visitors.LookupExternalTypes(
        {"__builtin__": b, "typing": t}, full_names=True))
    ast = ast.Visit(visitors.NamedTypeToClassType())
    mro = utils.GetBasesInMRO(ast.Lookup("Bar"), lookup_ast=ast)
    self.assertListEqual(["Foo", "typing.Generic", "__builtin__.object"],
                         [t.name for t in mro])

  def testBuiltinAlias(self):
    src = "Number = int"
    ast = parser.parse_string(src)
    self.assertMultiLineEqual(utils.Print(ast), src)

  def testTypingNameConflict1(self):
    src = textwrap.dedent("""
      import typing

      x = ...  # type: typing.List[str]

      def List() -> None: ...
    """)
    ast = parser.parse_string(src)
    self.assertMultiLineEqual(utils.Print(ast).strip("\n"), src.strip("\n"))

  def testTypingNameConflict2(self):
    ast = parser.parse_string(textwrap.dedent("""
      import typing
      from typing import Any

      x = ...  # type: typing.List[str]

      class MyClass(object):
          List = ...  # type: Any
          x = ...  # type: typing.List[str]
    """))
    expected = textwrap.dedent("""
      import typing
      from typing import Any, List

      x = ...  # type: List[str]

      class MyClass(object):
          List = ...  # type: Any
          x = ...  # type: typing.List[str]
    """)
    self.assertMultiLineEqual(utils.Print(ast).strip("\n"),
                              expected.strip("\n"))


class TestDataFiles(parser_test_base.ParserTest):
  """Test utils.GetPredefinedFile()."""

  def testGetPredefinedFileReturnsString(self):
    # smoke test, only checks that it doesn't throw and the result is a string
    self.assertIsInstance(
        utils.GetPredefinedFile("builtins", "__builtin__"),
        str)

  def testGetPredefinedFileThrows(self):
    # smoke test, only checks that it does throw
    with self.assertRaisesRegexp(
        IOError,
        r"File not found|Resource not found|No such file or directory"):
      utils.GetPredefinedFile("builtins", "-this-file-does-not-exist")

  def testPytdBuiltin(self):
    """Verify 'import sys'."""
    import_contents = utils.GetPredefinedFile("builtins", "__builtin__")
    with open(os.path.join(os.path.dirname(pytd.__file__),
                           "builtins", "__builtin__.pytd"), "rb") as fi:
      file_contents = fi.read()
    self.assertMultiLineEqual(import_contents, file_contents)


if __name__ == "__main__":
  unittest.main()
