"""Test functions."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestGenerators(test_base.BaseTest):
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
      class Thing:
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


class PreciseReturnTest(test_base.BaseTest):
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
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
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


class TestFunctions(test_base.BaseTest):
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
      class A:
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
    with test_utils.Tempdir() as d:
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
    self.Check("""
      def f(a, b):
        return a * b
      def g(*args, **kwargs):
        return f(*args, **kwargs)
      assert_type(g(1, 2), int)
    """)

  def test_pass_through_kwargs(self):
    self.Check("""
      def f(a, b):
        return a * b
      def g(*args, **kwargs):
        return f(*args, **kwargs)
      assert_type(g(a=1, b=2), int)
    """)

  def test_pass_through_named_args_and_kwargs(self):
    self.CheckWithErrors("""
      def f(a: int, b: str):
        pass
      def g(*args, **kwargs):
        return f(*args, a='a', **kwargs)  # wrong-arg-types
    """)

  def test_pass_through_partial_named_args_and_kwargs(self):
    self.Check("""
      class Foo:
        def __init__(self, name, labels):
          pass

      def g(name, bar, **kwargs):
        Foo(name=name, **kwargs)

      def f(name, x, **args):
        g(name=name, bar=x, **args)

      f('a', 10, labels=None)
    """)

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
    """, maximum_depth=1)
    self.assertErrorRegexes(errors, {"e": r"foo.*max"})

  def test_multiple_signatures_with_type_parameter(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
        def f(x, y) -> list: ...
      """)

  def test_multiple_signatures_with_multiple_type_parameter(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
        def f(x) -> Any: ...
      """)

  def test_unknown_single_signature(self):
    # Test that the right signature is picked in the presence of an unknown
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import List
        def f(y) -> List[str]: ...
    """)

  def test_unknown_with_solved_type_parameter(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any, Union
        def f(x) -> list: ...
      """)

  def test_unknown_with_extra_information(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any, List, MutableSequence
        def f(x) -> Any: ...
        def g(x) -> list: ...
        def h(x) -> list: ...
      """)

  def test_type_parameter_in_return(self):
    with test_utils.Tempdir() as d:
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
        import foo
        x = ...  # type: foo.MyMatch[str]
      """)

  def test_multiple_signatures(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str) -> float: ...
        def f(x: int, y: bool) -> int: ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.f(0, True)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        x = ...  # type: int
      """)

  def test_multiple_signatures_with_unknown(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
        def f(x) -> Any: ...
      """)

  def test_multiple_signatures_with_optional_arg(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
        def f(x) -> Any: ...
      """)

  def test_multiple_signatures_with_kwarg(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Type
      v1 = ...  # type: Callable
      v2 = ...  # type: Type[Callable]
    """)

  def test_function_class(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any, Callable, Tuple
        def f() -> None: ...
        v1 = ...  # type: Tuple[Callable[[], None]]
        v2 = Callable
        w1 = ...  # type: Tuple[Callable[[], Any]]
        w2 = Callable
      """)

  def test_type_parameter_visibility(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple, TypeVar, Union
        T = TypeVar("T")
        def f(x: T) -> Tuple[Union[T, str], int]: ...
      """)
      ty = self.Infer("""
        import foo
        v1, v2 = foo.f(42j)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Union
        v1 = ...  # type: Union[str, complex]
        v2 = ...  # type: int
      """)

  def test_pytd_function_in_class(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar(): ...
      """)
      self.Check("""
        import foo
        class A:
          bar = foo.bar
          def f(self):
           self.bar()
      """, pythonpath=[d.path])

  def test_interpreter_function_in_class(self):
    _, errors = self.InferWithErrors("""
      class A:
        bar = lambda x: x
        def f(self):
          self.bar(42)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"1.*2"})

  def test_lambda(self):
    # Inspired by b/243664545
    self.CheckWithErrors("""
      def f():
        a = lambda: 1 + ""  # unsupported-operands
    """)

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
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def b(x: int, y: int, z: int): ...
        """)
      ty = self.Infer("""
        import a
        a.b.__defaults__ = ('3',)
        a.b(1, 2)
        c = a.b
        """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
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
      class Foo:
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
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: str, *args) -> None: ...
      """)
      self.CheckWithErrors("""
        import foo
        foo.f(True, False)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_starargs_matching_pyi_posargs(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: int, y: int, z: int) -> None: ...
      """)
      self.CheckWithErrors("""
        import foo
        def g(x, *args):
          foo.f(x, *args)
          foo.f(x, 1, *args)
          foo.f(x, 1)  # missing-parameter
      """, pythonpath=[d.path])

  def test_starargs_forwarding(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: int) -> None: ...
      """)
      self.Check("""
        import foo
        def f(x, y, *args):
          for i in args:
            foo.f(i)
        def g(*args):
          f(1, 2, *args)
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
      import struct
      from typing import overload
      @overload
      def int2byte(*v) -> bytes: ...
      @overload
      def int2byte(i: int) -> str: ...
    """)

  def test_preserve_return_union(self):
    with test_utils.Tempdir() as d:
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
      import foo
      from typing import Union
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
    self.assertTypesMatchPytd(ty, """
      import functools
      def f(a, b) -> None: ...
      partial_f: functools.partial
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
      class X:
        def __init__(self, a, b):
          pass
      PartialX = functools.partial(X, 0)
      PartialX(0)
    """)

  def test_functools_partial_class_kw(self):
    self.Check("""
      import functools
      class X:
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
      import types
      from typing import Callable
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


if __name__ == "__main__":
  test_base.main()
