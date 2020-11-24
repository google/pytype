"""Tests for methods."""
from pytype import file_utils
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class MethodsTest(test_base.TargetIndependentTest):
  """Tests for methods."""

  def test_flow_and_replacement_sanity(self):
    ty = self.Infer("""
      def f(x):
        if x:
          x = 42
          y = x
          x = 1
        return x + 4
      f(4)
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((self.int,), self.int))

  def test_multiple_returns(self):
    ty = self.Infer("""
      def f(x):
        if x:
          return 1
        else:
          return 1.5
      f(0)
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"),
                                 ((self.int,), self.intorfloat))

  def test_loops_sanity(self):
    ty = self.Infer("""
      def f():
        x = 4
        y = -10
        for i in range(1000):
          x = x + (i+y)
          y = i
        return x
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasOnlySignatures(ty.Lookup("f"), ((), self.int))

  def test_add_int(self):
    ty = self.Infer("""
      def f(x):
        return x + 1
      f(3.2)
      f(3)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)
    self.assertHasSignature(ty.Lookup("f"), (self.float,), self.float)

  def test_add_float(self):
    ty = self.Infer("""
      def f(x):
        return x + 1.2
      f(3.2)
      f(3)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.intorfloat,), self.float)

  def test_conjugate(self):
    ty = self.Infer("""
      def f(x, y):
        return x.conjugate()
      f(int(), int())
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.int)

  def test_class_sanity(self):
    ty = self.Infer("""
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: A
      x1 = ...  # type: int
      x2 = ...  # type: float
      y = ...  # type: int
      class A(object):
        x = ...  # type: float
        def __init__(self) -> None : ...
        def get_x(self) -> Union[float, int]: ...
        def set_x(self, x: float) -> None: ...
    """)

  def test_boolean_op(self):
    ty = self.Infer("""
      def f(x, y):
        return 1 < x < 10
        return 1 > x > 10
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.bool)

  def test_is(self):
    ty = self.Infer("""
      def f(a, b):
        return a is b
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.bool)

  def test_is_not(self):
    ty = self.Infer("""
      def f(a, b):
        return a is not b
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.bool)

  def test_slice(self):
    ty = self.Infer("""
      def f(x):
        a, b = x
        return (a, b)
      f((1, 2))
    """, deep=False, show_library_calls=True)
    t = pytd.TupleType(self.tuple, (self.int, self.int))
    self.assertHasSignature(ty.Lookup("f"), (t,), t)

  def test_convert(self):
    ty = self.Infer("""
      def f(x):
        return repr(x)
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.str)

  def test_not(self):
    ty = self.Infer("""
      def f(x):
        return not x
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.bool)

  def test_positive(self):
    ty = self.Infer("""
      def f(x):
        return +x
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_negative(self):
    ty = self.Infer("""
      def f(x):
        return -x
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_invert(self):
    ty = self.Infer("""
      def f(x):
        return ~x
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_inheritance(self):
    ty = self.Infer("""
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
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("test"), (), self.unicode)

  def test_property(self):
    ty = self.Infer(
        """
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
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("test"), (), self.int)

  def test_explicit_property(self):
    ty = self.Infer("""
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
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("test"), (), self.int)

  def test_inherited_property(self):
    self.Check("""
      class A(object):
        @property
        def bar(self):
          return 42
      class B(A):
        def foo(self):
          return super(B, self).bar + 42
    """)

  def test_generators(self):
    ty = self.Infer("""
      def f():
        yield 3
      def g():
        for x in f():
          return x
      g()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.generator)

  def test_list_generator(self):
    ty = self.Infer("""
      def f():
        yield 3
      def g():
        for x in list(f()):
          return x
      g()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.generator)

  def test_recursion(self):
    ty = self.Infer("""
      def f():
        if __random__:
          return f()
        else:
          return 3
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_in_not_in(self):
    ty = self.Infer("""
      def f(x):
        if __random__:
          return x in [x]
        else:
          return x not in [x]

      f(3)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.bool)

  def test_complex_cfg(self):
    ty = self.Infer("""
      def g(h):
        return 2
      def h():
        return 1
      def f(x):
        if x:
          while x:
            pass
          while x:
            pass
          assert x
        return g(h())
      if __name__ == "__main__":
        f(0)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_branch_and_loop_cfg(self):
    ty = self.Infer("""
      def g():
          pass
      def f():
          if True:
            while True:
              pass
            return False
          g()
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.bool)

  def test_closure(self):
    ty = self.Infer("""
       def f(x, y):
         closure = lambda: x + y
         return closure()
       f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.int)

  def test_deep_closure(self):
    ty = self.Infer("""
       def f():
         x = 3
         def g():
           def h():
             return x
           return h
         return g()()
       f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_two_closures(self):
    ty = self.Infer("""
       def f():
         def g():
           return 3
         def h():
           return g
         return h()()
       f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_closure_binding_arguments(self):
    ty = self.Infer("""
       def f(x):
         y = 1
         def g(z):
           return x + y + z
         return g(1)
       f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_closure_on_multi_type(self):
    ty = self.Infer("""
      def f():
        if __random__:
          x = 1
        else:
          x = 3.5
        return (lambda: x)()
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.intorfloat)

  def test_call_kwargs(self):
    ty = self.Infer("""
      def f(x, y=3):
        return x + y
      f(40, **{"y": 2})
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.int)

  def test_call_args(self):
    ty = self.Infer("""
      def f(x):
        return x
      args = (3,)
      f(*args)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_call_args_kwargs(self):
    ty = self.Infer("""
      def f(x):
        return x
      args = (3,)
      kwargs = {}
      f(*args, **kwargs)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_call_positional_as_keyword(self):
    ty = self.Infer("""
      def f(named):
        return named
      f(named=3)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_two_keywords(self):
    ty = self.Infer("""
      def f(x, y):
        return x if x else y
      f(x=3, y=4)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.int), self.int)

  def test_two_distinct_keyword_params(self):
    f = """
      def f(x, y):
        return x if x else y
    """

    ty = self.Infer(f + """
      f(x=3, y="foo")
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.str), self.int)

    ty = self.Infer(f + """
      f(y="foo", x=3)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int, self.str), self.int)

  def test_starstar(self):
    ty = self.Infer("""
      def f(x):
        return x
      f(**{"x": 3})
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_starstar2(self):
    ty = self.Infer("""
      def f(x):
        return x
      kwargs = {}
      kwargs['x'] = 3
      f(**kwargs)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  @test_base.skip("Needs better pytd for 'dict'")
  def test_starstar3(self):
    ty = self.Infer("""
      def f(x):
        return x
      kwargs = dict(x=3)
      f(**kwargs)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_ambiguous_starstar(self):
    ty = self.Infer("""
      def f(x):
        return 0
      kwargs = {}
      if __random__:
        kwargs['x'] = 3
      else:
        kwargs['x'] = 3.1
      f(**kwargs)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.intorfloat,), self.int)

  def test_starargs_type(self):
    ty = self.Infer("""
      def f(*args, **kwds):
        return args
      f(3)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"),
                             pytd.TupleType(self.tuple, (self.int,)))

  def test_starargs_type2(self):
    ty = self.Infer("""
      def f(nr, *args):
        return args
      f("foo", 4)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"),
                             pytd.TupleType(self.tuple, (self.int,)))

  def test_starargs_deep(self):
    ty = self.Infer("""
      def f(*args):
        return args
      def g(x, *args):
        return args
      def h(x, y, *args):
        return args
    """)
    self.assertTypesMatchPytd(ty, """
    def f(*args) -> tuple: ...
    def g(x, *args) -> tuple: ...
    def h(x, y, *args) -> tuple: ...
    """)

  def test_starargs_pass_through(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, *args, **kwargs):
          super(Foo, self).__init__(*args, **kwargs)
    """)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      def __init__(self, *args, **kwargs) -> NoneType: ...
    """)

  def test_empty_starargs_type(self):
    ty = self.Infer("""
      def f(nr, *args):
        return args
      f(3)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.nothing_tuple)

  def test_starstar_kwargs_type(self):
    ty = self.Infer("""
      def f(*args, **kwargs):
        return kwargs
      f(foo=3, bar=4)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.str_int_dict)

  def test_starstar_kwargs_type2(self):
    ty = self.Infer("""
      def f(x, y, **kwargs):
        return kwargs
      f("foo", "bar", z=3)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.str_int_dict)

  def test_empty_starstar_kwargs_type(self):
    ty = self.Infer("""
      def f(nr, **kwargs):
        return kwargs
      f(3)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.nothing_nothing_dict)

  def test_starstar_deep(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, **kwargs):
          self.kwargs = kwargs
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Any
    class Foo(object):
      def __init__(self, **kwargs) -> NoneType: ...
      kwargs = ...  # type: dict[str, Any]
    """)

  def test_starstar_deep2(self):
    ty = self.Infer("""
      def f(**kwargs):
        return kwargs
      def g(x, **kwargs):
        return kwargs
      def h(x, y, **kwargs):
        return kwargs
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(**kwargs) -> dict[str, Any]: ...
      def g(x, **kwargs) -> dict[str, Any]: ...
      def h(x, y, **kwargs) -> dict[str, Any]: ...
    """)

  def test_builtin_starargs(self):
    with file_utils.Tempdir() as d:
      d.create_file("myjson.pyi", """
        from typing import Any
        def loads(s: str, encoding: Any = ...) -> Any: ...
      """)
      ty = self.Infer("""
        import myjson
        def f(*args):
          return myjson.loads(*args)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        myjson = ...  # type: module
        def f(*args) -> Any: ...
      """)

  def test_builtin_starstarargs(self):
    with file_utils.Tempdir() as d:
      d.create_file("myjson.pyi", """
        from typing import Any
        def loads(s: str, encoding: Any = ...) -> Any: ...
      """)
      ty = self.Infer("""
        import myjson
        def f(**args):
          return myjson.loads(**args)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        myjson = ...  # type: module
        def f(**args) -> Any: ...
      """)

  def test_builtin_keyword(self):
    with file_utils.Tempdir() as d:
      d.create_file("myjson.pyi", """
        from typing import Any
        def loads(s: str, encoding: Any = ...) -> Any: ...
      """)
      ty = self.Infer("""
        import myjson
        def f():
          return myjson.loads(s="{}")
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        myjson = ...  # type: module

        def f() -> Any: ...
      """)

  def test_none_or_function(self):
    ty = self.Infer("""
      def g():
        return 3

      def f():
        if __random__:
          x = None
        else:
          x = g

        if __random__:
          return x()
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_define_classmethod(self):
    ty = self.Infer("""
      class A(object):
        @classmethod
        def myclassmethod(*args):
          return 3
      def f():
        a = A()
        return a.myclassmethod
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.function)

  def test_classmethod_smoke(self):
    ty = self.Infer("""
      class A(object):
        @classmethod
        def mystaticmethod(x, y):
          return x + y
    """, deep=False, show_library_calls=True)
    ty.Lookup("A")

  def test_staticmethod_smoke(self):
    ty = self.Infer("""
      class A(object):
        @staticmethod
        def mystaticmethod(x, y):
          return x + y
    """, deep=False, show_library_calls=True)
    ty.Lookup("A")

  def test_classmethod(self):
    ty = self.Infer("""
      class A(object):
        @classmethod
        def myclassmethod(cls):
          return 3
      def f():
        return A().myclassmethod()
      f()
    """, deep=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(object):
        @classmethod
        def myclassmethod(cls: Type[A]) -> int: ...
      def f() -> int: ...
    """)

  def test_inherited_classmethod(self):
    self.Check("""
      class A(object):
        @classmethod
        def myclassmethod(cls):
          return 3
      class B(A):
        @classmethod
        def myclassmethod(cls):
          return super(B, cls).myclassmethod()
    """)

  def test_staticmethod(self):
    ty = self.Infer("""
      class A(object):
        @staticmethod
        def mystaticmethod(x, y):
          return x + y
      def f():
        return A.mystaticmethod(1, 2)
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_simple_staticmethod(self):
    ty = self.Infer("""
      class MyClass(object):
        @staticmethod
        def static_method():
          return None
      MyClass().static_method()
    """, deep=False, show_library_calls=True)
    # Only check that the class is there. pytd doesn't yet support staticmethod.
    ty.Lookup("MyClass")

  def test_default_return_type(self):
    ty = self.Infer("""
      def f(x=""):
          x = list(x)
      f()
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.none_type)

  def test_lookup(self):
    ty = self.Infer("""
      class Cloneable(object):
          def __init__(self):
            pass

          def clone(self):
            return type(self)()
      Cloneable().clone()
    """, deep=False, show_library_calls=True)
    cls = ty.Lookup("Cloneable")
    method = cls.Lookup("clone")
    self.assertEqual(pytd_utils.Print(method),
                     "def clone(self: _TCloneable) -> _TCloneable: ...")

  @test_base.skip("pytype thinks 'clone' returns a TypeVar(bound=Cloneable)")
  def test_simple_clone(self):
    ty = self.Infer("""
      class Cloneable(object):
        def clone(self):
          return Cloneable()
    """)
    self.assertTypesMatchPytd(ty, """
      class Cloneable(object):
        def clone(self) -> Cloneable: ...
    """)

  def test_decorator(self):
    ty = self.Infer("""
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
    """, deep=False, show_library_calls=True)
    f = ty.Lookup("f")
    self.assertOnlyHasReturnType(f, self.int)

  def test_unknown_decorator(self):
    ty = self.Infer("""
      @__any_object__
      def f():
        return 3j
      f()
    """, deep=False)
    self.assertEqual(ty.Lookup("f").type, pytd.AnythingType())

  def test_func_name(self):
    ty, _ = self.InferWithErrors("""
      def f():
        pass
      f.func_name = 3.1415  # annotation-type-mismatch
      def g():
        return f.func_name
      g()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("g"), (), self.str)

  def test_register(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      def f():
        lookup = {}
        lookup[''] = Foo
        lookup.get('')()
    """, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.float)

  def test_copy_method(self):
    ty = self.Infer("""
      class Foo(object):
        def mymethod(self, x, y):
          return 3
      myfunction = Foo.mymethod
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def mymethod(self, x, y) -> int: ...
      def myfunction(self: Foo, x, y) -> int: ...
    """)

  def test_assign_method(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      def myfunction(self, x, y):
        return 3
      Foo.mymethod = myfunction
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def mymethod(self, x, y) -> int: ...
      def myfunction(self: Foo, x, y) -> int: ...
    """)

  def test_function_attr(self):
    ty = self.Infer("""
      import os
      def f():
        pass
      class Foo(object):
        def method(self):
          pass
      foo = Foo()
      f.x = 3
      Foo.method.x = "bar"
      foo.method.x = 3j  # overwrites previous line
      os.chmod.x = 3.14
      a = f.x
      b = Foo.method.x
      c = foo.method.x
      d = os.chmod.x
    """)
    self.assertTypesMatchPytd(ty, """
    os = ...  # type: module
    def f() -> NoneType: ...
    class Foo(object):
      def method(self) -> NoneType: ...
    foo = ...  # type: Foo
    a = ...  # type: int
    b = ...  # type: complex
    c = ...  # type: complex
    d = ...  # type: float
    """)

  def test_json(self):
    ty = self.Infer("""
      import json
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
    json = ...  # type: module
    """)

  def test_new(self):
    ty = self.Infer("""
      x = str.__new__(str)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: str
    """)

  def test_override_new(self):
    ty = self.Infer("""
      class Foo(str):
        def __new__(cls, string):
          return str.__new__(cls, string)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo(str):
        def __new__(cls: Type[_TFoo], string) -> _TFoo: ...
    """)

  def test_inherit_new(self):
    ty = self.Infer("""
      class Foo(str): pass
      foo = Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(str): ...
      foo = ...  # type: Foo
    """)

  def test_attribute_in_new(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls, name):
          self = super(Foo, cls).__new__(cls)
          self.name = name
          return self
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo(object):
        name = ...  # type: Any
        def __new__(cls: Type[_TFoo], name) -> _TFoo: ...
    """)

  def test_attributes_in_new_and_init(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls):
          self = super(Foo, cls).__new__(cls)
          self.name = "Foo"
          return self
        def __init__(self):
          self.nickname = 400
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo(object):
        name = ...  # type: str
        nickname = ...  # type: int
        def __new__(cls: Type[_TFoo]) -> _TFoo: ...
        def __init__(self) -> None : ...
    """)

  def test_variable_product_complexity_limit(self):
    ty = self.Infer("""
      class A(object):
        def __new__(cls, w, x, y, z):
          pass
      class B(A):
        pass
      class C(A):
        pass
      class D(A):
        pass
      options = [
          (1, 2, 3, 4),
          (5, 6, 7, 8),
          (9, 10, 11, 12),
          (13, 14, 15, 16),
          (17, 18, 19, 20),
      ]
      for w, x, y, z in options:
        A(w, x, y, z)
        B(w, x, y, z)
        C(w, x, y, z)
        D(w, x, y, z)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      class A(object):
        def __new__(cls, w, x, y, z) -> None: ...
      class B(A): ...
      class C(A): ...
      class D(A): ...
      options = ...  # type: List[Tuple[int, int, int, int]]
      w = ...  # type: int
      x = ...  # type: int
      y = ...  # type: int
      z = ...  # type: int
    """)

  def test_return_self(self):
    ty = self.Infer("""
      class Foo(object):
        def __enter__(self):
          return self
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo(object):
        def __enter__(self: _TFoo) -> _TFoo: ...
    """)

  def test_attribute_in_inherited_new(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls, name):
          self = super(Foo, cls).__new__(cls)
          self.name = name
          return self
      class Bar(Foo):
        def __new__(cls):
          return super(Bar, cls).__new__(cls, "")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      _TBar = TypeVar("_TBar", bound=Bar)
      class Foo(object):
        name = ...  # type: Any
        def __new__(cls: Type[_TFoo], name) -> _TFoo: ...
      class Bar(Foo):
        name = ...  # type: str
        def __new__(cls: Type[_TBar]) -> _TBar: ...
    """)


test_base.main(globals(), __name__ == "__main__")
