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
      def f(x: int or float or complex or long,
            y: int or float or complex or long) -> Tuple[int or float or complex or long, ...]
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
      x3 = ...  # type: long or float or complex
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
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"set"),
                                   (6, "wrong-arg-types", r"frozenset"),
                                   (7, "wrong-arg-types", r"dict")])


if __name__ == "__main__":
  test_inference.main()
