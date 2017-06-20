"""Tests for implementation of protocols.

Based on PEP 544 https://www.python.org/dev/peps/pep-0544/.
"""

import unittest

from pytype import utils
from pytype.tests import test_inference


class ProtocolTest(test_inference.InferenceTest):
  """Tests for protocol implementation."""

  def test_multiple_signatures_with_type_parameter(self):
    self.options.tweak(protocols=True)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: int) -> List[T]
        def f(x: List[T], y: str) -> List[T]
      """)
      ty = self.Infer("""
        import foo
        def f(x, y):
          return foo.f(x, y)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f(x, y: int or str) -> list
      """)

  def test_unknown_single_signature(self):
    self.options.tweak(protocols=True)
    # Test that the right signature is picked in the presence of an unknown
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: int) -> List[T]
        def f(x: List[T], y: str) -> List[T]
      """)
      ty = self.Infer("""
        import foo
        def f(y):
          return foo.f("", y)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import List
        foo = ...  # type: module
        def f(y: int) -> List[str]
      """)

  def test_multiple_signatures_with_unknown(self):
    self.options.tweak(protocols=True)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(arg1: str) -> float
        def f(arg2: int) -> bool
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f(x: int or str) -> float or bool
      """)

  def test_multiple_signatures_with_optional_arg(self):
    self.options.tweak(protocols=True)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str) -> int
        def f(...) -> float
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f(x: str) -> int or float
      """)

  def test_multiple_signatures_with_kwarg(self):
    self.options.tweak(protocols=True)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(*, y: int) -> bool
        def f(y: str) -> float
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(y=x)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f(x: int or str) -> bool or float
      """)

  def testPow2(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""
      def t_testPow2(x, y):
        # pow(int, int) returns int, or float if the exponent is negative.
        # Hence, it's a handy function for testing UnionType returns.
        return pow(x, y)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def t_testPow2(x: complex or float or int, y: complex or float or int) -> complex or float or int
    """)

  @unittest.skip("Moving to protocols.")
  def testSlices(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""
      def trim(docstring):
        lines = docstring.splitlines()
        for line in lines[1:]:
          len(line)
        return lines
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def trim(docstring: bytearray or str or unicode) -> List[bytearray or str or unicode, ...]
    """)

  @unittest.skip("Moving to protocols.")
  def testMatchUnknownAgainstContainer(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""
      a = {1}
      def f(x):
        return a & x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Set
      a = ...  # type: Set[int]

      def f(x: Iterable) -> Set[int]: ...
    """)

  def testWorkflow1(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""
      class ConfigParser(object):
        def __init__(self, filename):
          self.filename = filename
        def read(self):
          with open(self.filename, "r") as fi:
            return fi.read()

      cp = ConfigParser(__any_object__())
      cp.read()
      """, deep=False)
    self.assertTypesMatchPytd(ty, """
      cp = ...  # type: ConfigParser

      class ConfigParser(object):
        def __init__(self, filename: str or buffer or unicode) -> NoneType
        def read(self) -> str
        filename = ...  # type: str or buffer or unicode
    """)

  def test_supports_lower(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
          from __future__ import google_type_annotations
          def f(x):
            return x.lower()
         """, deep=True)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsLower) -> Any
    """)

  def test_supports_contains(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
          from __future__ import google_type_annotations
          def f(x, y):
            return y in x
         """, deep=True)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsContains, y:Any) -> bool
    """)

if __name__ == "__main__":
  test_inference.main()
