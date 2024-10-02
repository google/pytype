"""Tests for methods."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class MethodsTest(test_base.BaseTest):
  """Tests for methods."""

  def test_flow_and_replacement_sanity(self):
    self.Check("""
      def f(x):
        if x:
          x = 42
          y = x
          x = 1
        return x + 4
      assert_type(f(4), int)
    """)

  def test_multiple_returns(self):
    self.Check("""
      def f(x):
        if x:
          return 1
        else:
          return 1.5
      assert_type(f(0), float)
      assert_type(f(1), int)
    """)

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
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int: ...")

  def test_add_int(self):
    self.Check("""
      def f(x):
        return x + 1
      assert_type(f(3.2), float)
      assert_type(f(3), int)
    """)

  def test_conjugate(self):
    self.Check("""
      def f(x, y):
        return x.conjugate()
      assert_type(f(int(), int()), int)
    """)

  def test_class_sanity(self):
    ty = self.Infer("""
      class A:
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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Union
      a: A
      x1: int
      x2: float
      y: int
      class A:
        x: Any
        def __init__(self) -> None : ...
        def get_x(self) -> int: ...
        def set_x(self, x) -> None: ...
    """,
    )

  def test_boolean_op(self):
    self.Check("""
      def f(x, y):
        return 1 < x < 10
        return 1 > x > 10
      assert_type(f(1, 2), bool)
    """)

  def test_is(self):
    self.Check("""
      def f(a, b):
        return a is b
      assert_type(f(1, 2), bool)
    """)

  def test_is_not(self):
    self.Check("""
      def f(a, b):
        return a is not b
      assert_type(f(1, 2), bool)
    """)

  def test_unpack(self):
    self.Check("""
      from typing import Tuple
      def f(x):
        a, b = x
        return (a, b)
      assert_type(f((1, 2)), Tuple[int, int])
    """)

  def test_convert(self):
    ty = self.Infer("""
      def f(x):
        return repr(x)
      f(1)
    """)
    self.assertTypesMatchPytd(ty, "def f(x) -> str: ...")

  def test_not(self):
    ty = self.Infer("""
      def f(x):
        return not x
      f(1)
    """)
    self.assertTypesMatchPytd(ty, "def f(x) -> bool: ...")

  def test_positive(self):
    self.Check("""
      def f(x):
        return +x
      assert_type(f(1), int)
    """)

  def test_negative(self):
    self.Check("""
      def f(x):
        return -x
      assert_type(f(1), int)
    """)

  def test_invert(self):
    self.Check("""
      def f(x):
        return ~x
      assert_type(f(1), int)
    """)

  def test_inheritance(self):
    ty = self.Infer("""
      class Base:
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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Base:
        def get_suffix(self) -> str: ...
      class Leaf(Base):
        def __init__(self) -> None: ...
      def test() -> str: ...
    """,
    )

  def test_property(self):
    ty = self.Infer("""
      class A:
        @property
        def my_property(self):
          return 1
        def foo(self):
          return self.my_property

      def test():
        x = A()
        return x.foo()

      test()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Annotated
      class A:
        my_property: Annotated[int, 'property']
        def foo(self) -> int: ...
      def test() -> int: ...
    """,
    )

  def test_explicit_property(self):
    ty = self.Infer("""
      class B:
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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Annotated
      class B:
        def _my_getter(self) -> int: ...
        def _my_setter(self) -> None: ...
        my_property: Annotated[int, 'property']
      def test() -> int: ...
    """,
    )

  def test_inherited_property(self):
    self.Check("""
      class A:
        @property
        def bar(self):
          return 42
      class B(A):
        def foo(self):
          return super(B, self).bar + 42
    """)

  def test_error_in_property(self):
    self.CheckWithErrors("""
      class Foo:
        @property
        def f(self):
          return self.nonexistent  # attribute-error
    """)

  def test_generators(self):
    ty = self.Infer("""
      def f():
        yield 3
      def g():
        for x in f():
          return x
      g()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Generator
      def f() -> Generator[int, Any, None]: ...
      def g() -> int | None: ...
    """,
    )

  def test_list_generator(self):
    ty = self.Infer("""
      def f():
        yield 3
      def g():
        for x in list(f()):
          return x
      g()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Generator
      def f() -> Generator[int, Any, None]: ...
      def g() -> int | None: ...
    """,
    )

  def test_recursion(self):
    ty = self.Infer("""
      def f():
        if __random__:
          return f()
        else:
          return 3
      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      def f() -> Any: ...
    """,
    )

  def test_in_not_in(self):
    ty = self.Infer("""
      def f(x):
        if __random__:
          return x in [x]
        else:
          return x not in [x]
      f(3)
    """)
    self.assertTypesMatchPytd(ty, "def f(x) -> bool: ...")

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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def g(h) -> int: ...
      def h() -> int: ...
      def f(x) -> int: ...
    """,
    )

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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      def g() -> None: ...
      def f() -> Any: ...
    """,
    )

  def test_closure(self):
    self.Check("""
       def f(x, y):
         closure = lambda: x + y
         return closure()
       assert_type(f(1, 2), int)
    """)

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
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int: ...")

  def test_two_closures(self):
    ty = self.Infer("""
       def f():
         def g():
           return 3
         def h():
           return g
         return h()()
       f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int: ...")

  def test_closure_binding_arguments(self):
    self.Check("""
       def f(x):
         y = 1
         def g(z):
           return x + y + z
         return g(1)
       assert_type(f(1), int)
    """)

  def test_closure_on_multi_type(self):
    ty = self.Infer("""
      def f():
        if __random__:
          x = 1
        else:
          x = 3.5
        return (lambda: x)()
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int | float: ...")

  def test_call_kwargs(self):
    self.Check("""
      def f(x, y=3):
        return x + y
      assert_type(f(40, **{"y": 2}), int)
    """)

  def test_call_args(self):
    self.Check("""
      def f(x):
        return x
      args = (3,)
      assert_type(f(*args), int)
    """)

  def test_call_args_kwargs(self):
    self.Check("""
      def f(x):
        return x
      args = (3,)
      kwargs = {}
      assert_type(f(*args, **kwargs), int)
    """)

  def test_call_positional_as_keyword(self):
    self.Check("""
      def f(named):
        return named
      assert_type(f(named=3), int)
    """)

  def test_two_keywords(self):
    self.Check("""
      def f(x, y):
        return x if x else y
      assert_type(f(x=3, y=4), int)
    """)

  def test_two_distinct_keyword_params(self):
    f = """
      def f(x, y):
        return x if x else y
    """

    self.Check(f + """
      assert_type(f(x=3, y="foo"), int)
    """)

    self.Check(f + """
      assert_type(f(y="foo", x=3), int)
    """)

  def test_starstar(self):
    self.Check("""
      def f(x):
        return x
      assert_type(f(**{"x": 3}), int)
    """)

  def test_starstar2(self):
    self.Check("""
      def f(x):
        return x
      kwargs = {}
      kwargs['x'] = 3
      assert_type(f(**kwargs), int)
    """)

  def test_starstar3(self):
    self.Check("""
      def f(x):
        return x
      kwargs = dict(x=3)
      assert_type(f(**kwargs), int)
    """)

  def test_starargs_type(self):
    self.Check("""
      from typing import Tuple
      def f(*args, **kwds):
        return args
      assert_type(f(3), Tuple[int])
    """)

  def test_starargs_type2(self):
    self.Check("""
      from typing import Tuple
      def f(nr, *args):
        return args
      assert_type(f("foo", 4), Tuple[int])
    """)

  def test_starargs_deep(self):
    ty = self.Infer("""
      def f(*args):
        return args
      def g(x, *args):
        return args
      def h(x, y, *args):
        return args
    """)
    self.assertTypesMatchPytd(
        ty,
        """
    def f(*args) -> tuple: ...
    def g(x, *args) -> tuple: ...
    def h(x, y, *args) -> tuple: ...
    """,
    )

  def test_starargs_pass_through(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self, *args, **kwargs):
          super(Foo, self).__init__(*args, **kwargs)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
    class Foo:
      def __init__(self, *args, **kwargs) -> NoneType: ...
    """,
    )

  def test_empty_starargs_type(self):
    self.Check("""
      from typing import Tuple
      def f(nr, *args):
        return args
      assert_type(f(3), Tuple[()])
    """)

  def test_starstar_kwargs_type(self):
    self.Check("""
      from typing import Dict
      def f(*args, **kwargs):
        return kwargs
      assert_type(f(foo=3, bar=4), Dict[str, int])
    """)

  def test_starstar_kwargs_type2(self):
    self.Check("""
      from typing import Dict
      def f(x, y, **kwargs):
        return kwargs
      assert_type(f("foo", "bar", z=3), Dict[str, int])
    """)

  def test_empty_starstar_kwargs_type(self):
    self.Check("""
      def f(nr, **kwargs):
        return kwargs
      assert_type(f(3), "dict[nothing, nothing]")
    """)

  def test_starstar_deep(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self, **kwargs):
          self.kwargs = kwargs
    """)
    self.assertTypesMatchPytd(
        ty,
        """
    from typing import Any
    class Foo:
      def __init__(self, **kwargs) -> NoneType: ...
      kwargs = ...  # type: dict[str, Any]
    """,
    )

  def test_starstar_deep2(self):
    ty = self.Infer("""
      def f(**kwargs):
        return kwargs
      def g(x, **kwargs):
        return kwargs
      def h(x, y, **kwargs):
        return kwargs
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      def f(**kwargs) -> dict[str, Any]: ...
      def g(x, **kwargs) -> dict[str, Any]: ...
      def h(x, y, **kwargs) -> dict[str, Any]: ...
    """,
    )

  def test_builtin_starargs(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "myjson.pyi",
          """
        from typing import Any
        def loads(s: str, encoding: Any = ...) -> Any: ...
      """,
      )
      ty = self.Infer(
          """
        import myjson
        def f(*args):
          return myjson.loads(*args)
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import myjson
        from typing import Any
        def f(*args) -> Any: ...
      """,
      )

  def test_builtin_starstarargs(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "myjson.pyi",
          """
        from typing import Any
        def loads(s: str, encoding: Any = ...) -> Any: ...
      """,
      )
      ty = self.Infer(
          """
        import myjson
        def f(**args):
          return myjson.loads(**args)
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import myjson
        from typing import Any
        def f(**args) -> Any: ...
      """,
      )

  def test_builtin_keyword(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "myjson.pyi",
          """
        from typing import Any
        def loads(s: str, encoding: Any = ...) -> Any: ...
      """,
      )
      ty = self.Infer(
          """
        import myjson
        def f():
          return myjson.loads(s="{}")
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import myjson
        from typing import Any

        def f() -> Any: ...
      """,
      )

  def test_none_or_function(self):
    ty, _ = self.InferWithErrors("""
      def g():
        return 3

      def f():
        if __random__:
          x = None
        else:
          x = g

        if __random__:
          return x()  # not-callable
      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Optional
      def g() -> int: ...
      def f() -> Optional[int]: ...
    """,
    )

  def test_define_classmethod(self):
    ty = self.Infer("""
      class A:
        @classmethod
        def myclassmethod(*args):
          return 3
      def f():
        a = A()
        return a.myclassmethod
      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Callable
      class A:
        @classmethod
        def myclassmethod(*args) -> int: ...
      def f() -> Callable: ...
    """,
    )

  def test_classmethod_smoke(self):
    self.Check("""
      class A:
        @classmethod
        def mystaticmethod(x, y):
          return x + y
    """)

  def test_invalid_classmethod(self):
    ty, err = self.InferWithErrors("""
      def f(x):
        return 42
      class A:
        @classmethod  # not-callable[e]>=3.11
        @f
        def myclassmethod(*args):  # not-callable[e]<3.11
          return 3
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      def f(x) -> int: ...
      class A:
        myclassmethod: Any
    """,
    )
    self.assertErrorSequences(
        err,
        {
            "e": [
                "int",
                "not callable",
                "@classmethod applied",
                "not a function",
            ]
        },
    )

  def test_staticmethod_smoke(self):
    self.Check("""
      class A:
        @staticmethod
        def mystaticmethod(x, y):
          return x + y
    """)

  def test_classmethod(self):
    ty = self.Infer("""
      class A:
        @classmethod
        def myclassmethod(cls):
          return 3
      def f():
        return A().myclassmethod()
      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Type
      class A:
        @classmethod
        def myclassmethod(cls: Type[A]) -> int: ...
      def f() -> int: ...
    """,
    )

  def test_inherited_classmethod(self):
    self.Check("""
      class A:
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
      class A:
        @staticmethod
        def mystaticmethod(x, y):
          return x + y
      def f():
        return A.mystaticmethod(1, 2)
      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      class A:
        @staticmethod
        def mystaticmethod(x, y) -> Any: ...
      def f() -> int: ...
    """,
    )

  def test_simple_staticmethod(self):
    self.Check("""
      class MyClass:
        @staticmethod
        def static_method():
          return None
      MyClass().static_method()
    """)

  def test_default_return_type(self):
    ty = self.Infer("""
      def f(x=""):
          x = list(x)
      f()
    """)
    self.assertTypesMatchPytd(ty, "def f(x=...) -> None: ...")

  def test_lookup(self):
    ty = self.Infer("""
      class Cloneable:
          def __init__(self):
            pass

          def clone(self):
            return type(self)()
      Cloneable().clone()
    """)
    cls = ty.Lookup("Cloneable")
    method = cls.Lookup("clone")
    self.assertEqual(
        pytd_utils.Print(method),
        "def clone(self: _TCloneable) -> _TCloneable: ...",
    )

  @test_base.skip("pytype thinks 'clone' returns a TypeVar(bound=Cloneable)")
  def test_simple_clone(self):
    ty = self.Infer("""
      class Cloneable:
        def clone(self):
          return Cloneable()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Cloneable:
        def clone(self) -> Cloneable: ...
    """,
    )

  def test_decorator(self):
    ty = self.Infer("""
      class MyStaticMethodDecorator:
        def __init__(self, func):
          self.__func__ = func
        def __get__(self, obj, cls):
          return self.__func__

      class A:
        @MyStaticMethodDecorator
        def mystaticmethod(x, y):
          return x + y

      def f():
        return A.mystaticmethod(1, 2)

      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      class MyStaticMethodDecorator:
        __func__: Any
        def __init__(self, func) -> None: ...
        def __get__(self, obj, cls) -> Any: ...
      class A:
        mystaticmethod: Any
      def f() -> int: ...
    """,
    )

  def test_unknown_decorator(self):
    ty = self.Infer("""
      @__any_object__
      def f():
        return 3j
      f()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      f: Any
    """,
    )

  def test_func_name(self):
    ty, _ = self.InferWithErrors("""
      def f():
        pass
      f.func_name = 3.1415
      def g():
        return f.func_name
      g()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def f() -> None: ...
      def g() -> float: ...
    """,
    )

  def test_register(self):
    ty, _ = self.InferWithErrors("""
      class Foo:
        pass
      def f():
        lookup = {}
        lookup[''] = Foo
        return lookup.get('')()  # not-callable
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo: ...
      def f() -> Foo: ...
    """,
    )

  def test_copy_method(self):
    ty = self.Infer("""
      class Foo:
        def mymethod(self, x, y):
          return 3
      myfunction = Foo.mymethod
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo:
        def mymethod(self, x, y) -> int: ...
      def myfunction(self: Foo, x, y) -> int: ...
    """,
    )

  def test_assign_method(self):
    ty = self.Infer("""
      class Foo:
        pass
      def myfunction(self, x, y):
        return 3
      Foo.mymethod = myfunction
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo:
        def mymethod(self, x, y) -> int: ...
      def myfunction(self: Foo, x, y) -> int: ...
    """,
    )

  def test_function_attr(self):
    ty = self.Infer("""
      import os
      def f():
        pass
      class Foo:
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
    self.assertTypesMatchPytd(
        ty,
        """
    import os
    def f() -> NoneType: ...
    class Foo:
      def method(self) -> NoneType: ...
    foo = ...  # type: Foo
    a = ...  # type: int
    b = ...  # type: complex
    c = ...  # type: complex
    d = ...  # type: float
    """,
    )

  def test_json(self):
    ty = self.Infer("""
      import json
    """)
    self.assertTypesMatchPytd(
        ty,
        """
    import json
    """,
    )

  def test_new(self):
    ty = self.Infer("""
      x = str.__new__(str)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      x = ...  # type: str
    """,
    )

  def test_override_new(self):
    ty = self.Infer("""
      class Foo(str):
        def __new__(cls, string):
          return str.__new__(cls, string)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo(str):
        def __new__(cls: Type[_TFoo], string) -> _TFoo: ...
    """,
    )

  def test_inherit_new(self):
    ty = self.Infer("""
      class Foo(str): pass
      foo = Foo()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo(str): ...
      foo = ...  # type: Foo
    """,
    )

  def test_attribute_in_new(self):
    ty = self.Infer("""
      class Foo:
        def __new__(cls, name):
          self = super(Foo, cls).__new__(cls)
          self.name = name
          return self
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo:
        name = ...  # type: Any
        def __new__(cls: Type[_TFoo], name) -> _TFoo: ...
    """,
    )

  def test_attributes_in_new_and_init(self):
    ty = self.Infer("""
      class Foo:
        def __new__(cls):
          self = super(Foo, cls).__new__(cls)
          self.name = "Foo"
          return self
        def __init__(self):
          self.nickname = 400
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo:
        name = ...  # type: str
        nickname = ...  # type: int
        def __new__(cls: Type[_TFoo]) -> _TFoo: ...
        def __init__(self) -> None : ...
    """,
    )

  def test_variable_product_complexity_limit(self):
    ty = self.Infer("""
      class A:
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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List, Tuple
      class A:
        def __new__(cls, w, x, y, z) -> None: ...
      class B(A): ...
      class C(A): ...
      class D(A): ...
      options = ...  # type: List[Tuple[int, int, int, int]]
      w = ...  # type: int
      x = ...  # type: int
      y = ...  # type: int
      z = ...  # type: int
    """,
    )

  def test_return_self(self):
    ty = self.Infer("""
      class Foo:
        def __enter__(self):
          return self
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo:
        def __enter__(self: _TFoo) -> _TFoo: ...
    """,
    )

  def test_attribute_in_inherited_new(self):
    ty = self.Infer("""
      class Foo:
        def __new__(cls, name):
          self = super(Foo, cls).__new__(cls)
          self.name = name
          return self
      class Bar(Foo):
        def __new__(cls):
          return super(Bar, cls).__new__(cls, "")
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      _TBar = TypeVar("_TBar", bound=Bar)
      class Foo:
        name = ...  # type: Any
        def __new__(cls: Type[_TFoo], name) -> _TFoo: ...
      class Bar(Foo):
        name = ...  # type: str
        def __new__(cls: Type[_TBar]) -> _TBar: ...
    """,
    )

  def test_pyi_classmethod_and_staticmethod(self):
    # Test that we can access method properties on imported classmethods.
    with self.DepTree([(
        "t.pyi",
        """
      class A:
        @classmethod
        def foo(): ...
        @staticmethod
        def bar(): ...
    """,
    )]):
      self.Check("""
        import t
        a = t.A.foo.__name__
        b = t.A.bar.__name__
        assert_type(a, str)
        assert_type(b, str)
      """)


if __name__ == "__main__":
  test_base.main()
