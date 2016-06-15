"""Tests for closures."""

from pytype.tests import test_inference


class ClosuresTest(test_inference.InferenceTest):
  """Tests for closures."""

  def testBasicClosure(self):
    ty = self.Infer("""
      def f():
        x = 3
        def g():
          return x
        return g
      def caller():
        return f()()
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> function
      def caller() -> int
    """)

  def testClosureOnArg(self):
    ty = self.Infer("""
      def f(x):
        def g():
          return x
        return g
      def caller():
        return f(3)()
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> function
      def caller() -> int
    """)

  def testClosureWithArg(self):
    ty = self.Infer("""
      def f(x):
        def g(y):
          return x[y]
        return g
      def caller():
        return f([1.0])(0)
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: List[float, ...]) -> function
      def caller() -> float
    """)

  def testClosureSameName(self):
    ty = self.Infer("""
      def f():
        x = 1
        y = 2
        def g():
          print y
          x = "foo"
          def h():
            return x
          return h
        return g
      def caller():
        return f()()()
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> function
      def caller() -> str
    """)

  def testClosuresAdd(self):
    ty = self.Infer("""
      def f(x):
        z = x+1
        def g(y):
          return x+y+z
        return g
      def caller():
        return f(1)(2)
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def caller() -> int
      def f(x: int) -> function
    """)

  def testClosuresWithDefaults(self):
    ty = self.Infer("""
      def f(x, y=13, z=43):
        def g(q, r=11):
          return x+y+z+q+r
        return g
      def t1():
        return f(1)(1)
      def t2():
        return f(1, 2)(1, 2)
      def t3():
        return f(1, 2, 3)(1)
      t1()
      t2()
      t3()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: int, ...) -> function
      def t1() -> int
      def t2() -> int
      def t3() -> int
    """)

  def testClosureScope(self):
    ty = self.Infer("""
      def f():
        x = ["foo"]
        def inner():
          x[0] = "bar"
          return x
        return inner
      def g(funcptr):
        x = 5
        def inner():
          return x
        y = funcptr()
        return y
      def caller():
        return g(f())
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def caller() -> List[str, ...]
      def f() -> function
      def g(funcptr: function) -> List[str, ...]
    """)

  def testDeepClosures(self):
    ty = self.Infer("""
      def f1(a):
        b = a
        def f2(c):
          d = c
          def f3(e):
            f = e
            def f4(g):
              h = g
              return a+b+c+d+e+f+g+h
            return f4
          return f3
        return f2
      def caller():
        return f1(3)(4)(5)(6)
      caller()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f1(a: int) -> function
      def caller() -> int
    """)

if __name__ == "__main__":
  test_inference.main()
