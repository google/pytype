"""Tests for matching against protocols.

Based on PEP 544 https://www.python.org/dev/peps/pep-0544/.
"""


from pytype.tests import test_inference


class ProtocolTest(test_inference.InferenceTest):
  """Tests for protocol implementation."""

  def test_check_protocol(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      import protocols
      from typing import Sized
      def f(x: protocols.Sized):
        return None
      def g(x: Sized):
        return None
      class Foo:
        def __len__(self):
          return 5
      f([])
      foo = Foo()
      f(foo)
      g([])
      g(foo)
    """)

  def test_check_iterator(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Iterator
      def f(x: Iterator):
        return None
      class Foo:
        def next(self):
          return None
        def __iter__(self):
          return None
      foo = Foo()
      f(foo)
    """)

  def test_check_protocol_error(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      import protocols

      def f(x: protocols.SupportsAbs):
        return x.__abs__()
      f(["foo"])
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types",
                                    r"\(x: SupportsAbs\).*\(x: List\[str\]\)")])

  def test_check_protocol_match_unknown(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Sized
      def f(x: Sized):
        pass
      class Foo(object):
        pass
      def g(x):
        foo = Foo()
        foo.__class__ = x
        f(foo)
    """)

  def test_check_protocol_against_garbage(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Sized
      def f(x: Sized):
        pass
      class Foo(object):
        pass
      def g(x):
        foo = Foo()
        foo.__class__ = 42
        f(foo)
    """)
    self.assertErrorLogIs(errors, [(10, "wrong-arg-types", r"\(x: Sized\)")])

  def test_check_parameterized_protocol(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Iterator, Iterable

      class Foo(object):
        def __iter__(self) -> Iterator[int]:
          return iter([])

      def f(x: Iterable[int]):
        pass

      foo = Foo()
      f(foo)
      f(iter([3]))
    """)

  def test_check_parameterized_protocol_error(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Iterator, Iterable

      class Foo(object):
        def __iter__(self) -> Iterator[str]:
          return iter([])

      def f(x: Iterable[int]):
        pass

      foo = Foo()
      f(foo)
    """)
    self.assertErrorLogIs(errors, [(12, "wrong-arg-types",
                                    r"\(x: Iterable\[int\]\).*\(x: Foo\)")])

  def test_check_parameterized_protocol_multi_signature(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Sequence, Union

      class Foo(object):
        def __len__(self):
          return 0
        def __getitem__(self, x: Union[int, slice]) -> Union[int, Sequence[int]]:
          return 0

      def f(x: Sequence[int]):
        pass

      foo = Foo()
      f(foo)
    """)

  def test_check_parameterized_protocol_error_multi_signature(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Sequence, Union

      class Foo(object):
        def __len__(self):
          return 0
        def __getitem__(self, x: int) -> int:
          return 0

      def f(x: Sequence[int]):
        pass

      foo = Foo()
      f(foo)
    """)
    self.assertErrorLogIs(errors, [(14, "wrong-arg-types",
                                    r"\(x: Sequence\[int\]\).*\(x: Foo\)")])

  def test_use_iterable(self):
    ty = self.Infer("""
      class A(object):
        def __iter__(self):
          return iter(__any_object__)
      v = list(A())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        def __iter__(self) -> Any: ...
      v = ...  # type: list
    """)

  def test_construct_dict_with_protocol(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      class Foo(object):
        def __iter__(self):
          pass
      def f(x: Foo):
        return dict(x)
    """)


if __name__ == "__main__":
  test_inference.main()
