"""Tests for typing.py."""


from pytype import utils
from pytype.pytd import pep484
from pytype.tests import test_inference


class TypingTest(test_inference.InferenceTest):
  """Tests for typing.py."""

  _TEMPLATE = """
    from __future__ import google_type_annotations
    import collections
    import typing
    def f(s: %(annotation)s):
      return s
    f(%(arg)s)
  """

  def _test_match(self, arg, annotation):
    self.assertNoErrors(self._TEMPLATE % locals())

  def _test_no_match(self, arg, annotation):
    _, errors = self.InferAndCheck(self._TEMPLATE % locals())
    self.assertNotEqual(0, len(errors))

  def test_list_match(self):
    self._test_match("[1, 2, 3]", "typing.List")
    self._test_match("[1, 2, 3]", "typing.List[int]")
    self._test_match("[1, 2, 3.1]", "typing.List[typing.Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "typing.List[int]")

  def test_sequence_match(self):
    self._test_match("[1, 2, 3]", "typing.Sequence")
    self._test_match("[1, 2, 3]", "typing.Sequence[int]")
    self._test_match("(1, 2, 3.1)", "typing.Sequence[typing.Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "typing.Sequence[int]")

  def test_namedtuple_match(self):
    self._test_match("collections.namedtuple('foo', [])()",
                     "typing.NamedTuple")
    self._test_match("collections.namedtuple('foo', ('x', 'y'))()",
                     "typing.NamedTuple('foo', [('x', int), ('y', int)])")

  def test_all(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      x = typing.__all__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      typing = ...  # type: module
      x = ...  # type: List[str]
    """)

  def test_cast1(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      def f():
        return typing.cast(typing.List[int], [])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      typing = ...  # type: module
      def f() -> List[int]
    """)

  def test_cast2(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      import typing
      foo = typing.cast(typing.Dict, {})
    """)

  def test_process_annotation_for_cast(self):
    ty, errors = self.InferAndCheck("""\
      import typing
      v1 = typing.cast(None, __any_object__)
      v2 = typing.cast(typing.Union, __any_object__)
      v3 = typing.cast("A", __any_object__)
      class A(object):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      typing = ...  # type: module
      v1 = ...  # type: None
      v2 = ...  # type: typing.Any
      v3 = ...  # type: typing.Any
      class A(object): ...
    """)
    self.assertErrorLogIs(errors, [(3, "invalid-annotation"),
                                   (4, "invalid-annotation")])

  def test_generator(self):
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Generator
      def f() -> Generator[int]:
        for i in range(3):
          yield i
    """)

  def test_type(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Type
      class Foo:
        x = 1
      def f1(foo: Type[Foo]):
        return foo.x
      def f2(foo: Type[Foo]):
        return foo.y  # bad
      def f3(foo: Type[Foo]):
        return foo.mro()
      def f4(foo: Type[Foo]):
        return foo()
      v1 = f1(Foo)
      v2 = f2(Foo)
      v3 = f3(Foo)
      v4 = f4(Foo)
    """)
    self.assertErrorLogIs(errors, [(8, "attribute-error", r"y.*Foo")])
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type
      class Foo:
        x = ...  # type: int
      def f1(foo: Type[Foo]) -> int
      def f2(foo: Type[Foo]) -> Any
      def f3(foo: Type[Foo]) -> list
      def f4(foo: Type[Foo]) -> Foo
      v1 = ...  # type: int
      v2 = ...  # type: Any
      v3 = ...  # type: list
      v4 = ...  # type: Foo
    """)

  def test_type_union(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Type, Union
      class Foo:
        bar = ...  # type: int
      def f1(x: Type[Union[int, Foo]]):
        # Currently not an error, since attributes on Unions are retrieved
        # differently.  See get_attribute() in attribute.py.
        x.bar
      def f2(x: Union[Type[int], Type[Foo]]):
        x.bar
        f1(x)
      def f3(x: Type[Union[int, Foo]]):
        f1(x)
        f2(x)
    """, strict_attr_checking=True)
    self.assertErrorLogIs(errors, [(10, "attribute-error", "bar.*int")])

  def test_generate_type_alias(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List
      MyType = List[str]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      MyType = List[str]
    """)

  def test_use_type_alias(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List
        MyType = List[str]
      """)
      self.assertNoErrors("""
        from __future__ import google_type_annotations
        import foo
        def f(x: foo.MyType):
          pass
        f([""])
      """, pythonpath=[d.path])

  def test_callable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable
        def f() -> Callable
      """)
      self.assertNoErrors("""\
        from __future__ import google_type_annotations
        from typing import Callable
        import foo
        def f() -> Callable:
          return foo.f()
        def g() -> Callable:
          return int
      """, pythonpath=[d.path])

  def test_callable_parameters(self):
    ty, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Any, Callable

      # The below are all valid. We treat "..." and Any as synonymous, and if
      # _RET is omitted, its value defaults to Any.
      def f1(x: Callable[[int, str], bool]): ...
      def f2(x: Callable[..., bool]): ...
      def f3(x: Callable[[int, ...], bool]): ...
      def f4(x: Callable[[..., bool], bool]): ...
      def f5(x: Callable[Any, bool]): ...
      def f6(x: Callable[[int, str], ...]): ...
      def f7(x: Callable[[], bool]): ...
      def f8(x: Callable[[int, str]]): ...

      def g1(x: Callable[int, bool]): ...  # bad: _ARGS not a list
      lst = [int] if __any_object__ else [str]
      def g2(x: Callable[lst, bool]): ...  # bad: _ARGS ambiguous
      def g3(x: Callable[[], bool or str]): ...  # bad: _RET ambiguous
      def g4(x: Callable[[int or str], bool]): ...  # bad: _ARGS[0] ambiguous
      lst = None  # type: list[int]
      def g5(x: Callable[lst, bool]): ...  # bad: _ARGS not a constant
      lst = [str]
      lst[0] = int
      def g6(x: Callable[lst, bool]): ...  # bad: _ARGS not a constant
      def g7(x: Callable[[42], bool]): ...  # bad: _ARGS[0] not a type
      def g8(x: Callable[[], bool, int]): ...  # bad: Too many params
    """)
    self.assertTypesMatchPytd(ty, """
       from typing import Any, Callable, List, Type

       lst = ...  # type: List[Type[str or int]]

       def f1(x: Callable[[int, str], bool]) -> None: ...
       def f2(x: Callable[Any, bool]) -> None: ...
       def f3(x: Callable[[int, Any], bool]) -> None: ...
       def f4(x: Callable[[Any, bool], bool]) -> None: ...
       def f5(x: Callable[Any, bool]) -> None: ...
       def f6(x: Callable[[int, str], Any]) -> None: ...
       def f7(x: Callable[[], bool]) -> None: ...
       def f8(x: Callable[[int, str], Any]) -> None: ...
       def g1(x: Callable[Any, bool]) -> None: ...
       def g2(x: Callable[Any, bool]) -> None: ...
       def g3(x: Callable) -> None: ...
       def g4(x: Callable[[Any], bool]) -> None: ...
       def g5(x: Callable[Any, bool]) -> None: ...
       def g6(x: Callable[Any, bool]) -> None: ...
       def g7(x) -> None: ...
       def g8(x: Callable[[], bool]) -> None: ...
    """)
    # TODO(rechen): Make sure the error messages are reasonable.
    self.assertErrorLogIs(errors, [
        (15, "invalid-annotation", r"'int'.*must be a list of argument types"),
        (17, "invalid-annotation", r"\[int\] or \[str\].*Must be constant"),
        (18, "invalid-annotation", r"bool or str.*Must be constant"),
        (19, "invalid-annotation", r"int or str.*Must be constant"),
        (21, "invalid-annotation",
         r"instance of List\[int\].*Must be constant"),
        (24, "invalid-annotation", r"\[str\].*Must be constant"),
        (25, "invalid-annotation", r"instance of int.*Not a type"),
        (26, "invalid-annotation", r"Callable.*Expected 2.*got 3"),])

  def test_generics(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Dict
        K = TypeVar("K")
        V = TypeVar("V")
        class CustomDict(Dict[K, V]): ...
      """)
      self.assertNoErrors("""\
        from __future__ import google_type_annotations
        import typing
        import foo
        def f(x: typing.Callable[..., int]): pass
        def f(x: typing.Iterator[int]): pass
        def f(x: typing.Iterable[int]): pass
        def f(x: typing.Container[int]): pass
        def f(x: typing.Sequence[int]): pass
        def f(x: typing.Tuple[int, str]): pass
        def f(x: typing.MutableSequence[int]): pass
        def f(x: typing.List[int]): pass
        def f(x: typing.IO[str]): pass
        def f(x: typing.Mapping[int, str]): pass
        def f(x: typing.MutableMapping[int, str]): pass
        def f(x: typing.Dict[int, str]): pass
        def f(x: typing.AbstractSet[int]): pass
        def f(x: typing.FrozenSet[int]): pass
        def f(x: typing.MutableSet[int]): pass
        def f(x: typing.Set[int]): pass
        def f(x: typing.Reversible[int]): pass
        def f(x: typing.SupportsAbs[int]): pass
        def f(x: typing.Optional[int]): pass
        def f(x: typing.Generator[int]): pass
        def f(x: typing.Type[int]): pass
        def f(x: typing.Pattern[str]): pass
        def f(x: typing.Match[str]): pass
        def f(x: foo.CustomDict[int, str]): pass
      """, pythonpath=[d.path])

  def test_generator_iterator_match(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Iterator
      def f(x: Iterator[int]):
        pass
      f(x for x in [42])
    """)

  def testNameConflict(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      def f() -> typing.Any:
        pass
      class Any(object):
        pass
      def g() -> Any:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      import __future__
      typing = ...  # type: module
      def f() -> typing.Any: ...
      def g() -> Any: ...
      class Any(object):
          pass
    """)

  def testImportAll(self):
    python = [
        "from __future__ import google_type_annotations",
        "from typing import *  # pytype: disable=not-supported-yet",
    ] + pep484.PEP484_NAMES
    ty = self.Infer("\n".join(python))
    self.assertTypesMatchPytd(ty, "")

  def testRecursiveTuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class Foo(Tuple[Foo]): ...
      """)
      self.assertNoErrors("""\
        import foo
        foo.Foo()
      """, pythonpath=[d.path])

  def testBaseClass(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Iterable
      class Foo(Iterable):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable
      class Foo(Iterable): ...
    """)

  def testTypeChecking(self):
    self.assertNoErrors("""\
      import typing
      if typing.TYPE_CHECKING:
          pass
      else:
          name_error
    """)

  def testNotTypeChecking(self):
    self.assertNoErrors("""\
      import typing
      if not typing.TYPE_CHECKING:
          name_error
      else:
          pass
    """)

  def testMatch(self):
    ty = self.Infer("""
      import re
      match1 = re.search("(?P<foo>.*)", "bar")
      v1 = match1.group(u"foo")
      match2 = re.search("(?P<foo>.*)", u"bar")
      v2 = match2.group("foo")
      v3 = match1.group(u"foo", u"foo")
      v4 = match1.start(u"foo")
      v5 = match1.end(u"foo")
      v6 = match1.span(u"foo")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Match, Tuple
      re = ...  # type: module
      match1 = ...  # type: Match[str]
      match2 = ...  # type: Match[unicode]
      v1 = ...  # type: str
      v2 = ...  # type: unicode
      v3 = ...  # type: Tuple[str, ...]
      v4 = ...  # type: int
      v5 = ...  # type: int
      v6 = ...  # type: Tuple[int, int]
    """)


if __name__ == "__main__":
  test_inference.main()
