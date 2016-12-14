"""Tests of builtins (in pytd/builtins/__builtins__.pytd).

File 2/2. Split into two parts to enable better test parallelism.
"""


from pytype import utils
from pytype.tests import test_inference


class BuiltinTests2(test_inference.InferenceTest):
  """Tests for builtin methods and classes."""

  def testDivModWithUnknown(self):
    ty = self.Infer("""
      def f(x, y):
        divmod(x, __any_object__)
        return divmod(3, y)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: int or float or complex,
            y: int or float or complex) -> Tuple[int or float or complex, ...]
    """)

  def testDefaultDict(self):
    ty = self.Infer("""
      import collections
      r = collections.defaultdict()
      r[3] = 3
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      r = ...  # type: collections.defaultdict[int, int]
    """)

  def testImportLib(self):
    ty = self.Infer("""
      import importlib
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      importlib = ...  # type: module
    """)

  def testSetUnion(self):
    ty = self.Infer("""
      def f(y):
        return set.union(*y)
      def g(y):
        return set.intersection(*y)
      def h(y):
        return set.difference(*y)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(y) -> set: ...
      def g(y) -> set: ...
      def h(y) -> set: ...
    """)

  def testSetInit(self):
    ty = self.Infer("""
      data = set(x for x in [""])
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      data = ...  # type: Set[str]
    """)

  def testFrozenSetInheritance(self):
    ty = self.Infer("""
      class Foo(frozenset):
        pass
      Foo([])
    """, deep=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(frozenset):
        pass
    """)

  def testOldStyleClass(self):
    ty = self.Infer("""
      class Foo:
        def get_dict(self):
          return self.__dict__
        def get_name(self):
          return self.__name__
        def get_class(self):
          return self.__class__
        def get_doc(self):
          return self.__doc__
        def get_module(self):
          return self.__module__
        def get_bases(self):
          return self.__bases__
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def get_dict(self) -> Dict[str, Any]
        def get_name(self) -> str
        def get_class(self) -> Type[Foo]
        def get_doc(self) -> str
        def get_module(self) -> str
        def get_bases(self) -> tuple
    """)

  def testNewStyleClass(self):
    ty = self.Infer("""
      class Foo(object):
        def get_dict(self):
          return self.__dict__
        def get_name(self):
          return self.__name__
        def get_class(self):
          return self.__class__
        def get_doc(self):
          return self.__doc__
        def get_module(self):
          return self.__module__
        def get_bases(self):
          return self.__bases__
        def get_hash(self):
          return self.__hash__()
        def get_mro(self):
          return self.__mro__
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def get_dict(self) -> Dict[str, Any]
        def get_name(self) -> str
        def get_class(self) -> Type[Foo]
        def get_doc(self) -> str
        def get_module(self) -> str
        def get_hash(self) -> int
        def get_mro(self) -> list
        def get_bases(self) -> tuple
    """)

  def testDictInit(self):
    ty = self.Infer("""
      x = dict(u=3, v=4, w=5)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: dict
    """)

  def testDictIterators(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def need_iterator(x: Iterator[Any]) -> None: ...
      """)
      ty = self.Infer("""\
        import foo
        d = {"a": 1}
        foo.need_iterator(d.iterkeys())
        key = d.iterkeys().next()
        foo.need_iterator(d.itervalues())
        value = d.itervalues().next()
        foo.need_iterator(d.iteritems())
        item = d.iteritems().next()
      """, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        d = ...  # type: dict[str, int]
        key = ...  # type: str
        value = ...  # type: int
        item = ...  # type: Tuple[Union[int, str], ...]
      """)

  def testMax(self):
    ty = self.Infer("""
      x = dict(u=3, v=4, w=5)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: dict
    """)

  def testModule(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: module
      """)
      ty = self.Infer("""\
        import foo
        foo.x.bar()
        x = foo.__name__
        y = foo.x.baz
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: str
        y = ...  # type: Any
      """)

  def testClassMethod(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
          x = ...  # type: classmethod
      """)
      ty = self.Infer("""\
        from foo import A
        y = A.x()
        z = A().x()
      """, pythonpath=[d.path], extract_locals=True)
      self.assertTypesMatchPytd(ty, """
        A = ...  # type: Type[foo.A]
        y = ...  # type: Any
        z = ...  # type: Any
      """)

  def testStaticMethod(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
          x = ...  # type: staticmethod
      """)
      ty = self.Infer("""\
        from foo import A
        y = A.x()
        z = A().x()
      """, pythonpath=[d.path], extract_locals=True)
      self.assertTypesMatchPytd(ty, """
        A = ...  # type: Type[foo.A]
        y = ...  # type: Any
        z = ...  # type: Any
      """)

  def testMinMax(self):
    ty = self.Infer("""
      x = min(x for x in range(3))
      y = max(x for x in range(3))
    """, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
      y = ...  # type: int
    """)

  def testMap(self):
    ty = self.Infer("""
      lst1 = []
      lst2 = [x for x in lst1]
      lst3 = map(str, lst2)
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      lst1 = ...  # type: List[nothing]
      lst2 = ...  # type: List[nothing]
      x = ...  # type: Any
      lst3 = ...  # type: List[nothing]
    """)

  def testFromKeys(self):
    ty = self.Infer("""
      d1 = dict.fromkeys([1])
      d2 = dict.fromkeys([1], 0)
      d3 = dict.fromkeys("123")
      d4 = dict.fromkeys(bytearray("x"))
      d5 = dict.fromkeys(u"x")
      d6 = dict.fromkeys(iter("123"))
      d7 = dict.fromkeys({True: False})
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      d1 = ...  # type: Dict[int, None]
      d2 = ...  # type: Dict[int, int]
      d3 = ...  # type: Dict[str, None]
      d4 = ...  # type: Dict[int, None]
      d5 = ...  # type: Dict[unicode, None]
      d6 = ...  # type: Dict[str, None]
      d7 = ...  # type: Dict[bool, None]
    """)

  def testRedefinedBuiltin(self):
    ty = self.Infer("""
      class BaseException(Exception): pass
      class CryptoException(BaseException, ValueError): pass
    """)
    p1, p2 = ty.Lookup("CryptoException").parents
    self.assertEqual(p1.name, "BaseException")
    self.assertEqual(p2.name, "__builtin__.ValueError")
    self.assertTypesMatchPytd(ty, """
      class BaseException(Exception): ...
      class CryptoException(BaseException, ValueError): ...
    """)

  def testSum(self):
    ty = self.Infer("""
      x1 = sum([1, 2])
      x2 = sum([1, 2], 0)
      x3 = sum([1.0, 3j])
      x4 = sum([1.0, 3j], 0)
      x5 = sum([[1], ["2"]], [])
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: int
      x2 = ...  # type: int
      x3 = ...  # type: int or float or complex
      x4 = ...  # type: int or float or complex
      x5 = ...  # type: List[int or str]
    """)

  def testReversed(self):
    ty, errors = self.InferAndCheck("""\
      x1 = reversed(xrange(42))
      x2 = reversed([42])
      x3 = reversed((4, 2))
      x4 = reversed("hello")
      x5 = reversed({42})
      x6 = reversed(frozenset([42]))
      x7 = reversed({True: 42})
    """)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: reversed[int]
      x2 = ...  # type: reversed[int]
      x3 = ...  # type: reversed[int]
      x4 = ...  # type: reversed[str]
      x5 = ...  # type: reversed[nothing]
      x6 = ...  # type: reversed[nothing]
      x7 = ...  # type: reversed[nothing]
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"Set\[int\]"),
                                   (6, "wrong-arg-types", r"FrozenSet\[int\]"),
                                   (7, "wrong-arg-types",
                                    r"Dict\[bool, int\]")])

  def testFilter(self):
    ty = self.Infer("""
      def f(x):
        pass
      x1 = filter(f, {1: None}.iterkeys())
      x2 = filter(None, {1: None}.iterkeys())
      x3 = filter(None, "")
      x4 = filter(None, u"")
      x5 = filter(None, bytearray(""))
      x6 = filter(None, (True, False))
      x7 = filter(None, {True, False})
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> None
      x1 = ...  # type: List[int]
      x2 = ...  # type: List[int]
      x3 = ...  # type: str
      x4 = ...  # type: unicode
      x5 = ...  # type: List[int]
      x6 = ...  # type: Tuple[bool]
      x7 = ...  # type: List[bool]
    """)

  def testStrJoin(self):
    ty = self.Infer("""
      a = ",".join([])
      b = u",".join([])
      c = ",".join(["foo"])
      d = u",".join(["foo"])
      e = ",".join([u"foo"])
      f = u",".join([u"foo"])
      g = ",".join([u"foo", "bar"])
      h = u",".join([u"foo", "bar"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: str
      b = ...  # type: unicode
      c = ...  # type: str
      d = ...  # type: unicode
      e = ...  # type: unicode
      f = ...  # type: unicode
      g = ...  # type: str or unicode
      h = ...  # type: unicode
    """)

  def testBytearrayJoin(self):
    ty = self.Infer("""
      b = bytearray()
      x1 = b.join([])
      x2 = b.join(["x"])
      x3 = b.join([b])
    """)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: bytearray
      x1 = ...  # type: bytearray
      x2 = ...  # type: bytearray
      x3 = ...  # type: bytearray
    """)

  def testReduce(self):
    self.assertNoErrors("""
      reduce(lambda x, y: x+y, [1,2,3]).real
      reduce(lambda x, y: x+y, ["foo"]).upper()
      reduce(lambda x, y: 4, "foo").real
      reduce(lambda x, y: 4, [], "foo").upper()
      reduce(lambda x, y: "s", [1,2,3], 0).upper()
    """)

  def testDictKeys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.viewkeys() & {1, 2, 3}
      b = m.viewkeys() - {1, 2, 3}
      c = m.viewkeys() | {1, 2, 3}
      d = m.viewkeys() ^ {1, 2, 3}
    """)
    self.assertTypesMatchPytd(ty, """
      m = ...  # type: Dict[str, None]
      a = ...  # type: Set[str]
      b = ...  # type: Set[str]
      c = ...  # type: Set[int or str]
      d = ...  # type: Set[int or str]
    """)

  def testLong(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: long): ...
      """)
      self.assertNoErrors("""
        import foo
        foo.f(42)
      """, pythonpath=[d.path])

  def testLongConstant(self):
    ty = self.Infer("""
      MAX_VALUE = 2**64
    """)
    self.assertTypesMatchPytd(ty, """
      MAX_VALUE = ...  # type: int
    """)


if __name__ == "__main__":
  test_inference.main()
