"""Test functions."""

from pytype import file_utils
from pytype.tests import test_base


class TestClosures(test_base.TargetIndependentTest):
  """Tests for closures."""

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
        x, _ = Foo(10)  # x gets set to abstract.Empty here.
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


class TestGenerators(test_base.TargetIndependentTest):
  """Tests for generators."""

  def test_first(self):
    self.Check("""
      def two():
        yield 1
        yield 2
      for i in two():
        print(i)
      """)

  def test_partial_generator(self):
    self.Check("""
      from functools import partial

      def f(a,b):
        num = a+b
        while num:
          yield num
          num -= 1

      f2 = partial(f, 2)
      three = f2(1)
      assert list(three) == [3,2,1]
      """)

  def test_unsolvable(self):
    self.assertNoCrash(self.Check, """
      assert list(three) == [3,2,1]
      """)

  def test_yield_multiple_values(self):
    self.assertNoCrash(self.Check, """
      def triples():
        yield 1, 2, 3
        yield 4, 5, 6

      for a, b, c in triples():
        print(a, b, c)
      """)

  def test_generator_reuse(self):
    self.Check("""
      g = (x*x for x in range(5))
      print(list(g))
      print(list(g))
      """)

  def test_generator_from_generator2(self):
    self.Check("""
      g = (x*x for x in range(3))
      print(list(g))

      g = (x*x for x in range(5))
      g = (y+1 for y in g)
      print(list(g))
      """)

  def test_generator_from_generator(self):
    self.assertNoCrash(self.Check, """
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


class PreciseReturnTest(test_base.TargetIndependentTest):
  """Tests for --precise-return."""

  def setUp(self):
    super().setUp()
    self.options.tweak(precise_return=True)

  def test_pytd_return(self):
    ty, errors = self.InferWithErrors("""
      x = 'hello'.startswith(0)  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, "x: bool")
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_param_return(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T: ...
      """)
      ty, _ = self.InferWithErrors("""
        import foo
        x = foo.f()  # missing-parameter
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo: module
        x: Any
      """)

  def test_binop(self):
    ty, _ = self.InferWithErrors("x = 'oops' + 0  # unsupported-operands")
    self.assertTypesMatchPytd(ty, "x: str")

  def test_inplace_op(self):
    ty, _ = self.InferWithErrors("""
      x = []
      x += 0  # unsupported-operands
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x: List[nothing]
    """)


class TestFunctions(test_base.TargetIndependentTest):
  """Tests for functions."""

  def test_functions(self):
    self.Check("""
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
    self.Check("""
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
    self.Check("""
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
    self.Check("""
      def fn(a, b=17, c="Hello", d=[]):
        d.append(99)
        print(a, b, c, d)
      fn(6, *[77, 88])
      fn(**{'c': 23, 'a': 7})
      fn(6, *[77], **{'c': 23, 'd': [123]})
      """)

  def test_calling_functions_with_generator_args(self):
    self.Check("""
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
    self.Check("""
      def fn(*args):
        print("args is %r" % (args,))
      fn(1, 2)
      """)
    self.Check("""
      def fn(**kwargs):
        print("kwargs is %r" % (kwargs,))
      fn(red=True, blue=False)
      """)
    self.Check("""
      def fn(*args, **kwargs):
        print("args is %r" % (args,))
        print("kwargs is %r" % (kwargs,))
      fn(1, 2, red=True, blue=False)
      """)
    self.Check("""
      def fn(x, y, *args, **kwargs):
        print("x is %r, y is %r" % (x, y))
        print("args is %r" % (args,))
        print("kwargs is %r" % (kwargs,))
      fn('a', 'b', 1, 2, red=True, blue=False)
      """)

  def test_defining_functions_with_empty_args_kwargs(self):
    self.Check("""
      def fn(*args):
        print("args is %r" % (args,))
      fn()
      """)
    self.Check("""
      def fn(**kwargs):
        print("kwargs is %r" % (kwargs,))
      fn()
      """)
    self.Check("""
      def fn(*args, **kwargs):
        print("args is %r, kwargs is %r" % (args, kwargs))
      fn()
      """)

  def test_partial(self):
    self.Check("""
      from functools import partial

      def f(a,b):
        return a-b

      f7 = partial(f, 7)
      four = f7(3)
      assert four == 4
      """)

  def test_partial_with_kwargs(self):
    self.Check("""
      from functools import partial

      def f(a,b,c=0,d=0):
        return (a,b,c,d)

      f7 = partial(f, b=7, c=1)
      them = f7(10)
      assert them == (10,7,1,0)
      """)

  def test_wraps(self):
    with file_utils.Tempdir() as d:
      d.create_file("myfunctools.pyi", """
        from typing import Any, Callable, Sequence
        from typing import Any
        _AnyCallable = Callable[..., Any]
        def wraps(wrapped: _AnyCallable, assigned: Sequence[str] = ..., updated: Sequence[str] = ...) -> Callable[[_AnyCallable], _AnyCallable]: ...
      """)
      self.Check("""
        from myfunctools import wraps
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
        """, pythonpath=[d.path])

  def test_pass_through_args(self):
    ty = self.Infer("""
      def f(a, b):
        return a * b
      def g(*args, **kwargs):
        return f(*args, **kwargs)
      g(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("g"), self.int)

  def test_pass_through_kwargs(self):
    ty = self.Infer("""
      def f(a, b):
        return a * b
      def g(*args, **kwargs):
        return f(*args, **kwargs)
      g(a=1, b=2)
    """, deep=False, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("g"), self.int)

  def test_list_comprehension(self):
    ty = self.Infer("""
      def f(elements):
        return "%s" % ",".join(t for t in elements)
    """)
    self.assertTypesMatchPytd(ty, """
      def f(elements) -> str: ...
    """)

  def test_named_arg_unsolvable_max_depth(self):
    # Main test here is for this not to throw a KeyError exception upon hitting
    # maximum depth.
    _, errors = self.InferWithErrors("""
      def f(x):
        return max(foo=repr(__any_object__))  # wrong-keyword-args[e]
    """, deep=True, maximum_depth=1)
    self.assertErrorRegexes(errors, {"e": r"foo.*max"})

  def test_multiple_signatures_with_type_parameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: int) -> List[T]: ...
        def f(x: List[T], y: str) -> List[T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x, y):
          return foo.f(x, y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x, y) -> list: ...
      """)

  def test_multiple_signatures_with_multiple_type_parameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, Tuple, TypeVar
        T = TypeVar("T")
        def f(arg1: int) -> List[T]: ...
        def f(arg2: str) -> Tuple[T, T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ... # type: module
        def f(x) -> Any: ...
      """)

  def test_unknown_single_signature(self):
    # Test that the right signature is picked in the presence of an unknown
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: int) -> List[T]: ...
        def f(x: List[T], y: str) -> List[T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(y):
          return foo.f("", y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        foo = ...  # type: module
        def f(y) -> List[str]: ...
    """)

  def test_unknown_with_solved_type_parameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T, y: T) -> List[T]: ...
        def f(x: List[T], y: T) -> List[T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x, "")
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Union
        foo = ...  # type: module
        # TODO(rechen): def f(x: str or List[str]) -> List[str]: ...
        def f(x) -> list: ...
      """)

  def test_unknown_with_extra_information(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List, TypeVar
        T = TypeVar("T")
        def f(x: T) -> List[T]: ...
        def f(x: List[T]) -> List[T]: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)[0].isnumeric()
        def g(x):
          return foo.f(x) + [""]
        def h(x):
          ret = foo.f(x)
          x + ""
          return ret
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, List, MutableSequence
        foo = ...  # type: module
        # TODO(rechen): def f(x: unicode or List[unicode]) -> bool: ...
        def f(x) -> Any: ...
        def g(x) -> list: ...
        # TODO(rechen): def h(x: Union[buffer, bytearray, unicode]) -> List[Union[buffer, bytearray, unicode]]: ...
        def h(x) -> list: ...
      """)

  def test_type_parameter_in_return(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class MyPattern(Generic[T]):
          def match(self, string: T) -> MyMatch[T]: ...
        class MyMatch(Generic[T]):
          pass
        def compile() -> MyPattern[T]: ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.compile().match("")
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import typing

        foo = ...  # type: module
        x = ...  # type: foo.MyMatch[str]
      """)

  def test_multiple_signatures(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str) -> float: ...
        def f(x: int, y: bool) -> int: ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.f(0, True)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        x = ...  # type: int
      """)

  def test_multiple_signatures_with_unknown(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(arg1: str) -> float: ...
        def f(arg2: int) -> bool: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x) -> Any: ...
      """)

  def test_multiple_signatures_with_optional_arg(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str) -> int: ...
        def f(*args) -> float: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x) -> Any: ...
      """)

  def test_multiple_signatures_with_kwarg(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(*, y: int) -> bool: ...
        def f(y: str) -> float: ...
      """)
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(y=x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        def f(x) -> Any: ...
      """)

  def test_isinstance(self):
    ty = self.Infer("""
      def f(isinstance=isinstance):
        pass
      def g():
        f()
      def h():
        return isinstance
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, Tuple, Union
      def f(isinstance = ...) -> None: ...
      def g() -> None: ...
      def h() -> Callable[[Any, Union[Tuple[Union[Tuple[type, ...], type], ...], type]], bool]: ...
    """)

  def test_wrong_keyword(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        pass
      f("", y=42)  # wrong-keyword-args[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"y"})

  def test_staticmethod_class(self):
    ty = self.Infer("""
      v1, = (object.__new__,)
      v2 = type(object.__new__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Type
      v1 = ...  # type: Callable
      v2 = ...  # type: Type[Callable]
    """)

  def test_function_class(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f() -> None: ...
      """)
      ty = self.Infer("""
        import foo
        def f(): pass
        v1 = (foo.f,)
        v2 = type(foo.f)
        w1 = (f,)
        w2 = type(f)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Callable, Tuple
        foo = ...  # type: module
        def f() -> None: ...
        v1 = ...  # type: Tuple[Callable[[], None]]
        v2 = Callable
        w1 = ...  # type: Tuple[Callable[[], Any]]
        w2 = Callable
      """)

  def test_type_parameter_visibility(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple, TypeVar, Union
        T = TypeVar("T")
        def f(x: T) -> Tuple[Union[T, str], int]: ...
      """)
      ty = self.Infer("""
        import foo
        v1, v2 = foo.f(42j)
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        foo = ...  # type: module
        v1 = ...  # type: Union[str, complex]
        v2 = ...  # type: int
      """)

  def test_pytd_function_in_class(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar(): ...
      """)
      self.Check("""
        import foo
        class A(object):
          bar = foo.bar
          def f(self):
           self.bar()
      """, pythonpath=[d.path])

  def test_interpreter_function_in_class(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        bar = lambda x: x
        def f(self):
          self.bar(42)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"1.*2"})

  def test_nested_lambda(self):
    # Inspired by b/37869955
    self.Check("""
      def f(c):
        return lambda c: f(c)
    """)

  def test_nested_lambda2(self):
    self.Check("""
      def f(d):
        return lambda c: f(c)
    """)

  def test_nested_lambda3(self):
    self.Check("""
      def f(t):
        lambda u=[t,1]: f(u)
      """)

  def test_set_defaults(self):
    self.Check("""
      import collections
      X = collections.namedtuple("X", "a b c d")
      X.__new__.__defaults__ = (3, 4)
      a = X(1, 2)
      b = X(1, 2, 3)
      c = X(1, 2, 3, 4)
      """)

  def test_set_defaults_non_new(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def b(x: int, y: int, z: int): ...
        """)
      ty = self.Infer("""
        import a
        a.b.__defaults__ = ('3',)
        a.b(1, 2)
        c = a.b
        """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        def c(x: int, y: int, z: int = ...): ...
        """)

  def test_bad_defaults(self):
    self.InferWithErrors("""
      import collections
      X = collections.namedtuple("X", "a b c")
      X.__new__.__defaults__ = (1)  # bad-function-defaults
      """)

  def test_multiple_valid_defaults(self):
    self.Check("""
      import collections
      X = collections.namedtuple("X", "a b c")
      X.__new__.__defaults__ = (1,) if __random__ else (1,2)
      X(0)  # should not cause an error
      """)

  def test_set_defaults_to_expression(self):
    # Test that get_atomic_python_constant fails but get_atomic_value pulls out
    # a tuple Instance.
    self.Check("""
      import collections
      X = collections.namedtuple("X", "a b c")
      X.__new__.__defaults__ = (None,) * len(X._fields)
      """)

  def test_set_defaults_non_tuple_instance(self):
    # Test that get_atomic_python_constant fails and get_atomic_value pulls out
    # a non-tuple Instance.
    self.InferWithErrors("""
      import collections
      X = collections.namedtuple("X", "a b c")
      X.__new__.__defaults__ = (lambda x: x)(0)  # bad-function-defaults
    """)

  def test_set_builtin_defaults(self):
    self.assertNoCrash(self.Check, """
      import os
      os.chdir.__defaults__ = ("/",)
      os.chdir()
      """)

  def test_interpreter_function_defaults(self):
    self.Check("""
      def test(a, b, c = 4):
        return a + b + c
      x = test(1, 2)
      test.__defaults__ = (3, 4)
      y = test(1, 2)
      y = test(1)
      test.__defaults__ = (2, 3, 4)
      z = test()
      z = test(1)
      z = test(1, 2)
      z = test(1, 2, 3)
      """)
    self.InferWithErrors("""
      def test(a, b, c):
        return a + b + c
      x = test(1, 2)  # missing-parameter
      test.__defaults__ = (3,)
      x = test(1, 2)
      x = test(1)  # missing-parameter
      """)

  def test_interpreter_function_defaults_on_class(self):
    self.InferWithErrors("""
      class Foo(object):
        def __init__(self, a, b, c):
          self.a = a
          self.b = b
          self.c = c
      a = Foo()  # missing-parameter
      Foo.__init__.__defaults__ = (1, 2)
      b = Foo(0)
      c = Foo()  # missing-parameter
      """)

  def test_split_on_kwargs(self):
    ty = self.Infer("""
      def make_foo(**kwargs):
        varargs = kwargs.pop("varargs", None)
        if kwargs:
          raise TypeError()
        return varargs
      Foo = make_foo(varargs=True)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Optional
      def make_foo(**kwargs) -> Any: ...
      Foo = ...  # type: bool
    """)

  def test_pyi_starargs(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str, *args) -> None: ...
      """)
      self.CheckWithErrors("""
        import foo
        foo.f(True, False)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_infer_bound_pytd_func(self):
    ty = self.Infer("""
      import struct
      if __random__:
        int2byte = struct.Struct(">B").pack
      else:
        int2byte = chr
    """)
    self.assertTypesMatchPytd(ty, """
      struct = ...  # type: module
      def int2byte(*v) -> bytes: ...
    """)

  def test_preserve_return_union(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Union
        def f(x: int) -> Union[int, str]: ...
        def f(x: float) -> Union[int, str]: ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.f(__any_object__)
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      foo = ...  # type: module
      v = ...  # type: Union[int, str]
    """)

  def test_call_with_varargs_and_kwargs(self):
    self.Check("""
      def foo(an_arg):
        pass
      def bar(an_arg, *args, **kwargs):
        foo(an_arg, *args, **kwargs)
    """)

  def test_functools_partial(self):
    ty = self.Infer("""
      import functools
      def f(a, b):
        pass
      partial_f = functools.partial(f, 0)
    """)
    # TODO(b/66005735): The type of partial_f should be functools.partial[Any].
    self.assertTypesMatchPytd(ty, """
      functools: module
      def f(a, b) -> None: ...
      partial_f: functools.partial[nothing]
    """)

  def test_functools_partial_kw(self):
    self.Check("""
      import functools
      def f(a, b=None):
        pass
      partial_f = functools.partial(f, 0)
      partial_f(0)
    """)

  def test_functools_partial_class(self):
    self.Check("""
      import functools
      class X(object):
        def __init__(self, a, b):
          pass
      PartialX = functools.partial(X, 0)
      PartialX(0)
    """)

  def test_functools_partial_class_kw(self):
    self.Check("""
      import functools
      class X(object):
        def __init__(self, a, b=None):
          pass
      PartialX = functools.partial(X, 0)
      PartialX(0)
    """)

  def test_functools_partial_bad_call(self):
    errors = self.CheckWithErrors("""
      import functools
      functools.partial()  # missing-parameter
      functools.partial(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Callable.*int"})

  def test_bad_comprehensions(self):
    # Test that we report errors in comprehensions and generators only once
    # while still reporting errors in lambdas.
    self.CheckWithErrors("""
      [name_error1 for x in ()]  # name-error
      {name_error2 for x in ()}  # name-error
      (name_error3 for x in ())  # name-error
      lambda x: name_error4  # name-error
    """)

  def test_new_function(self):
    ty = self.Infer("""
      import types
      def new_function(code, globals):
        return types.FunctionType(code, globals)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      types: module
      def new_function(code, globals) -> Callable: ...
    """)

  def test_function_globals(self):
    ty = self.Infer("""
      def f():
        def g():
          pass
        return g.__globals__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      def f() -> Dict[str, Any]: ...
    """)

  def test_hashable(self):
    self.Check("""
      from typing import Hashable
      def f(x):
        # type: (Hashable) -> None
        pass
      def g():
        pass
      f(g)
    """)


test_base.main(globals(), __name__ == "__main__")
