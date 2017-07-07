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

  def test_container(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x, y):
          return y in x
     """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Container
      def f(x: Container, y:Any) -> bool
    """)

  def test_supports_int(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        return x.__int__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import SupportsInt
      def f(x: SupportsInt) -> ?
    """)

  def test_supports_float(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
          return x.__float__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsFloat
      def f(x: SupportsFloat) -> ?
    """)

  def test_supports_complex(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        return x.__complex__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsComplex
      def f(x: SupportsComplex) -> Any
    """)

  def test_sized(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        return x.__len__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Sized
      def f(x: Sized) -> ?
    """)

  def test_supports_abs(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        y = abs(x)
        return y.__len__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import SupportsAbs, Sized
      def f(x: SupportsAbs[Sized]) -> ?
    """)

  @unittest.skip("doesn't match arguments correctly")
  def test_supports_round(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        y = x.__round__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import SupportsRound
      def f(x: SupportsRound) -> ?
    """)

  def test_reversible(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        y = x.__reversed__()
        return y
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Reversible
      def f(x: Reversible) -> iterator
    """)

  def test_iterable(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        return x.__iter__()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable
      def f(x: Iterable) -> iterator
    """)

  @unittest.skip("Iterator not implemented, breaks other functionality")
  def test_iterator(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        return x.next()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      def f(x: Iterator) -> ?
    """)

  def test_callable(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        return x().lower()
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any, Callable
      def f(x: Callable[Any, protocols.SupportsLower]) -> ?
    """)

  @unittest.skip("Matches Mapping[int, Any] but not Sequence")
  def test_sequence(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        x.index(6)
        x.count(7)
        return x.__getitem__(5) + x[1:5]
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any, Sequence
      def f(x: Sequence) -> ?
    """)

  @unittest.skip("doesn't match arguments correctly on exit")
  def test_context_manager(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x):
        x.__enter__()
        x.__exit__(None, None, None)
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import ContextManager
      def f(x: ContextManager) -> ?
    """)

  def test_protocol_needs_parameter(self):
    self.options.tweak(protocols=True)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Sized, SupportsAbs
        def f(x: SupportsAbs[Sized]) -> None
      """)
      ty = self.Infer("""\
        from __future__ import google_type_annotations
        import foo
        def g(y):
          return foo.f(y)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Sized, SupportsAbs
        foo = ...  # type: module
        def g(y: SupportsAbs[Sized]) -> None
      """)

  def test_protocol_needs_parameter_builtin(self):
    self.options.tweak(protocols=True)
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import SupportsAbs
        def f(x: SupportsAbs[int]) -> None
      """)
      ty = self.Infer("""\
        from __future__ import google_type_annotations
        import foo
        def g(y):
          return foo.f(y)
      """, pythonpath=[d.path], deep=True)
      self.assertTypesMatchPytd(ty, """
        from typing import SupportsAbs
        foo = ...  # type: module
        def g(y: SupportsAbs[int]) -> None
      """)

  @unittest.skip("Unexpectedly assumes returned result is sequence")
  def test_mapping_abstractmethod(self):
    self.options.tweak(protocols=True)
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      def f(x, y):
        return x.__getitem__(y)
      """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Mapping
      def f(x: Mapping, y) -> ?
    """)

if __name__ == "__main__":
  test_inference.main()
