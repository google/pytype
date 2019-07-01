"""Tests of selected stdlib functions."""

from pytype.tests import test_base


class StdlibTests(test_base.TargetPython27FeatureTest):
  """Tests for files in typeshed/stdlib."""

  def testPosix(self):
    ty = self.Infer("""
      import posix
      x = posix.urandom(10)
    """)
    self.assertTypesMatchPytd(ty, """
      posix = ...  # type: module
      x = ...  # type: str
    """)

  def testXRange(self):
    self.Check("""
      import random
      random.sample(xrange(10), 5)
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

  def testDefaultDict(self):
    self.Check("""\
      import collections
      import itertools
      ids = collections.defaultdict(itertools.count(17).next)
    """)

  def testSysVersionInfoLt(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] < 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: int
    """)

  def testSysVersionInfoLe(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] <= 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: int
    """)

  def testSysVersionInfoEq(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] == 2:
        v = 42
      elif sys.version_info[0] == 3:
        v = "hello world"
      else:
        v = None
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: int
    """)

  def testSysVersionInfoGe(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] >= 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: str
    """)

  def testSysVersionInfoGt(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] > 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: str
    """)

  def testSysVersionInfoNamedAttribute(self):
    ty = self.Infer("""
      import sys
      if sys.version_info.major == 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys: module
      v: int
    """)


test_base.main(globals(), __name__ == "__main__")
