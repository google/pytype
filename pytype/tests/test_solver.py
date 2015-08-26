"""Test cases that need solve_unknowns."""


from pytype.tests import test_inference


class SolverTests(test_inference.InferenceTest):
  """Tests for type inference that also runs convert_structural.py."""

  def testAmbiguousAttr(self):
    with self.Infer("""
      class Node(object):
          children = ()
          def __init__(self):
              self.children = []
              for ch in self.children:
                  pass
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Node:
        children: list<nothing> or tuple<nothing>
      """)

  def testCall(self):
    with self.Infer("""
      def f():
        x = __any_object__
        y = x.foo
        z = y()
        eval(y)
        return z
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> ?
      """)

  def testTypeParameters(self):
    with self.Infer("""
      def f(A):
        return [a - 42.0 for a in A.values()]
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
          # TODO(kramm): This is missing int, bool, long, complex
          def f(A: dict<?, float>) -> list<float>
      """)

  def testAnythingTypeParameters(self):
    with self.Infer("""
      def f(x):
        return x.keys()
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x: dict<?, ?>) -> list<?>
      """)

  def testNameConflict(self):
    with self.Infer("""
      import StringIO

      class Foobar(object):
        def foobar(self, out):
          out.write('')

      class Barbaz(object):
        def barbaz(self):
          __any_object__.foobar(StringIO.StringIO())
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        StringIO: module

        class Foobar(object):
          # TODO(kramm): Should 'out' be 'file or StringIO.StringIO'?
          def foobar(self, out: StringIO.StringIO) -> NoneType

        class Barbaz(object):
          def barbaz(self) -> NoneType
      """)

  def testTopLevelClass(self):
    with self.Infer("""
      import Foo  # bad import

      class Bar(Foo):
        pass
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertTypesMatchPytd(ty, """
        Foo: ?

        class Bar(?):
          pass
      """)

  def testDictWithNothing(self):
    with self.Infer("""
      def f():
        d = {}
        d[1] = "foo"
        for name in d:
          len(name)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> NoneType
      """)

  def testOptionalParams(self):
    with self.Infer("""
      class Foo(object):
        def __init__(self, *types):
          self.types = types
        def bar(self, val):
          return isinstance(val, self.types)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __init__(self, ...) -> NoneType
        types: tuple<type>
        def bar(self, val) -> bool
      """)

  def testNestedClass(self):
    with self.Infer("""
      class Foo(object):
        def f(self):
          class Foo(object):
            pass
          return Foo()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def f(self) -> ?
      """)

  def testEmptyTupleAsArg(self):
    with self.Infer("""
      def f():
        return isinstance(1, ())
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> bool
      """)

  def testIdentityFunction(self):
    with self.Infer("""
      def f(x):
        return x

      l = ["x"]
      d = {}
      d[l[0]] = 3
      f(**d)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x: int) -> int
        def f(x) -> ?

        d: dict<str, int>
        l: list<str>
      """)

  def testCallConstructor(self):
    with self.Infer("""
      def f(x):
        return int(x, 16)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        # TODO(kramm): Why is bool here?
        def f(x: bool or int or float) -> int
      """)

  def testCallMethod(self):
    with self.Infer("""
      def f(x):
        return "abc".find(x)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x: str or unicode or bytearray or bytes) -> int
      """)

  def testExternalType(self):
    with self.Infer("""
      import itertools
      def every(f, array):
        return all(itertools.imap(f, array))
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        itertools: module

        def every(f, array) -> bool
      """)

  def testNestedList(self):
    with self.Infer("""
      foo = [[]]
      bar = []

      def f():
        for obj in foo[0]:
          bar.append(obj)

      def g():
        f()
        foo[0].append(42)
        f()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        foo: list<list<int>>
        bar: list<int>

        def f() -> NoneType
        def g() -> NoneType
      """)

  def testTwiceNestedList(self):
    with self.Infer("""
      foo = [[[]]]
      bar = []

      def f():
        for obj in foo[0][0]:
          bar.append(obj)

      def g():
        f()
        foo[0][0].append(42)
        f()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        foo: list<list<list<int>>>
        bar: list<int>

        def f() -> NoneType
        def g() -> NoneType
      """)

  def testNestedListInClass(self):
    with self.Infer("""
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
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class Container:
          foo: list<list<int>>
          bar: list<int>

        container: Container

        def f() -> NoneType
        def g() -> NoneType
      """)

if __name__ == "__main__":
  test_inference.main()
