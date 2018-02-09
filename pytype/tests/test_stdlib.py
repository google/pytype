"""Tests of selected stdlib functions."""


from pytype.tests import test_base


class StdlibTests(test_base.BaseTest):
  """Tests for files in typeshed/stdlib."""

  def testAST(self):
    ty = self.Infer("""
      import ast
      def f():
        return ast.parse("True")
    """)
    self.assertTypesMatchPytd(ty, """
      ast = ...  # type: module
      def f() -> _ast.Module
    """)

  def testUrllib(self):
    ty = self.Infer("""
      import urllib
    """)
    self.assertTypesMatchPytd(ty, """
      urllib = ...  # type: module
    """)

  def testTraceBack(self):
    ty = self.Infer("""
      import traceback
      def f(exc):
        return traceback.format_exception(*exc)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      traceback = ...  # type: module
      def f(exc) -> List[str]
    """)

  def testOsWalk(self):
    ty = self.Infer("""
      import os
      x = list(os.walk("/tmp"))
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      os = ...  # type: module
      x = ...  # type: List[Tuple[str, List[str], List[str]]]
    """)

  def testStruct(self):
    ty = self.Infer("""
      import struct
      x = struct.Struct("b")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      struct = ...  # type: module
      x = ...  # type: struct.Struct
    """)

  def testWarning(self):
    ty = self.Infer("""
      import warnings
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      warnings = ...  # type: module
    """)


  def testPosix(self):
    ty = self.Infer("""
      import posix
      x = posix.urandom(10)
    """)
    self.assertTypesMatchPytd(ty, """
      posix = ...  # type: module
      x = ...  # type: str
    """)

  def testTempfile(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import tempfile
      import typing
      import os
      def f(fi: typing.IO):
        fi.write("foobar")
        pos = fi.tell()
        fi.seek(0, os.SEEK_SET)
        s = fi.read(6)
        fi.close()
        return s
      f(tempfile.TemporaryFile("wb", suffix=".foo"))
      f(tempfile.NamedTemporaryFile("wb", suffix=".foo"))
      f(tempfile.SpooledTemporaryFile(1048576, "wb", suffix=".foo"))
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union
      import typing
      os = ...  # type: module
      tempfile = ...  # type: module
      typing = ...  # type: module
      def f(fi: typing.IO) -> Union[str, unicode]: ...
    """)

  def testPathConf(self):
    self.Check("""
      import os
      max_len = os.pathconf('directory', 'name')
      filename = 'foobar.baz'
      r = len(filename) >= max_len - 1
    """)

  def testEnviron(self):
    self.Check("""
      import os
      os.getenv('foobar', 3j)
      os.environ['hello'] = 'bar'
      x = os.environ['hello']
      y = os.environ.get(3.14, None)
      z = os.environ.get(3.14, 3j)
      del os.environ['hello']
    """)

  def testStdlib(self):
    self.Check("""
      import re
      s = "the quick brown fox jumps over the lazy dog"
      word = re.compile(r"\\w*")
      print word.sub(lambda x: '<'+x.group(0)+'>', s)
    """)

  def testNamedtuple(self):
    self.Check("""\
      import collections
      collections.namedtuple(u"_", "")
      collections.namedtuple("_", u"")
      collections.namedtuple("_", [u"a", "b"])
    """)

  def testDefaultdict(self):
    ty = self.Infer("""\
      import collections
      a = collections.defaultdict(int, one = 1, two = 2)
      b = collections.defaultdict(int, {'one': 1, 'two': 2})
      c = collections.defaultdict(int, [('one', 1), ('two', 2)])
      d = collections.defaultdict(int, {})
      e = collections.defaultdict(int)
      f = collections.defaultdict(default_factory = int)
      """)
    self.assertTypesMatchPytd(ty, """\
      collections = ...  # type: module
      a = ...  # type: collections.defaultdict[str, int]
      b = ...  # type: collections.defaultdict[str, int]
      c = ...  # type: collections.defaultdict[str, int]
      d = ...  # type: collections.defaultdict[nothing, int]
      e = ...  # type: collections.defaultdict[nothing, int]
      f = ...  # type: collections.defaultdict[nothing, int]
      """)

  def testDefaultdictNoFactory(self):
    ty = self.Infer("""\
      import collections
      a = collections.defaultdict()
      b = collections.defaultdict(None)
      c = collections.defaultdict(lambda: __any_object__)
      d = collections.defaultdict(None, one = 1, two = 2)
      e = collections.defaultdict(None, {'one': 1, 'two': 2})
      f = collections.defaultdict(None, [('one', 1), ('two', 2)])
      g = collections.defaultdict(one = 1, two = 2)
      h = collections.defaultdict(default_factory = None)
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Any
      collections = ...  # type: module
      a = ...  # type: collections.defaultdict[nothing, nothing]
      b = ...  # type: collections.defaultdict[nothing, nothing]
      c = ...  # type: collections.defaultdict[nothing, Any]
      d = ...  # type: collections.defaultdict[str, int]
      e = ...  # type: collections.defaultdict[str, int]
      f = ...  # type: collections.defaultdict[str, int]
      g = ...  # type: collections.defaultdict[str, int]
      h = ...  # type: collections.defaultdict[nothing, nothing]
      """)

  def testDefaultdictDiffDefaults(self):
    ty = self.Infer("""\
      import collections
      a = collections.defaultdict(int, one = '1')
      b = collections.defaultdict(str, one = 1)
      c = collections.defaultdict(None, one = 1)
      d = collections.defaultdict(int, {1: 'one'})
      """)
    self.assertTypesMatchPytd(ty, """\
      from typing import Union
      collections = ...  # type: module
      a = ...  # type: collections.defaultdict[str, Union[int, str]]
      b = ...  # type: collections.defaultdict[str, Union[int, str]]
      c = ...  # type: collections.defaultdict[str, int]
      d = ...  # type: collections.defaultdict[int, Union[int, str]]
      """)

  def testCounter(self):
    self.Check("""
      import collections
      x = collections.Counter()
      y = collections.Counter()
      (x + y).elements
      (x - y).elements
      (x & y).elements
      (x | y).elements
    """)

  def testStringTypes(self):
    ty = self.Infer("""
      import types
      if isinstance("", types.StringTypes):
        x = 42
      if isinstance(False, types.StringTypes):
        y = 42
      if isinstance(u"", types.StringTypes):
        z = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      types = ...  # type: module
      x = ...  # type: int
      z = ...  # type: int
    """)

  def testXRange(self):
    self.Check("""
      import random
      random.sample(xrange(10), 5)
    """)

  def testXml(self):
    self.Check("""
      import xml.etree.cElementTree
      xml.etree.cElementTree.SubElement
      xml.etree.cElementTree.iterparse
    """)

  def testCsv(self):
    self.Check("""
      import _csv
      import csv
    """)

  def testFuture(self):
    self.Check("""\
      import __future__
    """)

  def testDefaultDict(self):
    self.Check("""\
      import collections
      import itertools
      ids = collections.defaultdict(itertools.count(17).next)
    """)

  def _testCollectionsObject(self, obj, good_arg, bad_arg, error,
                             python_version=(2, 7)):
    errors = self.CheckWithErrors("""\
      from __future__ import google_type_annotations
      import collections
      def f(x: collections.{obj}): ...
      f({good_arg})
      f({bad_arg})  # line 5
    """.format(obj=obj, good_arg=good_arg, bad_arg=bad_arg),
                                  python_version=python_version)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", error)])

  def testCollectionsContainer(self):
    self._testCollectionsObject("Container", "[]", "42", r"Container.*int")

  def testCollectionsHashable(self):
    self._testCollectionsObject("Hashable", "42", "[]", r"Hashable.*List")

  def testCollectionsIterable(self):
    self._testCollectionsObject("Iterable", "[]", "42", r"Iterable.*int")

  def testCollectionsIterator(self):
    self._testCollectionsObject("Iterator", "iter([])", "42", r"Iterator.*int")

  def testCollectionsSized(self):
    self._testCollectionsObject("Sized", "[]", "42", r"Sized.*int")

  def testCollectionsCallable(self):
    self._testCollectionsObject("Callable", "list", "42", r"Callable.*int")

  def testCollectionsSequence(self):
    self._testCollectionsObject("Sequence", "[]", "42", r"Sequence.*int")

  def testCollectionsMutableSequence(self):
    self._testCollectionsObject(
        "MutableSequence", "[]", "42", r"MutableSequence.*int")

  def testCollectionsSet(self):
    self._testCollectionsObject("Set", "set()", "42", r"set.*int")

  def testCollectionsMutableSet(self):
    self._testCollectionsObject("MutableSet", "set()", "42", r"MutableSet.*int")

  def testCollectionsMapping(self):
    self._testCollectionsObject("Mapping", "{}", "42", r"Mapping.*int")

  def testCollectionsMutableMapping(self):
    self._testCollectionsObject(
        "MutableMapping", "{}", "42", r"MutableMapping.*int")

  def testCollectionsMappingView(self):
    self._testCollectionsObject(
        "MappingView", "{}.viewitems()", "42", r"MappingView.*int")

  def testCollectionsItemsView(self):
    self._testCollectionsObject(
        "ItemsView", "{}.viewitems()", "42", r"ItemsView.*int")

  def testCollectionsKeysView(self):
    self._testCollectionsObject(
        "KeysView", "{}.viewkeys()", "42", r"KeysView.*int")

  def testCollectionsValuesView(self):
    self._testCollectionsObject(
        "ValuesView", "{}.viewvalues()", "42", r"ValuesView.*int")

  def testCollectionsBytestring(self):
    self._testCollectionsObject(
        "ByteString", "bytes('hello', encoding='utf-8')", "42",
        r"ByteString.*int", python_version=(3, 6))

  def testCollectionsCollection(self):
    self._testCollectionsObject("Collection", "[]", "42", r"Collection.*int",
                                python_version=(3, 6))

  def testCollectionsGenerator(self):
    self._testCollectionsObject("Generator", "i for i in range(42)", "42",
                                r"generator.*int", python_version=(3, 6))

  def test_collections_reversible(self):
    self._testCollectionsObject("Reversible", "[]", "42", r"Reversible.*int",
                                python_version=(3, 6))

  def testCollectionsDeque(self):
    # This method is different from the preceding ones because we model
    # collections.deque as a subclass, rather than an alias, of typing.Deque.
    errors = self.CheckWithErrors("""\
      from __future__ import google_type_annotations
      from typing import Deque
      import collections
      def f1(x: Deque): ...
      def f2(x: int): ...
      f1(collections.deque())
      f2(collections.deque())  # line 7
    """)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types", r"int.*deque")])

  def testCollectionsSmokeTest(self):
    self.Check("""
      import collections
      collections.AsyncIterable
      collections.AsyncIterator
      collections.AsyncGenerator
      collections.Awaitable
      collections.Coroutine
    """, python_version=(3, 6))


if __name__ == "__main__":
  test_base.main()
