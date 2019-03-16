"""Tests of selected stdlib functions."""

from pytype.tests import test_base


class StdlibTests(test_base.TargetIndependentTest):
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
      word.sub(lambda x: '<'+x.group(0)+'>', s)
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

  def testRange(self):
    self.Check("""
      import random
      random.sample(range(10), 5)
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

  def testLoad2and3(self):
    """Test that files in stdlib/2and3/ load in both versions."""
    self.Check("""
      import collections
      import _ctypes
      import ctypes
      import dummy_thread
      import encodings
      import __future__
      import xmlrpclib
    """)

  def testSysVersionInfo(self):
    ty = self.Infer("""
      import sys
      major, minor, micro, releaselevel, serial = sys.version_info
    """)
    self.assertTypesMatchPytd(ty, """
      sys: module
      major: int
      minor: int
      micro: int
      releaselevel: str
      serial: int
    """)


test_base.main(globals(), __name__ == "__main__")
