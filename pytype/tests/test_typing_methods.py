"""Tests for the methods in typing.pyi."""

import textwrap


from pytype import utils
from pytype.tests import test_inference


class TypingMethodsTest(test_inference.InferenceTest):
  """Tests for typing.py."""

  def _check_call(self, t, expr):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import %(type)s
        def f() -> %(type)s
      """ % {"type": t})
      indented_expr = textwrap.dedent(expr).replace("\n", "\n" + " "*8)
      self.assertNoErrors("""\
        import foo
        x = foo.f()
        %(expr)s
      """ % {"expr": indented_expr}, pythonpath=[d.path])

  def test_text(self):
    self._check_call("Text", "x.upper()")

  def test_supportsabs(self):
    self._check_call("SupportsAbs", "abs(x)")

  def test_supportsround(self):
    self._check_call("SupportsRound", "round(x)")

  def test_supportsint(self):
    self._check_call("SupportsInt", "int(x); int(3)")

  def test_supportsfloat(self):
    self._check_call("SupportsFloat", "float(x); float(3.14)")

  def test_supportscomplex(self):
    self._check_call("SupportsComplex", "complex(x); complex(3j)")

  def test_reversible(self):
    self._check_call("Reversible", "reversed(x)")

  def test_hashable(self):
    self._check_call("Hashable", "hash(x)")

  def test_sized(self):
    self._check_call("Sized", "len(x)")

  def test_iterator(self):
    self._check_call("Iterator", "next(x)")

  def test_iterable(self):
    self._check_call("Iterable", "next(iter(x))")

  def test_container(self):
    self._check_call("Container", "42 in x")

  def test_io(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import IO
        def f() -> IO[str]
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f()
        with x as fi:
            fi.read()
        for b in x: pass
        a = x.fileno()
        x.flush()
        b = x.isatty()
        c = x.read()
        d = x.read(30)
        e = x.readable()
        f = x.readline()
        g = x.readlines()
        h = x.seek(0)
        i = x.seek(0, 1)
        j = x.seekable()
        k = x.tell()
        x.truncate(10)
        m = x.writable()
        x.write("foo")
        x.writelines(["foo", "bar"])
        x.close()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import IO, List
        fi = ...  # type: IO[str]
        foo = ...  # type: module
        a = ...  # type: int
        b = ...  # type: bool
        c = ...  # type: str
        d = ...  # type: str
        e = ...  # type: bool
        f = ...  # type: str
        g = ...  # type: List[str]
        h = ...  # type: None
        i = ...  # type: None
        j = ...  # type: bool
        k = ...  # type: int
        m = ...  # type: bool
        x = ...  # type: IO[str]
      """)

  def test_binary_io(self):
    self._check_call("BinaryIO", "x.read(10).upper()")

  def test_text_io(self):
    self._check_call("TextIO", "x.read(10).upper()")

  def test_sequence_and_tuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Sequence, Tuple
        def seq() -> Sequence[str]
        def tpl() -> Tuple[str]
      """)
      ty = self.Infer("""\
        import foo
        for seq in [foo.seq(), foo.tpl()]:
          a = seq[0]
          seq[0:10]
          b = seq.index("foo")
          c = seq.count("foo")
          d = "foo" in seq
          e = iter(seq)
          f = reversed(seq)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Iterator, List, Sequence, Tuple, Union
        foo = ...  # type: module
        seq = ...  # type: Sequence[str] or Tuple[str]
        a = ...  # type: str
        b = ...  # type: int
        c = ...  # type: int
        d = ...  # type: bool
        e = ...  # type: Iterator[str] or tupleiterator[str]
        f = ...  # type: reversed[str]
      """)

  def test_mutablesequence_and_list(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, MutableSequence
        def seq() -> MutableSequence[str]
        def lst() -> List[str]
      """)
      ty = self.Infer("""\
        import foo
        for seq in [foo.seq(), foo.lst()]:
          seq[0] = 3
          del seq[0]
          a = seq.append(3)
          c = seq.insert(3, "foo")
          d = seq.reverse()
          e = seq.pop()
          f = seq.pop(4)
          g = seq.remove("foo")
          seq[0:5] = [1,2,3]
          b = seq.extend([1,2,3])
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Iterator, List, Sequence, Union
        foo = ...  # type: module
        # TODO(kramm): Should be List[Union[int, str]]
        seq = ...  # type: list or typing.MutableSequence[Union[int, str]]
        a = ...  # type: None
        b = ...  # type: None
        c = ...  # type: None
        d = ...  # type: None
        e = ...  # type: int or str
        f = ...  # type: int or str
        g = ...  # type: None
      """)

  def test_mapping(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Mapping
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
        from typing import List, Tuple, Union
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
        x = ...  # type: Union[int, str, Tuple[str, int]]
      """)

  def test_mutablemapping(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import MutableMapping, TypeVar
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
        from typing import Tuple, Union
        import foo
        foo = ...  # type: module
        m = ...  # type: foo.MyDict[Union[complex, int, str], Union[complex, float, int]]
        a = ...  # type: Union[complex, float, int]
        b = ...  # type: Tuple[Union[complex, str], Union[float, int]]
        c = ...  # type: Union[complex, float, int]
      """)

  def test_dict_and_defaultdict(self):
    # Sanity checks. (Default)Dict is just MutableMapping, which is tested above
    self._check_call("DefaultDict", "x[42j]")
    self._check_call("Dict", "x[42j]")

  def test_abstractset(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import AbstractSet
        def f() -> AbstractSet[str]
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f()
        a = "bar" in x
        b = x & x
        c = x | x
        d = x - x
        e = x ^ x
        f = x.isdisjoint([1,2,3])
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import AbstractSet
        foo = ...  # type: module
        x = ...  # type: AbstractSet[str]
        a = ...  # type: bool
        b = ...  # type: AbstractSet[str]
        c = ...  # type: AbstractSet[str]
        d = ...  # type: AbstractSet[str]
        e = ...  # type: AbstractSet[str]
        f = ...  # type: bool
      """)

  def test_frozenset(self):
    # Sanity check. FrozenSet is just AbstractSet, tested above.
    self._check_call("FrozenSet", "3 in x")

  def test_mutableset(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import MutableSet
        def f() -> MutableSet[str]
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f()
        x.add(1)
        a = x.pop()
        x.discard(2)
        x.clear()
        x.add(3j)
        x.remove(3j)
        b = x & {1,2,3}
        c = x | {1,2,3}
        d = x ^ {1,2,3}
        e = 3 in x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import MutableSet, Union
        foo = ...  # type: module
        a = ...  # type: Union[int, str]
        # TODO(kramm): We do a clear() after adding "int".
        #              Why does "int" still appear for b?
        b = ...  # type: MutableSet[Union[complex, int, str]]
        c = ...  # type: MutableSet[Union[complex, int, str]]
        d = ...  # type: MutableSet[Union[complex, int, str]]
        e = ...  # type: bool
        x = ...  # type: MutableSet[Union[complex, int, str]]
      """)

  def test_set(self):
    # Sanity check. Set is just MutableSet, tested above.
    self._check_call("Set", "x.add(3)")

  def test_generator(self):
    self._check_call("Generator", """
      next(x)
      x.send(42)
      x.throw(Exception())
      x.close()
    """)

  def test_pattern_and_match(self):
    # Basic pattern sanity check.
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Pattern
        def f() -> Pattern[str]
      """)
      ty = self.Infer("""\
        import foo
        pattern = foo.f()
        m1 = pattern.search("foo")
        pattern.match("foo")
        pieces = pattern.split("foo")
        pattern.findall("foo")[0]
        list(pattern.finditer("foo"))[0]
        pattern.sub("x", "x")
        pattern.subn("x", "x")
        a = m1.pos
        b = m1.endpos
        c = m1.group(1)
        d = m1.start()
        e = m1.end()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List, Match, Pattern
        foo = ...  # type: module
        a = ...  # type: int
        b = ...  # type: int
        c = ...  # type: str
        d = ...  # type: int
        e = ...  # type: int
        m1 = ...  # type: Match[str]
        pattern = ...  # type: Pattern[str]
        pieces = ...  # type: List[str]
      """)


if __name__ == "__main__":
  test_inference.main()
