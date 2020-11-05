"""Tests for closures."""

from pytype.tests import test_base


class ClosuresTest(test_base.TargetIndependentTest):
  """Tests for closures."""

  def test_basic_closure(self):
    ty = self.Infer("""
      def f():
        x = 3
        def g():
          return x
        return g
      def caller():
        return f()()
      caller()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      def f() -> Callable[[], Any]: ...
      def caller() -> int: ...
    """)

  def test_closure_on_arg(self):
    ty = self.Infer("""
      def f(x):
        def g():
          return x
        return g
      def caller():
        return f(3)()
      caller()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      def f(x: int) -> Callable[[], Any]: ...
      def caller() -> int: ...
    """)

  def test_closure_with_arg(self):
    ty = self.Infer("""
      def f(x):
        def g(y):
          return x[y]
        return g
      def caller():
        return f([1.0])(0)
      caller()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Callable
      def f(x: List[float, ...]) -> Callable[[Any], Any]: ...
      def caller() -> float: ...
    """)

  def test_closure_same_name(self):
    ty = self.Infer("""
      def f():
        x = 1
        y = 2
        def g():
          print(y)
          x = "foo"
          def h():
            return x
          return h
        return g
      def caller():
        return f()()()
      caller()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      def f() -> Callable[[], Any]: ...
      def caller() -> str: ...
    """)

  def test_closures_add(self):
    ty = self.Infer("""
      def f(x):
        z = x+1
        def g(y):
          return x+y+z
        return g
      def caller():
        return f(1)(2)
      caller()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      def caller() -> int: ...
      def f(x: int) -> Callable[[Any], Any]: ...
    """)

  def test_closures_with_defaults(self):
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      def f(x: int, y: int=..., z: int=...) -> Callable: ...
      def t1() -> int: ...
      def t2() -> int: ...
      def t3() -> int: ...
    """)

  def test_closure_scope(self):
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, List
      def caller() -> List[str, ...]: ...
      def f() -> Callable[[], Any]: ...
      def g(funcptr: Callable[[], Any]) -> List[str, ...]: ...
    """)

  def test_deep_closures(self):
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      def f1(a: int) -> Callable[[Any], Any]: ...
      def caller() -> int: ...
    """)

  def test_no_visible_bindings(self):
    # Regression test for a crash; see vm.VirtualMachine.load_closure_cell.
    self.Check("""
      def foo():
        name = __any_object__
        def msg():
          return name
        while True:
          if __random__:
            name = __any_object__
            raise ValueError(msg())
          else:
            break
        if __random__:
          return {'': name}
        return {'': name}
    """)


test_base.main(globals(), __name__ == "__main__")
