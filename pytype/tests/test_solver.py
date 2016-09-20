"""Test cases that need solve_unknowns."""

import unittest


from pytype import utils
from pytype.tests import test_inference


class SolverTests(test_inference.InferenceTest):
  """Tests for type inference that also runs convert_structural.py."""

  def testAmbiguousAttr(self):
    ty = self.Infer("""
      class Node(object):
          children = ()
          def __init__(self):
              self.children = []
              for ch in self.children:
                  pass
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
    class Node(object):
      children = ...  # type: List[nothing, ...] or Tuple[nothing, ...]
    """)

  def testCall(self):
    ty = self.Infer("""
      def f():
        x = __any_object__
        y = x.foo
        z = y()
        eval(y)
        return z
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> ?
    """)

  def testTypeParameters(self):
    ty = self.Infer("""
      def f(A):
        return [a - 42.0 for a in A.values()]
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
        def f(A: dict[?, float or complex or int or long]) -> List[float or complex, ...]
    """)

  def testAnythingTypeParameters(self):
    ty = self.Infer("""
      def f(x):
        return x.keys()
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: dict) -> list
    """)

  @unittest.skip("Infers x as Any because dict params are nothing")
  def testNothingTypeParameters(self):
    ty = self.Infer("""
      def f(x):
        x[""] = dict()
    """, deep=True, solve_unknowns=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: Dict[str, dict]) -> None
    """)

  def testNameConflict(self):
    ty = self.Infer("""
      import StringIO

      class Foobar(object):
        def foobar(self, out):
          out.write('')

      class Barbaz(object):
        def barbaz(self):
          __any_object__.foobar(StringIO.StringIO())
    """, deep=True, solve_unknowns=True)
    # TODO(rechen): Both StringIO[str] and BinaryIO are subclasses of IO[str],
    # which therefore should be optimized away.
    self.assertTypesMatchPytd(ty, """
      StringIO = ...  # type: module

      class Foobar(object):
        def foobar(self, out: StringIO.StringIO[str] or BinaryIO or IO[str]) -> NoneType

      class Barbaz(object):
        def barbaz(self) -> NoneType
    """)

  def testTopLevelClass(self):
    ty = self.Infer("""
      import Foo  # bad import

      class Bar(Foo):
        pass
    """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      Foo = ...  # type: ?

      class Bar(?):
        pass
    """)

  def testDictWithNothing(self):
    ty = self.Infer("""
      def f():
        d = {}
        d[1] = "foo"
        for name in d:
          len(name)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> NoneType
    """)

  def testOptionalParams(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, *types):
          self.types = types
        def bar(self, val):
          return issubclass(val, self.types)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def __init__(self, *types) -> NoneType
      types = ...  # type: Tuple[type, ...]
      def bar(self, val) -> bool
    """)

  @unittest.skip("isinstance() doesn't record a type signature")
  def testOptionalParams_obsolete(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, *types):
          self.types = types
        def bar(self, val):
          return isinstance(val, self.types)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def __init__(self, *types) -> NoneType
      types = ...  # type: Tuple[type, ...]
      def bar(self, val) -> bool
    """)

  def testNestedClass(self):
    ty = self.Infer("""
      class Foo(object):
        def f(self):
          class Foo(object):
            pass
          return Foo()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def f(self) -> ?
    """)

  def testEmptyTupleAsArg(self):
    ty = self.Infer("""
      def f():
        return isinstance(1, ())
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> bool
    """)

  def testIdentityFunction(self):
    ty = self.Infer("""
      def f(x):
        return x

      l = ["x"]
      d = {}
      d[l[0]] = 3
      f(**d)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> ?

      d = ...  # type: Dict[str, int]
      l = ...  # type: List[str, ...]
    """)

  def testCallConstructor(self):
    ty = self.Infer("""
      def f(x):
        return int(x, 16)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: int or float or str) -> int
    """)

  def testCallMethod(self):
    ty = self.Infer("""
      def f(x):
        return "abc".find(x)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: str or unicode or bytearray) -> int
    """)

  def testImport(self):
    ty = self.Infer("""
      import itertools
      def every(f, array):
        return all(itertools.imap(f, array))
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      itertools = ...  # type: module

      def every(f, array) -> bool
    """)

  def testNestedList(self):
    ty = self.Infer("""
      foo = [[]]
      bar = []

      def f():
        for obj in foo[0]:
          bar.append(obj)

      def g():
        f()
        foo[0].append(42)
        f()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      foo = ...  # type: List[list[int, ...], ...]
      bar = ...  # type: List[int, ...]

      def f() -> NoneType
      def g() -> NoneType
    """)

  def testTwiceNestedList(self):
    ty = self.Infer("""
      foo = [[[]]]
      bar = []

      def f():
        for obj in foo[0][0]:
          bar.append(obj)

      def g():
        f()
        foo[0][0].append(42)
        f()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      foo = ...  # type: List[List[List[int, ...], ...], ...]
      bar = ...  # type: List[int, ...]

      def f() -> NoneType
      def g() -> NoneType
    """)

  def testNestedListInClass(self):
    ty = self.Infer("""
      class Container(object):
        def __init__(self):
          self.foo = [[]]
          self.bar = []

      container = Container()

      def f():
        for obj in container.foo[0]:
          container.bar.append(obj)

      def g():
        f()
        container.foo[0].append(42)
        f()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class Container(object):
        foo = ...  # type: List[List[int, ...], ...]
        bar = ...  # type: List[int, ...]

      container = ...  # type: Container

      def f() -> NoneType
      def g() -> NoneType
    """)

  def testMatchAgainstFunctionWithoutSelf(self):
    with utils.Tempdir() as d:
      d.create_file("bad_mod.pyi", """
        class myclass:
          def bad_method() -> bool
      """)
      ty = self.Infer("""\
        import bad_mod
        def f(date):
          return date.bad_method()
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        bad_mod = ...  # type: module
        def f(date: bad_mod.myclass) -> bool
      """)

  def testExternalName(self):
    ty = self.Infer("""\
      import collections
      def bar(d):
          d[""] = collections.defaultdict(int, [(0, 0)])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      def bar(d: Dict[str, collections.defaultdict] or
                 collections.OrderedDict[str, collections.defaultdict] or
                 collections.defaultdict[str, collections.defaultdict]
              ) -> NoneType
    """)

  def testNameConflictWithBuiltin(self):
    ty = self.Infer("""\
      class LookupError(KeyError):
        pass
      def f(x):
        pass
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class LookupError(KeyError): ...
      def f(x) -> NoneType
    """)

  def testMutatingTypeParameters(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f() -> List[int]
      """)
      ty = self.Infer("""
        import foo
        def f():
          x = foo.f()
          x.append("str")
          return x
      """, deep=True, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> List[int or str]
      """)

  @unittest.skip("type_match.py needs support for kwonly.")
  def testDuplicateKeyword(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x, *args, y) -> None
      """)
      self.Infer("""\
        import foo
        foo.f(1, y=2)
      """, pythonpath=[d.path], solve_unknowns=True)


if __name__ == "__main__":
  test_inference.main()
