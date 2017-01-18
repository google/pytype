"""Tests for typing.py."""

import os


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

  def test_list(self):
    self._test_match("[1, 2, 3]", "typing.List")
    self._test_match("[1, 2, 3]", "typing.List[int]")
    self._test_match("[1, 2, 3.1]", "typing.List[typing.Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "typing.List[int]")

  def test_sequence(self):
    self._test_match("[1, 2, 3]", "typing.Sequence")
    self._test_match("[1, 2, 3]", "typing.Sequence[int]")
    self._test_match("(1, 2, 3.1)", "typing.Sequence[typing.Union[int, float]]")
    self._test_no_match("[1.1, 2.1, 3.1]", "typing.Sequence[int]")

  def test_namedtuple(self):
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
      typing = ...  # type: module
      x = ...  # type: List[str]
    """)

  def test_cast(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      def f():
        return typing.cast(typing.List[int], [])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      typing = ...  # type: module
      def f() -> Any
    """)

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
      from typing import Any
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
    self.assertNoErrors("""\
      from __future__ import google_type_annotations
      from typing import Type, Union
      class Foo:
        bar = ...  # type: int
      def f1(x: Type[Union[int, Foo]]):
        x.bar
      def f2(x: Union[Type[int], Type[Foo]]):
        x.bar
        f1(x)
      def f3(x: Type[Union[int, Foo]]):
        f1(x)
        f2(x)
    """)

  def test_generate_type_alias(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List
      MyType = List[str]
    """)
    self.assertTypesMatchPytd(ty, """
      MyType = List[str]
    """)

  def test_use_type_alias(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", "MyType = List[str]")
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

  def test_generics(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
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

  def test_mapping(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        class MyDict(Mapping[K, V]): ...
        def f() -> MyDict[str, int]
      """)
      ty = self.Infer("""\
        import foo
        m = foo.f()
        a = m.copy()
        b = "foo" in m
        c = m["foo"]
        d = m.get("foo", 3)
        e = [x for x in m.items()]
        f = [x for x in m.keys()]
        g = [x for x in m.values()]
        h = [x for x in m.iteritems()]
        i = [x for x in m.iterkeys()]
        j = [x for x in m.itervalues()]
        k = [x for x in m.viewitems()]
        l = [x for x in m.viewkeys()]
        n = [x for x in m.viewvalues()]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        foo = ...  # type: module
        m = ...  # type: foo.MyDict[str, int]
        a = ...  # type: typing.Mapping[str, int]
        b = ...  # type: bool
        c = ...  # type: int
        d = ...  # type: int
        e = ...  # type: List[Tuple[str, int]]
        f = ...  # type: List[str]
        g = ...  # type: List[int]
        h = ...  # type: List[Tuple[str, int]]
        i = ...  # type: List[str]
        j = ...  # type: List[int]
        k = ...  # type: List[Tuple[str, int]]
        l = ...  # type: List[str]
        n = ...  # type: List[int]
        x = ...  # type: int
      """)

  def test_mutablemapping(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        class MyDict(MutableMapping[K, V]): ...
        def f() -> MyDict[str, int]
      """)
      ty = self.Infer("""\
        import foo
        m = foo.f()
        m.clear()
        m[3j] = 3.14
        del m["foo"]
        a = m.pop("bar", 3j)
        b = m.popitem()
        c = m.setdefault("baz", 3j)
        m.update({4j: 2.1})
        m.update([(1, 2), (3, 4)])
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        foo = ...  # type: module
        m = ...  # type: foo.MyDict[Union[complex, int, str], Union[complex, float, int]]
        a = ...  # type: Union[complex, float, int]
        b = ...  # type: Tuple[Union[complex, str], Union[float, int]]
        c = ...  # type: Union[complex, float, int]
      """)

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
      class Foo(Iterable): ...
    """)


if __name__ == "__main__":
  test_inference.main()
