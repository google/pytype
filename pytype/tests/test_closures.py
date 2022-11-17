"""Tests for closures."""

from pytype.tests import test_base


class ClosuresTest(test_base.BaseTest):
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
      def f(x: List[float]) -> Callable[[Any], Any]: ...
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
    self.Check("""
      def make_adder(x, y=13, z=43):
        def add(q, r=11):
          return x+y+z+q+r
        return add
      a = make_adder(10, 17)
      print(a(7))
      assert a(7) == 88
      """)

  def test_closures_with_defaults_inference(self):
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
      def caller() -> List[str]: ...
      def f() -> Callable[[], Any]: ...
      def g(funcptr: Callable[[], Any]) -> List[str]: ...
    """)

  def test_deep_closures(self):
    self.Check("""
      def f1(a):
        b = 2*a
        def f2(c):
          d = 2*c
          def f3(e):
            f = 2*e
            def f4(g):
              h = 2*g
              return a+b+c+d+e+f+g+h
            return f4
          return f3
        return f2
      answer = f1(3)(4)(5)(6)
      print(answer)
      assert answer == 54
      """)

  def test_deep_closures_inference(self):
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
    # Regression test for a crash; see vm_utils.load_closure_cell.
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

  def test_undefined_var(self):
    err = self.CheckWithErrors("""
      def f(param):
        pass

      def outer_fn():
        def inner_fn():
          f(param=yet_to_be_defined)  # name-error[e]
        inner_fn()
        yet_to_be_defined = 0
    """)
    self.assertErrorRegexes(err, {"e": r"yet_to_be_defined.*not.defined"})

  def test_closures(self):
    self.Check("""
      def make_adder(x):
        def add(y):
          return x+y
        return add
      a = make_adder(10)
      print(a(7))
      assert a(7) == 17
      """)

  def test_closures_store_deref(self):
    self.Check("""
      def make_adder(x):
        z = x+1
        def add(y):
          return x+y+z
        return add
      a = make_adder(10)
      print(a(7))
      assert a(7) == 28
      """)

  def test_empty_vs_deleted(self):
    self.Check("""
      import collections
      Foo = collections.namedtuple('Foo', 'x')
      def f():
        (x,) = Foo(10)  # x gets set to abstract.Empty here.
        def g():
          return x  # Should not raise a name-error
    """)

  def test_closures_in_loop(self):
    self.Check("""
      def make_fns(x):
        fns = []
        for i in range(x):
          fns.append(lambda i=i: i)
        return fns
      fns = make_fns(3)
      for f in fns:
        print(f())
      assert (fns[0](), fns[1](), fns[2]()) == (0, 1, 2)
      """)

  def test_closure(self):
    ty = self.Infer("""
      import ctypes
      f = 0
      def e():
        global f
        s = 0
        f = (lambda: ctypes.foo(s))  # ctypes.foo doesn't exist
        return f()
      e()
    """, report_errors=False)
    self.assertHasReturnType(ty.Lookup("e"), self.anything)
    self.assertTrue(ty.Lookup("f"))

  def test_recursion(self):
    self.Check("""
      def f(x):
        def g(y):
          f({x: y})
    """)

  def test_unbound_closure_variable(self):
    self.CheckWithErrors("""
      def foo():
        def bar():
          return tuple(xs)  # name-error
        xs = bar()
      foo()
    """)

  def test_attribute_error(self):
    errors = self.CheckWithErrors("""
      def f(x: int):
        def g():
          return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})

  def test_name_error(self):
    self.CheckWithErrors("""
      def f(x):
        try:
          return [g() for y in x]  # name-error
        except:
          return []
        def g():
          pass
    """)


class ClosuresTestPy3(test_base.BaseTest):
  """Tests for closures in Python 3."""

  def test_if_split_delete_deref(self):
    ty = self.Infer("""
      def f(a: int):
        x = "hello"
        def g():
          nonlocal x
          x = 42
        if a:
          g()
        else:
          return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      def f(a: int) -> Optional[str]: ...
    """)

  def test_closures_delete_deref(self):
    self.InferWithErrors("""
      def f():
        x = "hello"
        def g():
          nonlocal x  # force x to be stored in a closure cell
          x = 10
        del x
        return x  # name-error
    """)

  def test_nonlocal(self):
    ty = self.Infer("""
      def f():
        x = "hello"
        def g():
          nonlocal x
          x = 10
        g()
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_nonlocal_delete_deref(self):
    self.InferWithErrors("""
      def f():
        x = True
        def g():
          nonlocal x
          del x
        g()
        return x  # name-error
    """)

  def test_reuse_after_delete_deref(self):
    ty = self.Infer("""
      def f():
        x = True
        def g():
          nonlocal x
          del x
        g()
        x = 42
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_closure_annotations(self):
    errors = self.CheckWithErrors("""
      def f():
        a = 1
        def g(x: int) -> int:
          a  # makes sure g is a closure
          return "hello"  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_filter_before_delete(self):
    # TODO(b/117463644): Remove the disable on line 7.
    self.CheckWithErrors("""
      from typing import Optional
      def f(x: Optional[str]):
        if x is None:
          raise TypeError()
        def nested():
          nonlocal x
          print(x.upper())  # pytype: disable=name-error
          del x
        nested()
        return x  # name-error
    """)


if __name__ == "__main__":
  test_base.main()
