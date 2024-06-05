"""Tests for inferring protocols."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ProtocolInferenceTest(test_base.BaseTest):
  """Tests for protocol implementation."""

  def setUp(self):
    super().setUp()
    self.options.tweak(check=False, protocols=True)

  def test_multiple_signatures_with_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: int) -> List[T]: ...
        def f(x: List[T], y: str) -> List[T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x, y):
          return foo.f(x, y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        def f(x, y: Union[int, str]) -> list: ...
      """)

  def test_unknown_single_signature(self):
    # Test that the right signature is picked in the presence of an unknown
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: int) -> List[T]: ...
        def f(x: List[T], y: str) -> List[T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(y):
          return foo.f("", y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import List
        def f(y: int) -> List[str]: ...
      """)

  def test_multiple_signatures_with_unknown(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(arg1: str) -> float: ...
        def f(arg2: int) -> bool: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        def f(x: Union[int, str]) -> Union[float, bool]: ...
      """)

  def test_multiple_signatures_with_optional_arg(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str) -> int: ...
        def f(x = ...) -> float: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        def f(x: str) -> Union[int, float]: ...
      """)

  def test_multiple_signatures_with_kwarg(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(*, y: int) -> bool: ...
        def f(y: str) -> float: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(y=x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        def f(x: Union[int, str]) -> Union[bool, float]: ...
      """)

  def test_pow2(self):
    ty = self.Infer("""
      def t_testPow2(x, y):
        # pow(int, int) returns int, or float if the exponent is negative.
        # Hence, it's a handy function for testing UnionType returns.
        return pow(x, y)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testPow2(x: Union[complex, float, int], y: Union[complex, float, int]) -> Union[complex, float, int]: ...
    """)

  @test_base.skip("Moving to protocols.")
  def test_slices(self):
    ty = self.Infer("""
      def trim(docstring):
        lines = docstring.splitlines()
        for line in lines[1:]:
          len(line)
        return lines
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      def trim(docstring: Union[bytearray, str, unicode]) -> List[Union[bytearray, str, unicode], ...]: ...
    """)

  def test_match_unknown_against_container(self):
    ty = self.Infer("""
      a = {1}
      def f(x):
        return a & x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Set
      a = ...  # type: Set[int]

      def f(x) -> Set[int]: ...
    """)

  def test_supports_lower(self):
    ty = self.Infer("""
      def f(x):
        return x.lower()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsLower) -> Any: ...
    """)

  def test_container(self):
    ty = self.Infer("""
      def f(x, y):
          return y in x
     """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Container
      def f(x: Container, y:Any) -> bool: ...
    """)

  def test_supports_int(self):
    ty = self.Infer("""
      def f(x):
        return x.__int__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsInt
      def f(x: SupportsInt) -> Any: ...
    """)

  def test_supports_float(self):
    ty = self.Infer("""
      def f(x):
          return x.__float__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsFloat
      def f(x: SupportsFloat) -> Any: ...
    """)

  def test_supports_complex(self):
    ty = self.Infer("""
      def f(x):
        return x.__complex__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsComplex
      def f(x: SupportsComplex) -> Any: ...
    """)

  def test_sized(self):
    ty = self.Infer("""
      def f(x):
        return x.__len__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Sized
      def f(x: Sized) -> Any: ...
    """)

  def test_supports_abs(self):
    ty = self.Infer("""
      def f(x):
        y = abs(x)
        return y.__len__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsAbs, Sized
      def f(x: SupportsAbs[Sized]) -> Any: ...
    """)

  @test_base.skip("doesn't match arguments correctly")
  def test_supports_round(self):
    ty = self.Infer("""
      def f(x):
        y = x.__round__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, SupportsRound
      def f(x: SupportsRound) -> Any: ...
    """)

  def test_reversible(self):
    ty = self.Infer("""
      def f(x):
        y = x.__reversed__()
        return y
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator, Reversible
      def f(x: Reversible) -> Iterator: ...
    """)

  def test_iterable(self):
    ty = self.Infer("""
      def f(x):
        return x.__iter__()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable, Iterator
      def f(x: Iterable) -> Iterator: ...
    """)

  @test_base.skip("Iterator not implemented, breaks other functionality")
  def test_iterator(self):
    ty = self.Infer("""
      def f(x):
        return x.next()
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Iterator
      def f(x: Iterator) -> Any: ...
    """)

  def test_callable(self):
    ty = self.Infer("""
      def f(x):
        return x().lower()
      """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any, Callable
      def f(x: Callable[..., protocols.SupportsLower]) -> Any: ...
    """)

  @test_base.skip("Matches Mapping[int, Any] but not Sequence")
  def test_sequence(self):
    ty = self.Infer("""
      def f(x):
        x.index(6)
        x.count(7)
        return x.__getitem__(5) + x[1:5]
      """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any, Sequence
      def f(x: Sequence) -> Any: ...
    """)

  @test_base.skip("doesn't match arguments correctly on exit")
  def test_context_manager(self):
    ty = self.Infer("""
      def f(x):
        x.__enter__()
        x.__exit__(None, None, None)
      """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any, ContextManager
      def f(x: ContextManager) -> Any: ...
    """)

  def test_protocol_needs_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Sized, SupportsAbs
        def f(x: SupportsAbs[Sized]) -> None: ...
      """)
      ty = self.Infer("""
        import foo
        def g(y):
          return foo.f(y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Sized, SupportsAbs
        def g(y: SupportsAbs[Sized]) -> None: ...
      """)

  def test_protocol_needs_parameter_builtin(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import SupportsAbs
        def f(x: SupportsAbs[int]) -> None: ...
      """)
      ty = self.Infer("""
        import foo
        def g(y):
          return foo.f(y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import SupportsAbs
        def g(y: SupportsAbs[int]) -> None: ...
      """)

  @test_base.skip("Unexpectedly assumes returned result is sequence")
  def test_mapping_abstractmethod(self):
    ty = self.Infer("""
      def f(x, y):
        return x.__getitem__(y)
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Mapping
      def f(x: Mapping, y) -> Any: ...
    """)

  def test_supports_upper(self):
    ty = self.Infer("""
      def f(x):
        return x.upper()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsUpper) -> Any: ...
    """)

  def test_supports_startswith(self):
    ty = self.Infer("""
      def f(x):
        return x.startswith("foo")
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsStartswith) -> Any: ...
    """)

  def test_supports_endswith(self):
    ty = self.Infer("""
      def f(x):
        return x.endswith("foo")
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsEndswith) -> Any: ...
    """)

  def test_supports_lstrip(self):
    ty = self.Infer("""
      def f(x):
        return x.lstrip()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsLstrip) -> Any: ...
    """)

  def test_supports_replace(self):
    ty = self.Infer("""
      def f(x):
        return x.replace("foo", "bar")
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsReplace) -> Any: ...
    """)

  def test_supports_encode(self):
    ty = self.Infer("""
      def f(x):
        return x.encode()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsEncode) -> Any: ...
    """)

  def test_supports_decode(self):
    ty = self.Infer("""
      def f(x):
        return x.decode()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsDecode) -> Any: ...
    """)

  def test_supports_splitlines(self):
    ty = self.Infer("""
      def f(x):
        return x.splitlines()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsSplitlines) -> Any: ...
    """)

  def test_supports_split(self):
    ty = self.Infer("""
      def f(x):
        return x.split()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsSplit) -> Any: ...
    """)

  def test_supports_strip(self):
    ty = self.Infer("""
      def f(x):
        return x.strip()
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsStrip) -> Any: ...
    """)

  def test_supports_find(self):
    ty = self.Infer("""
      def f(x):
        return x.find("foo")
     """)
    self.assertTypesMatchPytd(ty, """
      import protocols
      from typing import Any
      def f(x: protocols.SupportsFind) -> Any: ...
    """)

  def test_signature_template(self):
    # Regression test for https://github.com/google/pytype/issues/410
    self.assertNoCrash(self.Infer, """
      def rearrange_proc_table(val):
        procs = val['procs']
        val['procs'] = dict((ix, procs[ix]) for ix in range(0, len(procs)))
        del val['fields']
    """)


if __name__ == "__main__":
  test_base.main()
