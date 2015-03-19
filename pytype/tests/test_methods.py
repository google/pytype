import unittest

from pytype.pytd import pytd
from pytype.tests import test_inference

# TODO(pludemann): add some tests for methods with 1st arg named something
#                  other than "self".


class MethodsTest(test_inference.InferenceTest):

  def testFlowAndReplacementSanity(self):
    with self.Infer("""
      def f(x):
        if x:
          x = 42
          y = x
          x = 1
        return x + 4
      f(4)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((self.int,), self.int))

  def testMultipleReturns(self):
    with self.Infer("""
      def f(x):
        if x:
          return 1
        else:
          return 1.5
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"),
                                   ((self.int,), self.intorfloat))

  def testLoopsSanity(self):
    with self.Infer("""
      def f():
        x = 4
        y = -10
        for i in xrange(1000):
          x = x + (i+y)
          y = i
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasOnlySignatures(ty.Lookup("f"), ((), self.int))

  def testAddInt(self):
    with self.Infer("""
      def f(x):
        return x + 1
      f(3.2)
      f(3)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)
      self.assertHasSignature(ty.Lookup("f"), (self.float,), self.float)

  def testAddFloat(self):
    with self.Infer("""
      def f(x):
        return x + 1.2
      f(3.2)
      f(3)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.intorfloat,), self.float)

  def testAddStr(self):
    with self.Infer("""
      def f(x):
        return x + "Test"
      f(3.2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertItemsEqual(ty.functions, [])

  def testConjugate(self):
    with self.Infer("""
      def f(x, y):
        return x.conjugate()
      f(int(), int())
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.int)

  def testClassSanity(self):
    with self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 1

        def get_x(self):
          return self.x

        def set_x(self, x):
          self.x = x
      a = A()
      y = a.x
      x1 = a.get_x()
      a.set_x(1.2)
      x2 = a.get_x()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("A").Lookup("set_x"),
                              (pytd.ClassType("A"), self.float), self.none_type)
      self.assertHasSignature(ty.Lookup("A").Lookup("get_x"),
                              (pytd.ClassType("A"),), self.intorfloat)

  def testBooleanOp(self):
    with self.Infer("""
      def f(x, y):
        return 1 < x < 10
        return 1 > x > 10
      f(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.bool)

  def testIs(self):
    with self.Infer("""
      def f(a, b):
        return a is b
      f(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.bool)

  def testIsNot(self):
    with self.Infer("""
      def f(a, b):
        return a is not b
      f(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.bool)

  def testSlice(self):
    with self.Infer("""
      def f(x):
        a, b = x
        return (a, b)
      f((1, 2))
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int_tuple,), self.int_tuple)

  def testConvert(self):
    with self.Infer("""
      def f(x):
        return repr(x)
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.str)

  def testNot(self):
    with self.Infer("""
      def f(x):
        return not x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.bool)

  def testPositive(self):
    with self.Infer("""
      def f(x):
        return +x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testNegative(self):
    with self.Infer("""
      def f(x):
        return -x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testInvert(self):
    with self.Infer("""
      def f(x):
        return ~x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testInheritance(self):
    with self.Infer("""
      class Base(object):
        def get_suffix(self):
            return u""

      class Leaf(Base):
        def __init__(self):
          pass

      def test():
        l1 = Leaf()
        return l1.get_suffix()

      if __name__ == "__main__":
        test()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("test"), (), self.unicode)

  def testProperty(self):
    with self.Infer("""
      class A(object):
        @property
        def my_property(self):
          return 1
        def foo(self):
          return self.my_property

      def test():
        x = A()
        return x.foo()

      test()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("test"), (), self.int)

  def testExplicitProperty(self):
    with self.Infer("""
      class B(object):
        def _my_getter(self):
          return 1
        def _my_setter(self):
          pass
        my_property = property(_my_getter, _my_setter)
      def test():
        b = B()
        b.my_property = 3
        return b.my_property
      test()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("test"), (), self.int)

  def testGenerators(self):
    with self.Infer("""
      def f():
        yield 3
      def g():
        for x in f():
          return x
      g()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.generator)

  def testListGenerator(self):
    with self.Infer("""
      def f():
        yield 3
      def g():
        for x in list(f()):
          return x
      g()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.generator)

  def testRecursion(self):
    with self.Infer("""
      def f():
        if f:
          return f()
        else:
          return 3
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testInNotIn(self):
    with self.Infer("""
      def f(x):
        if x:
          return x in [x]
        else:
          return x not in [x]

      f(3)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.bool)

  def testComplexCFG(self):
    with self.Infer("""
      def g(h):
        return 2
      def h():
        return 1
      def f(x):
        if True:
          while x:
            pass
          while x:
            pass
          assert x
        return g(h())
      if __name__ == "__main__":
        f(0)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testBranchAndLoopCFG(self):
    with self.Infer("""
      def f():
          if True:
            while True:
              pass
            return False
          g()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.bool)

  def testClosure(self):
    with self.Infer("""
       def f(x, y):
         closure = lambda: x + y
         return closure()
       f(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.int)

  def testDeepClosure(self):
    with self.Infer("""
       def f():
         x = 3
         def g():
           def h():
             return x
           return h
         return g()()
       f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testTwoClosures(self):
    with self.Infer("""
       def f():
         def g():
           return 3
         def h():
           return g
         return h()()
       f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testClosureBindingArguments(self):
    with self.Infer("""
       def f(x):
         y = 1
         def g(z):
           return x + y + z
         return g(1)
       f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testClosureOnMultiType(self):
    with self.Infer("""
      def f():
        if __any_object__:
          x = 1
        else:
          x = 3.5
        return (lambda: x)()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.intorfloat)

  def testCallKwArgs(self):
    with self.Infer("""
      def f(x, y=3):
        return x + y
      f(40, **{"y": 2})
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testCallArgs(self):
    with self.Infer("""
      def f(x):
        return x
      args = (3,)
      f(*args)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testCallArgsKwArgs(self):
    with self.Infer("""
      def f(x):
        return x
      args = (3,)
      kwargs = {}
      f(*args, **kwargs)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testCallPositionalAsKeyword(self):
    with self.Infer("""
      def f(named):
        return named
      f(named=3)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testTwoKeywords(self):
    with self.Infer("""
      def f(x, y):
        return x if x else y
      f(x=3, y=4)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.int)

  @unittest.skip("Needs order matching")
  def testTwoDistinctKeywordParams(self):
    f = """
      def f(x, y):
        return x if x else y
    """

    with self.Infer(f + """
      f(x=3, y="foo")
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.str), self.int)

    with self.Infer(f + """
      f(y="foo", x=3)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int, self.str), self.int)

  def testStarStar(self):
    with self.Infer("""
      def f(x):
        return x
      f(**{"x": 3})
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testStarStar2(self):
    with self.Infer("""
      def f(x):
        return x
      kwargs = {}
      kwargs['x'] = 3
      f(**kwargs)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  @unittest.skip("Needs better pytd for 'dict'")
  def testStarStar3(self):
    with self.Infer("""
      def f(x):
        return x
      kwargs = dict(x=3)
      f(**kwargs)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testAmbiguousStarStar(self):
    with self.Infer("""
      def f(x):
        return 0
      kwargs = {}
      if __any_object__:
        kwargs['x'] = 3
      else:
        kwargs['x'] = 3.1
      f(**kwargs)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.intorfloat,), self.int)

  def testStarArgsType(self):
    with self.Infer("""
      def f(*args, **kwds):
        return args
      f(3)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int_tuple)

  def testStarStarKwargsType(self):
    with self.Infer("""
      def f(*args, **kwargs):
        return kwargs
      f(foo=3, bar=4)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.str_int_dict)

  def testNoneOrFunction(self):
    with self.Infer("""
      def g():
        return 3

      def f():
        if g:
          x = None
        else:
          x = g

        if x:
          return x()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testDefineClassMethod(self):
    with self.Infer("""
      class A(object):
        @classmethod
        def myclassmethod(*args):
          return 3
      def f():
        a = A()
        return a.myclassmethod
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.function)

  def testClassMethodSmoke(self):
    with self.Infer("""
      class A(object):
        @classmethod
        def mystaticmethod(x, y):
          return x + y
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      ty.Lookup("A")

  def testStaticMethodSmoke(self):
    with self.Infer("""
      class A(object):
        @staticmethod
        def mystaticmethod(x, y):
          return x + y
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      ty.Lookup("A")

  def testClassMethod(self):
    with self.Infer("""
      class A(object):
        @classmethod
        def myclassmethod(cls):
          return 3
      def f():
        return A().myclassmethod()
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testStaticMethod(self):
    with self.Infer("""
      class A(object):
        @staticmethod
        def mystaticmethod(x, y):
          return x + y
      def f():
        return A.mystaticmethod(1, 2)
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testSimpleStaticMethod(self):
    with self.Infer("""
      class MyClass(object):
        @staticmethod
        def static_method():
          return None
      MyClass().static_method()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      # Only check that the class is there. pytd doesn't yet support staticmethod.
      ty.Lookup("MyClass")

  def testDefaultReturnType(self):
    with self.Infer("""
      def f(x=None):
          x = list(x)
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("f"), self.none_type)

  def testLookup(self):
    with self.Infer("""
      class Cloneable(object):
          def __init__(self):
            pass

          def clone(self):
              return Cloneable()
      Cloneable().clone()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      cls = ty.Lookup("Cloneable")
      method = cls.Lookup("clone")
      self.assertOnlyHasReturnType(method, pytd.ClassType("Cloneable", cls))

  def testDecorator(self):
    with self.Infer("""
      class MyStaticMethodDecorator(object):
        def __init__(self, func):
          self.__func__ = func
        def __get__(self, obj, cls):
          return self.__func__

      class A(object):
        @MyStaticMethodDecorator
        def mystaticmethod(x, y):
          return x + y

      def f():
        return A.mystaticmethod(1, 2)

      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      f = ty.Lookup("f")
      self.assertOnlyHasReturnType(f, self.int)

  @unittest.skip("Needs enhanced naming of unknowns")
  def testUnknownDecorator(self):
    with self.Infer("""
      @__any_object__
      def f():
        return 3j
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      f = ty.Lookup("f")
      self.assertOnlyHasReturnType(f, self.int)

  def testFuncName(self):
    with self.Infer("""
      def f():
        pass
      f.func_name = 3.1415
      def g():
        return f.func_name
      g()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("g"), (), self.float)

if __name__ == "__main__":
  test_inference.main()
