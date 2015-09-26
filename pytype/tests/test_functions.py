"""Test functions etc, for Byterun."""


import unittest

from pytype.tests import test_inference


class TestFunctions(test_inference.InferenceTest):

  def test_functions(self):
    self.assertNoErrors("""\
      def fn(a, b=17, c="Hello", d=[]):
        d.append(99)
        print(a, b, c, d)
      fn(1)
      fn(2, 3)
      fn(3, c="Bye")
      fn(4, d=["What?"])
      fn(5, "b", "c")
      """)

  def test_function_locals(self):
    self.assertNoErrors("""\
      def f():
        x = "Spite"
        print(x)
      def g():
        x = "Malice"
        print(x)
      x = "Humility"
      f()
      print(x)
      g()
      print(x)
      """)

  def test_recursion(self):
    self.assertNoErrors("""\
      def fact(n):
        if n <= 1:
          return 1
        else:
          return n * fact(n-1)
      f6 = fact(6)
      print(f6)
      assert f6 == 720
      """)

  def test_calling_functions_with_args_kwargs(self):
    self.assertNoErrors("""\
      def fn(a, b=17, c="Hello", d=[]):
        d.append(99)
        print(a, b, c, d)
      fn(6, *[77, 88])
      fn(**{'c': 23, 'a': 7})
      fn(6, *[77], **{'c': 23, 'd': [123]})
      """)

  def test_calling_functions_with_generator_args(self):
    self.assertNoErrors("""\
      class A(object):
        def next(self):
          raise StopIteration()
        def __iter__(self):
          return A()
      def f(*args):
        pass
      f(*A())
    """)

  def test_defining_functions_with_args_kwargs(self):
    self.assertNoErrors("""\
      def fn(*args):
        print("args is %r" % (args,))
      fn(1, 2)
      """)
    self.assertNoErrors("""\
      def fn(**kwargs):
        print("kwargs is %r" % (kwargs,))
      fn(red=True, blue=False)
      """)
    self.assertNoErrors("""\
      def fn(*args, **kwargs):
        print("args is %r" % (args,))
        print("kwargs is %r" % (kwargs,))
      fn(1, 2, red=True, blue=False)
      """)
    self.assertNoErrors("""\
      def fn(x, y, *args, **kwargs):
        print("x is %r, y is %r" % (x, y))
        print("args is %r" % (args,))
        print("kwargs is %r" % (kwargs,))
      fn('a', 'b', 1, 2, red=True, blue=False)
      """)

  def test_defining_functions_with_empty_args_kwargs(self):
    self.assertNoErrors("""\
      def fn(*args):
        print("args is %r" % (args,))
      fn()
      """)
    self.assertNoErrors("""\
      def fn(**kwargs):
        print("kwargs is %r" % (kwargs,))
      fn()
      """)
    self.assertNoErrors("""\
      def fn(*args, **kwargs):
        print("args is %r, kwargs is %r" % (args, kwargs))
      fn()
      """)

  def test_partial(self):
    self.assertNoErrors("""\
      from _functools import partial

      def f(a,b):
        return a-b

      f7 = partial(f, 7)
      four = f7(3)
      assert four == 4
      """)

  def test_partial_with_kwargs(self):
    self.assertNoErrors("""\
      from _functools import partial

      def f(a,b,c=0,d=0):
        return (a,b,c,d)

      f7 = partial(f, b=7, c=1)
      them = f7(10)
      assert them == (10,7,1,0)
      """)

  def test_wraps(self):
    self.assertNoErrors("""\
      from functools import wraps
      def my_decorator(f):
        dec = wraps(f)
        def wrapper(*args, **kwds):
          print('Calling decorated function')
          return f(*args, **kwds)
        wrapper = dec(wrapper)
        return wrapper

      @my_decorator
      def example():
        '''Docstring'''
        return 17

      assert example() == 17
      """)


class TestClosures(test_inference.InferenceTest):

  def test_closures(self):
    self.assertNoErrors("""\
      def make_adder(x):
        def add(y):
          return x+y
        return add
      a = make_adder(10)
      print(a(7))
      assert a(7) == 17
      """)

  def test_closures_store_deref(self):
    self.assertNoErrors("""\
      def make_adder(x):
        z = x+1
        def add(y):
          return x+y+z
        return add
      a = make_adder(10)
      print(a(7))
      assert a(7) == 28
      """)

  def test_closures_in_loop(self):
    self.assertNoErrors("""\
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

  def test_closures_with_defaults(self):
    self.assertNoErrors("""\
      def make_adder(x, y=13, z=43):
        def add(q, r=11):
          return x+y+z+q+r
        return add
      a = make_adder(10, 17)
      print(a(7))
      assert a(7) == 88
      """)

  def test_deep_closures(self):
    self.assertNoErrors("""\
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

class TestGenerators(test_inference.InferenceTest):

  def test_first(self):
    self.assertNoErrors("""\
      def two():
        yield 1
        yield 2
      for i in two():
        print(i)
      """)

  def test_partial_generator(self):
    self.assertNoErrors("""\
      from _functools import partial

      def f(a,b):
        num = a+b
        while num:
          yield num
          num -= 1

      f2 = partial(f, 2)
      three = f2(1)
      assert list(three) == [3,2,1]
      """)

  def test_yield_multiple_values(self):
    # TODO(kramm): The generator doesn't have __iter__?
    self.assertNoCrash("""\
      def triples():
        yield 1, 2, 3
        yield 4, 5, 6

      for a, b, c in triples():
        print(a, b, c)
      """)

  def test_generator_reuse(self):
    self.assertNoErrors("""\
      g = (x*x for x in range(5))
      print(list(g))
      print(list(g))
      """)

  def test_generator_from_generator2(self):
    self.assertNoErrors("""\
      g = (x*x for x in range(3))
      print(list(g))

      g = (x*x for x in range(5))
      g = (y+1 for y in g)
      print(list(g))
      """)

  def test_generator_from_generator(self):
    # TODO(kramm): The generator doesn't have __iter__?
    self.assertNoCrash("""\
      class Thing(object):
        RESOURCES = ('abc', 'def')
        def get_abc(self):
          return "ABC"
        def get_def(self):
          return "DEF"
        def resource_info(self):
          for name in self.RESOURCES:
            get_name = 'get_' + name
            yield name, getattr(self, get_name)

        def boom(self):
          #d = list((name, get()) for name, get in self.resource_info())
          d = [(name, get()) for name, get in self.resource_info()]
          return d

      print(Thing().boom())
      """)

  def test_pass_through_args(self):
    with self.Infer("""
      def f(a, b):
        return a * b
      def g(*args, **kwargs):
        return f(*args, **kwargs)
      g(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("g"), self.int)

  def test_pass_through_kwargs(self):
    with self.Infer("""
      def f(a, b):
        return a * b
      def g(*args, **kwargs):
        return f(*args, **kwargs)
      g(a=1, b=2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("g"), self.int)

  def test_closure(self):
    with self.Infer("""
      import ctypes
      f = 0
      def e():
        global f
        s = 0
        f = (lambda: ctypes.foo(s))  # ctypes.foo doesn't exist
        return f()
      e()
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertHasReturnType(ty.Lookup("e"), self.anything)
      self.assertTrue(ty.Lookup("f"))

  def testListComprehension(self):
    with self.Infer("""
      def f(elements):
        return "%s" % ",".join(t for t in elements)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(elements) -> str
      """)

  def testTupleArgsSmoke(self):
    with self.Infer("""
      def foo((x, y), z):
        pass
    """, deep=True, solve_unknowns=True) as unused_ty:
      # Smoke test only. pytd doesn't support automatic tuple unpacking in args.
      pass

  def test_matching_functions(self):
    with self.Infer("""
      def f():
        return 3

      class Foo(object):
        def match_method(self):
          return map(self.method, [])
        def match_function(self):
          return map(f, [])
        def match_pytd_function(self):
          return map(map, [])
        def match_bound_pytd_function(self):
          return map({}.keys, [])
        def method(self):
          pass
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> int
        class Foo:
          def match_method(self) -> list<nothing>
          def match_function(self) -> list<nothing>
          def match_pytd_function(self) -> list<nothing>
          def match_bound_pytd_function(self) -> list<nothing>
          def method(self) -> NoneType
      """)


if __name__ == "__main__":
  test_inference.main()
