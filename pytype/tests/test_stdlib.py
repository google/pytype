"""Tests of selected stdlib functions."""


from pytype.tests import test_inference


class StdlibTests(test_inference.InferenceTest):
  """Tests for files in typeshed/stdlib."""

  def testAST(self):
    ty = self.Infer("""
      import ast
      def f():
        return ast.parse("True")
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      ast = ...  # type: module
      def f() -> _ast.Module
    """)

  def testUrllib(self):
    ty = self.Infer("""
      import urllib
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      urllib = ...  # type: module
    """)

  def testTraceBack(self):
    ty = self.Infer("""
      import traceback
      def f(exc):
        return traceback.format_exception(*exc)
    """, deep=True)
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
    """, deep=True)
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
      from typing import Any
      import typing
      os = ...  # type: module
      tempfile = ...  # type: module
      typing = ...  # type: module
      def f(fi: typing.IO) -> Any: ...
    """)

  def testPathConf(self):
    self.assertNoErrors("""
      import os
      max_len = os.pathconf('directory', 'name')
      filename = 'foobar.baz'
      r = len(filename) >= max_len - 1
    """)

  def testEnviron(self):
    self.assertNoErrors("""
      import os
      os.getenv('foobar', 3j)
      os.environ['hello'] = 'bar'
      x = os.environ['hello']
      y = os.environ.get(3.14, None)
      z = os.environ.get(3.14, 3j)
      del os.environ['hello']
    """)

  def testStdlib(self):
    self.assertNoErrors("""
      import re
      s = "the quick brown fox jumps over the lazy dog"
      word = re.compile(r"\\w*")
      print word.sub(lambda x: '<'+x.group(0)+'>', s)
    """)

  def testNamedtuple(self):
    self.assertNoErrors("""\
      import collections
      collections.namedtuple(u"_", "")
      collections.namedtuple("_", u"")
      collections.namedtuple("_", [u"a", "b"])
    """)

  def testDefaultdict(self):
    ty, errors = self.InferAndCheck("""\
      import collections
      a = collections.defaultdict(int, one = 1, two = 2)
      b = collections.defaultdict(int, {'one': 1, 'two': 2})
      c = collections.defaultdict(int, [('one', 1), ('two', 2)])
      d = collections.defaultdict(int, {})
      e = collections.defaultdict(int)
      f = collections.defaultdict(default_factory = int)
      """)
    self.assertErrorLogIs(errors, [])
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
    ty, errors = self.InferAndCheck("""\
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
    self.assertErrorLogIs(errors, [])
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
    ty, errors = self.InferAndCheck("""\
      import collections
      a = collections.defaultdict(int, one = '1')
      b = collections.defaultdict(str, one = 1)
      c = collections.defaultdict(None, one = 1)
      d = collections.defaultdict(int, {1: 'one'})
      """)
    self.assertErrorLogIs(errors, [])
    self.assertTypesMatchPytd(ty, """\
      from typing import Union
      collections = ...  # type: module
      a = ...  # type: collections.defaultdict[str, Union[int, str]]
      b = ...  # type: collections.defaultdict[str, Union[int, str]]
      c = ...  # type: collections.defaultdict[str, int]
      d = ...  # type: collections.defaultdict[int, Union[int, str]]
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
    """)
    self.assertTypesMatchPytd(ty, """
      types = ...  # type: module
      x = ...  # type: int
      z = ...  # type: int
    """)

  def testXRange(self):
    self.assertNoErrors("""
      import random
      random.sample(xrange(10), 5)
    """)


if __name__ == "__main__":
  test_inference.main()
