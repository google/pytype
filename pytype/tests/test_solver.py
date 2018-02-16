"""Test cases that need solve_unknowns."""


from pytype import utils
from pytype.tests import test_base


class SolverTests(test_base.BaseTest):
  """Tests for type inference that also runs convert_structural.py."""

  def testAmbiguousAttr(self):
    ty = self.Infer("""
      class Node(object):
          children = ()
          def __init__(self):
              self.children = []
              for ch in self.children:
                  pass
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import List, Tuple
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
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> ?
    """)

  def testTypeParameters(self):
    ty = self.Infer("""
      def f(A):
        A.has_key("foo")
        return [a - 42.0 for a in A.viewvalues()]
    """)
    self.assertTypesMatchPytd(ty, """
        from typing import List
        def f(A) -> list
    """)

  def testAnythingTypeParameters(self):
    ty = self.Infer("""
      def f(x):
        return x.keys()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x) -> Any
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
    """)
    # TODO(rechen): Both StringIO[str] and IO are subclasses of IO[str],
    # which therefore should be optimized away.
    self.assertTypesMatchPytd(ty, """
      from typing import BinaryIO, IO
      StringIO = ...  # type: module

      class Foobar(object):
        def foobar(self, out) -> NoneType

      class Barbaz(object):
        def barbaz(self) -> NoneType
    """)

  def testTopLevelClass(self):
    ty = self.Infer("""
      import Foo  # bad import

      class Bar(Foo):
        pass
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      Foo = ...  # type: ?

      class Bar(?):
        pass
    """)

  def testDictWithNothing(self):
    ty = self.Infer("""
      def f():
        d = {}
        d["foo"] = "bar"
        for name in d:
          len(name)
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> NoneType
    """)

  def testOptionalParamsIsSubclass(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, *types):
          self.types = types
        def bar(self, val):
          return issubclass(val, self.types)
    """)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def __init__(self, *types) -> NoneType
      types = ...  # type: tuple
      def bar(self, val) -> bool
    """)

  def testOptionalParamsIsInstance(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, *types):
          self.types = types
        def bar(self, val):
          return isinstance(val, self.types)
    """)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def __init__(self, *types) -> NoneType
      types = ...  # type: tuple
      def bar(self, val) -> bool
    """)

  def testNestedClass(self):
    ty = self.Infer("""
      class Foo(object):
        def f(self):
          class Foo(object):
            pass
          return Foo()
    """)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def f(self) -> ?
    """)

  def testEmptyTupleAsArg(self):
    ty = self.Infer("""
      def f():
        return isinstance(1, ())
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, TypeVar
      _T0 = TypeVar("_T0")
      def f(x: _T0) -> _T0

      d = ...  # type: Dict[str, int]
      l = ...  # type: List[str, ...]
    """)

  def testCallConstructor(self):
    ty = self.Infer("""
      def f(x):
        return int(x, 16)
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int
    """)

  def testCallMethod(self):
    ty = self.Infer("""
      def f(x):
        return "abc".find(x)
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int
    """)

  def testImport(self):
    ty = self.Infer("""
      import itertools
      def every(f, array):
        return all(itertools.imap(f, array))
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        bad_mod = ...  # type: module
        def f(date) -> Any
      """)

  def testExternalName(self):
    ty = self.Infer("""\
      import collections
      def bar(l):
          l.append(collections.defaultdict(int, [(0, 0)]))
    """)
    self.assertTypesMatchPytd(ty, """
      import typing
      collections = ...  # type: module
      # TODO(kramm): The optimizer should collapse these two.
      def bar(l) -> NoneType
    """)

  def testNameConflictWithBuiltin(self):
    ty = self.Infer("""\
      class LookupError(KeyError):
        pass
      def f(x):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      class LookupError(KeyError): ...
      def f(x) -> NoneType
    """)

  def testMutatingTypeParameters(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List
        def f() -> List[int]
      """)
      ty = self.Infer("""
        import foo
        def f():
          x = foo.f()
          x.append("str")
          return x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        foo = ...  # type: module
        def f() -> List[int or str]
      """)

  def testDuplicateKeyword(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x, *args, y: T) -> T
      """)
      ty = self.Infer("""\
        import foo
        x = foo.f(1, y=2j)
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: complex
      """)

  def test_store_name_cfg(self):
    ty = self.Infer("""\
      a = 1
      a = a + 1
      """)
    self.assertTypesMatchPytd(ty, "a = ...  # type: int")

  def test_store_global_cfg(self):
    # STORE_GLOBAL didn't advance the cfg, so it required additional statements
    # in between in order to show the bug.
    ty = self.Infer("""\
      global a
      b = 1
      a = 1
      b = 1 + b
      a = 1 + a
      """)
    self.assertTypesMatchPytd(ty, """\
      a = ...  # type: int
      b = ...  # type: int
    """)


if __name__ == "__main__":
  test_base.main()
