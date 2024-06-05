"""Basic tests."""

from pytype.tests import test_base


class TestBasic(test_base.BaseTest):
  """Basic tests."""

  def test_constant(self):
    self.Check("17")

  def test_for_loop(self):
    self.Check("""
      out = ""
      for i in range(5):
        out = out + str(i)
      print(out)
      """)

  def test_inplace_operators(self):
    self.assertNoCrash(self.Check, """
      x, y = 2, 3
      x **= y
      assert x == 8 and y == 3
      x *= y
      assert x == 24 and y == 3
      x //= y
      assert x == 8 and y == 3
      x %= y
      assert x == 2 and y == 3
      x += y
      assert x == 5 and y == 3
      x -= y
      assert x == 2 and y == 3
      x <<= y
      assert x == 16 and y == 3
      x >>= y
      assert x == 2 and y == 3

      x = 0x8F
      x &= 0xA5
      assert x == 0x85
      x |= 0x10
      assert x == 0x95
      x ^= 0x33
      assert x == 0xA6
      """)

  def test_inplace_division(self):
    self.assertNoCrash(self.Check, """
      x, y = 24, 3
      x /= y
      assert x == 8 and y == 3
      assert isinstance(x, int)
      x /= y
      assert x == 2 and y == 3
      assert isinstance(x, int)
      """)

  def test_slice(self):
    ty = self.Infer("""
      s = "hello, world"
      def f1():
        return s[3:8]
      def f2():
        return s[:8]
      def f3():
        return s[3:]
      def f4():
        return s[:]
      def f5():
        return s[::-1]
      def f6():
        return s[3:8:2]
      """)
    self.assertTypesMatchPytd(ty, """
    s = ...  # type: str
    def f1() -> str: ...
    def f2() -> str: ...
    def f3() -> str: ...
    def f4() -> str: ...
    def f5() -> str: ...
    def f6() -> str: ...
    """)

  def test_slice_assignment(self):
    self.Check("""
      l = list(range(10))
      l[3:8] = ["x"]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      l[:8] = ["x"]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      l[3:] = ["x"]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      l[:] = ["x"]
      print(l)
      """)

  def test_slice_deletion(self):
    self.Check("""
      l = list(range(10))
      del l[3:8]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      del l[:8]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      del l[3:]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      del l[:]
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      del l[::2]
      print(l)
      """)

  def test_building_stuff(self):
    self.Check("""
      print((1+1, 2+2, 3+3))
      """)
    self.Check("""
      print([1+1, 2+2, 3+3])
      """)
    self.Check("""
      print({1:1+1, 2:2+2, 3:3+3})
      """)

  def test_subscripting(self):
    self.Check("""
      l = list(range(10))
      print("%s %s %s" % (l[0], l[3], l[9]))
      """)
    self.Check("""
      l = list(range(10))
      l[5] = 17
      print(l)
      """)
    self.Check("""
      l = list(range(10))
      del l[5]
      print(l)
      """)

  def test_generator_expression(self):
    self.Check("""
      x = "-".join(str(z) for z in range(5))
      assert x == "0-1-2-3-4"
      """)

  def test_generator_expression2(self):
    # From test_regr.py
    # This failed a different way than the previous join when genexps were
    # broken:
    self.Check("""
      from textwrap import fill
      x = set(['test_str'])
      width = 70
      indent = 4
      blanks = ' ' * indent
      res = fill(' '.join(str(elt) for elt in sorted(x)), width,
            initial_indent=blanks, subsequent_indent=blanks)
      print(res)
      """)

  def test_list_comprehension(self):
    self.Check("""
      x = [z*z for z in range(5)]
      assert x == [0, 1, 4, 9, 16]
      """)

  def test_dict_comprehension(self):
    self.Check("""
      x = {z:z*z for z in range(5)}
      assert x == {0:0, 1:1, 2:4, 3:9, 4:16}
      """)

  def test_set_comprehension(self):
    self.Check("""
      x = {z*z for z in range(5)}
      assert x == {0, 1, 4, 9, 16}
      """)

  def test_list_slice(self):
    self.Check("""
      [1, 2, 3][1:2]
      """)

  def test_strange_sequence_ops(self):
    # from stdlib: test/test_augassign.py
    self.assertNoCrash(self.Check, """
      x = [1,2]
      x += [3,4]
      x *= 2

      assert x == [1, 2, 3, 4, 1, 2, 3, 4]

      x = [1, 2, 3]
      y = x
      x[1:2] *= 2
      y[1:2] += [1]

      assert x == [1, 2, 1, 2, 3]
      assert x is y
      """)

  def test_unary_operators(self):
    self.Check("""
      x = 8
      print(-x, ~x, not x)
      """)

  def test_attributes(self):
    self.Check("""
      l = lambda: 1   # Just to have an object...
      l.foo = 17
      print(hasattr(l, "foo"), l.foo)
      del l.foo
      print(hasattr(l, "foo"))
      """)

  def test_attribute_inplace_ops(self):
    self.assertNoCrash(self.Check, """
      l = lambda: 1   # Just to have an object...
      l.foo = 17
      l.foo -= 3
      print(l.foo)
      """)

  def test_deleting_names(self):
    _, err = self.InferWithErrors("""
      g = 17
      assert g == 17
      del g
      g  # name-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["Variable g", "deleted", "line 3"]})

  def test_deleting_local_names(self):
    self.InferWithErrors("""
      def f():
        l = 23
        assert l == 23
        del l
        l  # name-error
      f()
    """)

  def test_import(self):
    self.Check("""
      import math
      print(math.pi, math.e)
      from math import sqrt
      print(sqrt(2))
      from math import *
      print(sin(2))
      """)

  def test_classes(self):
    self.Check("""
      class Thing:
        def __init__(self, x):
          self.x = x
        def meth(self, y):
          return self.x * y
      thing1 = Thing(2)
      thing2 = Thing(3)
      print(thing1.x, thing2.x)
      print(thing1.meth(4), thing2.meth(5))
      """)

  def test_class_mros(self):
    self.Check("""
      class A: pass
      class B(A): pass
      class C(A): pass
      class D(B, C): pass
      class E(C, B): pass
      print([c.__name__ for c in D.__mro__])
      print([c.__name__ for c in E.__mro__])
      """)

  def test_class_mro_method_calls(self):
    self.Check("""
      class A:
        def f(self): return 'A'
      class B(A): pass
      class C(A):
        def f(self): return 'C'
      class D(B, C): pass
      print(D().f())
      """)

  def test_calling_methods_wrong(self):
    _, errors = self.InferWithErrors("""
      class Thing:
        def __init__(self, x):
          self.x = x
        def meth(self, y):
          return self.x * y
      thing1 = Thing(2)
      print(Thing.meth(14))  # missing-parameter[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"self"})

  def test_calling_subclass_methods(self):
    self.Check("""
      class Thing:
        def foo(self):
          return 17

      class SubThing(Thing):
        pass

      st = SubThing()
      print(st.foo())
      """)

  def test_other_class_methods(self):
    _, errors = self.InferWithErrors("""
      class Thing:
        def foo(self):
          return 17

      class SubThing:
        def bar(self):
          return 9

      st = SubThing()
      print(st.foo())  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"foo.*SubThing"})

  def test_attribute_access(self):
    self.Check("""
      class Thing:
        z = 17
        def __init__(self):
          self.x = 23
      t = Thing()
      print(Thing.z)
      print(t.z)
      print(t.x)
      """)

  def test_attribute_access_error(self):
    errors = self.CheckWithErrors("""
      class Thing:
        z = 17
        def __init__(self):
          self.x = 23
      t = Thing()
      print(t.xyzzy)  # attribute-error[e]
      """)
    self.assertErrorRegexes(errors, {"e": r"xyzzy.*Thing"})

  def test_staticmethods(self):
    self.Check("""
      class Thing:
        @staticmethod
        def smeth(x):
          print(x)
        @classmethod
        def cmeth(cls, x):
          print(x)

      Thing.smeth(1492)
      Thing.cmeth(1776)
      """)

  def test_unbound_methods(self):
    self.Check("""
      class Thing:
        def meth(self, x):
          print(x)
      m = Thing.meth
      m(Thing(), 1815)
      """)

  def test_callback(self):
    self.Check("""
      def lcase(s):
        return s.lower()
      l = ["xyz", "ABC"]
      l.sort(key=lcase)
      print(l)
      assert l == ["ABC", "xyz"]
      """)

  def test_unpacking(self):
    self.Check("""
      a, b, c = (1, 2, 3)
      assert a == 1
      assert b == 2
      assert c == 3
      """)

  def test_jump_if_true_or_pop(self):
    self.Check("""
      def f(a, b):
        return a or b
      assert f(17, 0) == 17
      assert f(0, 23) == 23
      assert f(0, "") == ""
      """)

  def test_jump_if_false_or_pop(self):
    self.Check("""
      def f(a, b):
        return not(a and b)
      assert f(17, 0) is True
      assert f(0, 23) is True
      assert f(0, "") is True
      assert f(17, 23) is False
      """)

  def test_pop_jump_if_true(self):
    self.Check("""
      def f(a):
        if not a:
          return 'foo'
        else:
          return 'bar'
      assert f(0) == 'foo'
      assert f(1) == 'bar'
      """)

  def test_decorator(self):
    self.Check("""
      def verbose(func):
        def _wrapper(*args, **kwargs):
          return func(*args, **kwargs)
        return _wrapper

      @verbose
      def add(x, y):
        return x+y

      add(7, 3)
      """)

  def test_multiple_classes(self):
    # Making classes used to mix together all the class-scoped values
    # across classes.  This test would fail because A.__init__ would be
    # over-written with B.__init__, and A(1, 2, 3) would complain about
    # too many arguments.
    self.Check("""
      class A:
        def __init__(self, a, b, c):
          self.sum = a + b + c

      class B:
        def __init__(self, x):
          self.x = x

      a = A(1, 2, 3)
      b = B(7)
      print(a.sum)
      print(b.x)
      """)

  def test_global(self):
    self.Check("""
      foobar = False
      def baz():
        global foobar
        foobar = True
      baz()
      assert(foobar)
      """)

  def test_delete_global(self):
    self.InferWithErrors("""
      a = 3
      def f():
        global a
        del a
      f()
      x = a  # name-error
      """)

  def test_string(self):
    self.Check("v = '\\xff'")

  def test_string2(self):
    self.Check("v = '\\uD800'")

  def test_del_after_listcomp(self):
    self.Check("""
      def foo(x):
        num = 1
        nums = [num for _ in range(2)]
        del num
    """)


class TestLoops(test_base.BaseTest):
  """Loop tests."""

  def test_for(self):
    self.Check("""
      for i in range(10):
        print(i)
      print("done")
      """)

  def test_break(self):
    self.Check("""
      for i in range(10):
        print(i)
        if i == 7:
          break
      print("done")
      """)

  def test_continue(self):
    # fun fact: this doesn't use CONTINUE_LOOP
    self.Check("""
      for i in range(10):
        if i % 3 == 0:
          continue
        print(i)
      print("done")
      """)

  def test_continue_in_try_except(self):
    self.Check("""
      for i in range(10):
        try:
          if i % 3 == 0:
            continue
          print(i)
        except ValueError:
          pass
      print("done")
      """)

  def test_continue_in_try_finally(self):
    self.Check("""
      for i in range(10):
        try:
          if i % 3 == 0:
            continue
          print(i)
        finally:
          print(".")
      print("done")
      """)


class TestComparisons(test_base.BaseTest):
  """Comparison tests."""

  def test_in(self):
    self.Check("""
      assert "x" in "xyz"
      assert "x" not in "abc"
      assert "x" in ("x", "y", "z")
      assert "x" not in ("a", "b", "c")
      """)

  def test_less(self):
    self.Check("""
      assert 1 < 3
      assert 1 <= 2 and 1 <= 1
      assert "a" < "b"
      assert "a" <= "b" and "a" <= "a"
      """)

  def test_greater(self):
    self.Check("""
      assert 3 > 1
      assert 3 >= 1 and 3 >= 3
      assert "z" > "a"
      assert "z" >= "a" and "z" >= "z"
      """)


class TestSlices(test_base.BaseTest):

  def test_slice_with_step(self):
    self.Check("""
      [0][1:-2:2]
      """)

  def test_slice_on_unknown(self):
    self.Check("""
      __any_object__[1:-2:2]
      """)


if __name__ == "__main__":
  test_base.main()
