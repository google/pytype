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
from pytype.pytd import pytd
from pytype.pytd import utils
from pytype.pytd.parse import parser_test


class TestUtils(parser_test.ParserTest):
  """Test the visitors in optimize.py."""

  def testGetPredefinedFileReturnsString(self):
    # smoke test, only checks that it doesn't throw and the result is a string
    self.assertIsInstance(
        utils.GetPredefinedFile("builtins", "errno"),
        str)

  def testGetPredefinedFileThrows(self):
    # smoke test, only checks that it does throw
    with self.assertRaisesRegexp(IOError, "File not found|Resource not found"):
      utils.GetPredefinedFile("builtins", "-this-file-does-not-exist")

  def testUnpackUnion(self):
    """Test for UnpackUnion."""
    ast = self.Parse("""
      c1: int or float
      c2: int
      c3: list<int or float>""")
    c1 = ast.Lookup("c1").type
    c2 = ast.Lookup("c2").type
    c3 = ast.Lookup("c3").type
    self.assertItemsEqual(utils.UnpackUnion(c1), c1.type_list)
    self.assertItemsEqual(utils.UnpackUnion(c2), [c2])
    self.assertItemsEqual(utils.UnpackUnion(c3), [c3])

  def testConcat(self):
    """Test for concatenating two pytd ASTs."""
    ast1 = self.Parse("""
      c1: int

      def f1() -> int

      class Class1:
        pass
    """)
    ast2 = self.Parse("""
      c2: int

      def f2() -> int

      class Class2:
        pass
    """)
    expected = textwrap.dedent("""
      c1: int
      c2: int

      def f1() -> int
      def f2() -> int

      class Class1:
          pass

      class Class2:
          pass
    """)
    combined = utils.Concat(ast1, ast2)
    self.AssertSourceEquals(combined, expected)

  def testConcat3(self):
    """Test for concatenating three pytd ASTs."""
    ast1 = self.Parse("""c1: int""")
    ast2 = self.Parse("""c2: float""")
    ast3 = self.Parse("""c3: bool""")
    combined = utils.Concat(ast1, ast2, ast3)
    expected = textwrap.dedent("""
      c1: int
      c2: float
      c3: bool
    """)
    self.AssertSourceEquals(combined, expected)

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

    s1 = pytd.Signature((), pytd.NothingType(), (), (), False)
    s2 = pytd.Signature((), pytd.AnythingType(), (), (), False)
    self.assertTrue(MyTypeMatcher().match(
        pytd.Function("f1", (s1, s2)),
        pytd.Function("f2", (s1, s2)),
        mykeyword="foobar"))
    self.assertFalse(MyTypeMatcher().match(
        pytd.Function("f1", (s1, s2)),
        pytd.Function("f2", (s2, s2)),
        mykeyword="foobar"))

  def testRemoveMutableList(self):
    # Simple test for RemoveMutableParameters, with simplified list class
    src = textwrap.dedent("""
      class TrivialList<T>:
        def append<T2>(self, v: T2) -> NoneType:
          self := T or T2

      class TrivialList2<T>:
        # TODO(pludemann): instead of self := T2 use
        #                  T = T2, when it's implemented
        # def __init__<T2>(self, x: T2) -> NoneType:
        #   self := T2
        def __init__(self, x: T) -> NoneType
        def append<T2>(self, v: T2) -> NoneType:
          self := T or T2
        def get_first(self) -> T
    """)
    expected = textwrap.dedent("""
      class TrivialList<T>:
          def append(self, v: T) -> NoneType

      class TrivialList2<T>:
          def __init__(self, x: T) -> NoneType
          def append(self, v: T) -> NoneType
          def get_first(self) -> T
    """)
    ast = self.Parse(src)
    ast = utils.RemoveMutableParameters(ast)
    self.AssertSourceEquals(ast, expected)

  def testRemoveMutableDict(self):
    # Test for RemoveMutableParameters, with simplified dict class.
    src = textwrap.dedent("""
      class MyDict<K, V>:
          def getitem<T>(self, k: K, default: T) -> V or T
          def setitem<K2, V2>(self, k: K2, value: V2) -> NoneType:
              self := dict<K or K2, V or V2>
          def getanykeyorvalue(self) -> K or V
          def setdefault<K2, V2>(self, k: K2, v: V2) -> V or V2:
              self := dict<K or K2, V or V2>
    """)
    expected = textwrap.dedent("""
      class MyDict<K, V>:
          def getitem(self, k: K, default: V) -> V
          def setitem(self, k: K, value: V) -> NoneType
          def getanykeyorvalue(self) -> K or V
          def setdefault(self, k: K, v: V) -> V
    """)
    ast = self.Parse(src)
    ast = utils.RemoveMutableParameters(ast)
    self.AssertSourceEquals(ast, expected)

  def testPrint(self):
    """Smoketests for printing pytd."""
    ast = self.Parse("""
      c1: int
      class A<T>:
        bar: T
        def foo(self, x: list<int>, y: T) -> list<T> or float raises ValueError
      def bar<X, Y>(x: X or Y) -> ?
    """)
    # TODO(kramm): Do more extensive testing.
    utils.Print(ast, print_format="pytd")
    utils.Print(ast, print_format="pep484stub")

  def testParsePyTD(self):
    """Test ParsePyTD()."""
    ast = utils.ParsePyTD("a: int", "<inline>", python_version=(2, 7, 6))
    a = ast.Lookup("a").type
    self.assertItemsEqual(a, pytd.ClassType("int"))
    self.assertIsNotNone(a.cls)  # verify that the lookup succeeded

  def testNamedOrExternalType(self):
    """Test NamedOrExternalType()."""
    self.assertEquals(utils.NamedOrExternalType("name"), pytd.NamedType("name"))
    self.assertEquals(utils.NamedOrExternalType("name", None),
                      pytd.NamedType("name"))
    self.assertEquals(utils.NamedOrExternalType("name", "package"),
                      pytd.ExternalType("name", "package"))

  def testPytdBuiltin(self):
    """Verify 'import sys'."""
    import_contents = utils.GetPredefinedFile("builtins", "sys")
    with open(os.path.join(os.path.dirname(pytd.__file__),
                           "builtins", "sys.pytd"), "rb") as fi:
      file_contents = fi.read()
    self.assertMultiLineEqual(import_contents, file_contents)


if __name__ == "__main__":
  unittest.main()
