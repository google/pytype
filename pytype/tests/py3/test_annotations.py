"""Tests for inline annotations."""


from pytype import file_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class AnnotationTest(test_base.TargetPython3BasicTest):
  """Tests for PEP 484 style inline annotations."""

  def test_none_unpacking_is(self):
    """Tests that is works with None."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is None:
          return ""
        return x
      """)

  def test_none_unpacking_is_not(self):
    """Tests that is not works with None."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is not None:
          return x
        return ""
      """)

  def test_only_annotations(self):
    ty = self.Infer("""
      def bar(p1: str, p2: complex) -> int:
         pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def bar(p1: str, p2: complex) -> int: ...
    """)

  def test_deep(self):
    ty = self.Infer("""
      def bar(p1: str, p2: complex) -> None:
         pass
    """)
    self.assertTypesMatchPytd(ty, """
      def bar(p1: str, p2: complex) -> None: ...
    """)

  def test_union(self):
    ty = self.Infer("""
      import typing
      def foo(x: typing.Union[int, float], y: int):
        return x + y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      typing = ...  # type: module
      def foo(x: Union[int, float], y:int) -> Union[int, float]: ...
    """)

  def test_call_error(self):
    _, errors = self.InferWithErrors("""
      s = {1}
      def foo(x: int):
        s.intersection(x)
      foo(3.0)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x: int.*x: float"})

  def test_ambiguous_arg(self):
    self.Check("""
      def f(x: int):
        return x
      def g(y, z):
        if y:
          x = 3
        elif z:
          x = 3j
        else:
          x = "foo"
        f(x)
    """)

  def test_inner_error(self):
    _, errors = self.InferWithErrors("""
      def foo(x: int):
        return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})

  def test_list(self):
    ty = self.Infer("""
      from typing import List

      def foo(l1: List[int], l2: List[str], b):
        if b:
          x = l1
          y = 3
        else:
          x = l2
          y = "foo"
        x.append(y)
    """)
    self.assertTypesMatchPytd(ty, """
        from typing import List
        def foo(l1: List[int], l2: List[str], b) -> None: ...
    """)

  def test_analyze_init(self):
    ty = self.Infer("""
      from typing import List
      class Foo:
        def f(self, x: List[int]):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo:
        def f(self, x: List[int]) -> None: ...
    """)

  def test_string_annotation(self):
    ty = self.Infer("""
      def f(c: "int") -> "None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(ty, """
      def f(c: int) -> None: ...
    """)

  def test_unicode_annotation(self):
    ty = self.Infer("""
      def f(c: u"int") -> u"None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(ty, """
      def f(c: int) -> None: ...
    """)

  def test_future_unicode_literal_annotation(self):
    ty = self.Infer("""
      from __future__ import unicode_literals
      def f(c: "int") -> "None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(ty, """
      import __future__

      unicode_literals = ...  # type: __future__._Feature

      def f(c: int) -> None: ...
    """)

  def test_typing_only_import(self):
    ty = self.Infer("""
      import typing
      if typing.TYPE_CHECKING:
        import calendar
      def f(c: "calendar.Calendar") -> int:
        return c.getfirstweekday()
    """)
    self.assertTypesMatchPytd(ty, """
      typing = ...  # type: module
      calendar = ...  # type: module
      def f(c: calendar.Calendar) -> int: ...
    """)

  def test_ambiguous_annotation(self):
    _, errors = self.InferWithErrors("""
      def foo(x: int if __random__ else float):  # invalid-annotation[e1]
        return x
      def foo(x: "int if __random__ else float"):  # invalid-annotation[e2]
        return x
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"float or int.*x.*constant",
        # For a late annotation, we print the string literal, which is why the
        # types below are not in alphabetical order.
        "e2": r"int.*float.*x.*constant"})

  def test_bad_string_annotation(self):
    _, errors = self.InferWithErrors("""
      def foo(x: str()):  # invalid-annotation[e]
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*constant"})

  def test_bad_return(self):
    self.InferWithErrors("""
      def foo(x: str, y: str) -> int:
        return "foo"  # bad-return-type
    """)

  def test_multiple_returns(self):
    _, errors = self.InferWithErrors("""
      def foo(x: str, y: str) -> int:
        if x:
          return "foo"  # bad-return-type[e1]
        else:
          return 3j  # bad-return-type[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Expected.*int.*Actual.*str",
                                     "e2": r"Expected.*int.*Actual.*complex"})

  def test_ambiguous_return(self):
    _, errors = self.InferWithErrors("""
      def foo(x: str) -> int:
        if x:
          y = "foo"
        else:
          y = 3j
        return y  # bad-return-type[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*int.*Actual.*Union(?=.*complex).*str"})

  def test_default_return(self):
    ty = self.Infer("""
      class Foo(object):
        def bar(self, x: float, default="") -> str:
          default.upper
          return default
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def bar(self, x: float, default=...) -> str: ...
    """)

  def test_compat_bool(self):
    self.Check("""
      def bar(x: bool) -> bool:
        return None
      bar(None)
    """)

  def test_compat_float(self):
    self.Check("""
      def bar(x: float) -> float:
        return 1
      bar(42)
    """)

  def test_compat_unicode_str(self):
    # Use str to be identical in py2 and py3
    self.Check("""
      from typing import Text
      def bar(x: Text) -> Text:
        return str("foo")
      bar(str("bar"))
    """)

  def test_unsolvable(self):
    self.assertNoCrash(self.Check, """
      import unknown_module
      def f(x: unknown_module.Iterable):
        pass
    """)

  def test_any(self):
    ty = self.Infer("""
      from typing import Any
      def f(x: Any):
        pass
      x = f(3)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> None: ...
      x = ...  # type: None
    """)

  def test_dict(self):
    self.InferWithErrors("""
      from typing import Dict, List
      def keys(d: Dict[str, int]):
        return
      keys({"foo": 3})
      keys({})  # ok
      keys({3: 3})  # wrong-arg-types
    """, deep=True)

  def test_sequence(self):
    self.InferWithErrors("""
      from typing import Sequence
      def f(s: Sequence):
        return s
      f([1,2,3])
      f((1,2,3))
      f({1,2,3})  # wrong-arg-types
      f(1)  # wrong-arg-types
    """, deep=True)

  def test_optional(self):
    self.InferWithErrors("""
      from typing import Optional
      def f(s: Optional[int]):
        return s
      f(1)
      f(None)
      f("foo")  # wrong-arg-types
    """, deep=True)

  def test_set(self):
    self.InferWithErrors("""
      from typing import Set
      def f(d: Set[str]):
        return
      f({"foo"})  # ok
      f(set())  # ok
      f({})  # {} isn't a set  # wrong-arg-types
      f({3})  # wrong-arg-types
    """, deep=True)

  def test_frozenset(self):
    self.InferWithErrors("""
      from typing import FrozenSet
      def f(d: FrozenSet[str]):
        return
      f(frozenset(["foo"]))  # ok
      f(frozenset())  # ok
      f(frozenset([3]))  # wrong-arg-types
    """, deep=True)

  def test_generic_and_typevar(self):
    self.assertNoCrash(self.Check, """
      import typing
      _T = typing.TypeVar("_T")
      class A(typing.Generic[_T]):
        ...
    """)

  def test_jump_into_class_through_annotation(self):
    self.Check("""
      class Foo(object):
        def __init__(self) -> None:
          self.myset = set()
        def qux(self):
          self.myset.add("foo")

      def bar(foo: "Foo"):
        foo.qux()
    """)

  def test_forward_declarations(self):
    self.Check("""
      def f(a: "B"):
        return a

      class B(object):
        pass
    """)
    self.Check("""
      def f(a) -> "B":
        return B()

      class B(object):
        pass
    """)

  def test_without_forward_decl(self):
    _, errorlog = self.InferWithErrors("""
      def f(a) -> Bar:  # name-error[e]
        return Bar()

      class Bar(object):
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Bar"})

  def test_invalid_forward_decl(self):
    self.Check("""
      def f(a) -> "Foo":
        return Foo()

      class Foo(object):
        pass
    """)
    _, errorlog = self.InferWithErrors("""
      def f(a: "Foo"):  # name-error[e]
        return B()

      class B(object):
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Foo"})

  def test_forward_decl_bad_return(self):
    _, errorlog = self.InferWithErrors("""
        def f() -> "Foo":
          return 1  # bad-return-type[e]

        class Foo(object):
          pass
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorRegexes(errorlog, {"e": r"return type.*int"})

  def test_confusing_forward_decl(self):
    _, errorlog = self.InferWithErrors("""
        class Foo(object):
          def foo(self):
            return 4

        def f() -> "Foo":
          return Foo()

        class Foo(object):
          def bar(self):
            return 2

        def g():
          return f().bar()  # attribute-error[e]
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorRegexes(errorlog, {"e": r"\'bar\'.*Foo"})

  def test_return_type_error(self):
    _, errors = self.InferWithErrors("""
      class FooBar(object): pass
      def f() -> FooBar:
        return 3  # bad-return-type[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Expected: FooBar"})

  def test_unknown_argument(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def factory() -> type: ...
      """)
      ty = self.Infer("""
        import a
        A = a.factory()
        def f(x: A):
          return x.name
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        A = ...  # type: Any
        def f(x) -> Any: ...
      """)

  @test_utils.skipFromPy((3, 8), "error line number changed in 3.8")
  def test_bad_call_no_kwarg_pre_38(self):
    ty, errors = self.InferWithErrors("""
      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(
          labels['baz'])  # wrong-arg-types[e]

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> None: ...
      def bar(path: str, **kwargs) -> str: ...
    """)
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  @test_utils.skipBeforePy((3, 8), "error line number changed in 3.8")
  def test_bad_call_no_kwarg(self):
    ty, errors = self.InferWithErrors("""
      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(  # wrong-arg-types[e]
          labels['baz'])

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> None: ...
      def bar(path: str, **kwargs) -> str: ...
    """)
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  @test_utils.skipFromPy((3, 8), "error line number changed in 3.8")
  def test_bad_call_with_kwarg_pre_38(self):
    ty, errors = self.InferWithErrors("""
      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(
          labels['baz'], x=42)  # wrong-arg-types[e]

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> None: ...
      def bar(path: str, **kwargs) -> str: ...
    """)
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  @test_utils.skipBeforePy((3, 8), "error line number changed in 3.8")
  def test_bad_call_with_kwarg(self):
    ty, errors = self.InferWithErrors("""
      def foo():
        labels = {
          'baz': None
        }

        labels['baz'] = bar(  # wrong-arg-types[e]
          labels['baz'], x=42)

      def bar(path: str, **kwargs):
        return path

    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> None: ...
      def bar(path: str, **kwargs) -> str: ...
    """)
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  def test_skip_functions_with_annotations(self):
    ty = self.Infer("""
      _analyzed_baz = None
      class Foo(object):
        def __init__(self):
          self._executed_init = True
        def bar(self, x: int) -> None:
          self._analyzed_bar = True
      def baz(x: int) -> None:
        global _analyzed_baz
        _analyzed_baz = 3
    """, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
      _analyzed_baz = ... # type: None
      class Foo(object):
        # We expect to *not* see _analyzed_bar here, because it's an attribute
        # initialized by a function we're not analyzing.
        _executed_init = ...  # type: bool
        def __init__(self) -> None: ...
        def bar(self, x: int) -> None: ...
      def baz(x: int) -> None: ...
    """)

  def test_annotated_init(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self, x: str):
          self.x = x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
        def __init__(self, x: str) -> None: ...
    """)

  def test_union_instantiation(self):
    # If unions are not instantiated properly, the call to x.value will
    # cause an error and Infer will fail.
    self.Infer("""
      from typing import Union

      class Container1(object):
        def __init__(self, value):
          self.value1 = value

      class Container2(object):
        def __init__(self, value):
          self.value2 = value

      def func(x: Union[Container1, Container2]):
        if isinstance(x, Container1):
          return x.value1
        else:
          return x.value2
    """)

  def test_imprecise_annotation(self):
    ty, errors = self.InferWithErrors("""
      from typing import Union
      class A: pass
      class B:
        x = 42
      def f(v: Union[A, B]):
        return v.x  # attribute-error[e]
      f(A())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A: ...
      class B:
        x = ...  # type: int
      def f(v: Union[A, B]) -> int: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*A"})

  def test_tuple(self):
    ty = self.Infer("""
      def f():
        return (0, "")
      def g(x: str):
        return x
      x = g(f()[1])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      def f() -> Tuple[int, str]: ...
      def g(x: str) -> str: ...
      x = ...  # type: str
    """)

  def test_optional_arg(self):
    self.Check("""
      def f(x: str, y: bool=False):
        pass
      f("", y=True)
    """)

  def test_empty(self):
    self.Check("""
      from typing import Any, List
      def f(x: List[Any]):
        pass
      f([])
    """)

  def test_inner_string(self):
    self.Check("""
      from typing import List, Union
      def f(x: List["int"]):
        pass
      def g(x: Union["int"]):
        pass
    """)

  def test_ambiguous_inner_annotation(self):
    _, errors = self.InferWithErrors("""
      from typing import List, Union
      def f(x: List[int if __random__ else str]):  # invalid-annotation[e1]
        pass
      def g(x: Union[int if __random__ else str]):  # invalid-annotation[e2]
        pass
      def h(x: List[Union[int, str]]):  # okay
        pass
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"List\[int\] or List\[str\].*constant",
        "e2": r"int or str.*constant"})

  def test_kwargs(self):
    ty, errors = self.InferWithErrors("""
      from typing import Dict
      def f(x, **kwargs: int):
        return kwargs
      def g() -> Dict[str, float]:
        return __any_object__
      def h() -> Dict[float, int]:
        return __any_object__
      f("", y=42)
      f("", **{})
      f("", **{"y": 42})
      f("", **g())  # wrong-arg-types[e1]
      f("", **h())  # wrong-arg-types[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f(x, **kwargs: int) -> Dict[str, int]: ...
      def g() -> Dict[str, float]: ...
      def h() -> Dict[float, int]: ...
    """)
    error1 = (r"Expected.*Mapping\[str, int\].*"
              r"Actually passed.*Dict\[str, float\]")
    error2 = (r"Expected.*Mapping\[str, int\].*"
              r"Actually passed.*Dict\[float, int\]")
    self.assertErrorRegexes(errors, {"e1": error1, "e2": error2})

  @test_base.skip("Types not checked due to function.Args.simplify")
  def test_simplified_varargs_and_kwargs(self):
    _, errors = self.InferWithErrors("""
      def f(x, *args: int):
        pass
      def g(x, **kwargs: int):
        pass
      f("", 42.0)  # wrong-arg-types[e1]
      g("", y=42.0)  # wrong-arg-types[e2]
      g("", **{"y": 42.0})  # wrong-arg-types[e3]
    """)
    error = r"Expected.*int.*Actually passed.*float"
    self.assertErrorRegexes(errors, {"e1": error, "e2": error, "e3": error})

  def test_use_varargs_and_kwargs(self):
    ty = self.Infer("""
      class A(object):
        pass
      def f(*args: A):
        return args[0]
      def g(**kwargs: A):
        return kwargs["x"]
      v1 = f()
      v2 = g()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class A(object): ...
      def f(*args: A) -> A: ...
      def g(**kwargs: A) -> A: ...
      v1 = ...  # type: A
      v2 = ...  # type: A
    """)

  def test_use_varargs_and_kwargs_in_forward_references(self):
    self.Check("""
      class Foo(object):
        def f(self, *args: "Foo", **kwargs: "Foo"):
          for a in args:
            pass
          for a in kwargs:
            pass
      def Bar():
        Foo().f()
    """)

  def test_nested_none_type(self):
    ty, errors = self.InferWithErrors("""
      from typing import List, Union
      class A:
        x = 42
      def f() -> Union[A, None]:
        pass
      def g() -> List[None]:
        return [None]
      v1 = f().x  # attribute-error[e]
      v2 = g()[0]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      class A:
        x = ...  # type: int
      def f() -> Union[A, None]: ...
      def g() -> List[None]: ...
      v1 = ...  # type: int
      v2 = ...  # type: None
    """)
    self.assertErrorRegexes(errors, {"e": r"x.*None"})

  def test_match_late_annotation(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        def f(self, x: "A"):
          pass
      def f():
        A().f(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*int"})

  def test_recursive_forward_reference(self):
    _, errors = self.InferWithErrors("""
      class A(object):
        def __init__(self, x: "A"):
          self.foo = x.foo
          f(x)  # wrong-arg-types[e1]
        def method1(self):
          self.foo
        def method2(self):
          self.bar  # attribute-error[e2]
      def f(x: int):
        pass
    """)
    self.assertErrorRegexes(errors, {"e1": r"int.*A", "e2": r"bar"})

  def test_module_level_forward_reference_error(self):
    errors = self.CheckWithErrors("""
      class A(object):
        def f(self, x: "A"):
          pass
      A().f(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*int"})

  def test_return_annotation1(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      x = A.New().x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: int
        def __init__(self) -> None: ...
        @staticmethod
        def New() -> A: ...
      x = ...  # type: int
    """)

  def test_return_annotation2(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      def f():
        return A.New().x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: int
        def __init__(self) -> None: ...
        @staticmethod
        def New() -> A: ...
      def f() -> int: ...
    """)

  def test_deeply_nested_annotation(self):
    self.Check("""
      from typing import Any, Dict, List, Optional
      def G(x: Optional[List[Dict[str, Any]]]):
        if x:
          pass
      def F(x: Optional[List[Dict[str, Any]]]):
        G(x)
    """)

  def test_nested_late_annotation(self):
    self.Check("""
      from typing import List
      Type = "int"
      def f(x: "List[Type]"):
        pass
    """)

  def test_late_annotation(self):
    ty = self.Infer("""
      def new_x() -> 'X':
        return X()
      class X(object):
        def __init__(self) -> None:
          self.foo = 1
      def get_foo() -> int:
        return new_x().foo
    """)
    self.assertTypesMatchPytd(ty, """
      def new_x() -> X: ...
      def get_foo() -> int: ...

      class X(object):
        foo = ...  # type: int
        def __init__(self) -> None: ...
    """)

  def test_change_annotated_arg(self):
    ty, _ = self.InferWithErrors("""
      from typing import Dict
      def f(x: Dict[str, str]):
        x[True] = 42  # container-type-mismatch[e]
        return x
      v = f({"a": "b"})
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      def f(x: Dict[str, str]) -> Dict[Union[str, bool], Union[str, int]]: ...
      v = ...  # type: Dict[Union[str, bool], Union[str, int]]
    """)

  def test_inner_string_annotation(self):
    ty = self.Infer("""
      from typing import List
      def f(x: List["A"]) -> int:
        pass
      class A(object):
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import typing

      def f(x: typing.List[A]) -> int: ...

      class A(object): ...
    """)

  def test_type_alias_annotation(self):
    ty = self.Infer("""
      from typing import List
      TypeA = "A"
      ListA = "List[A]"
      def f(x: "ListA") -> int:
        pass
      class A(object):
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import typing
      ListA = ...  # type: str
      TypeA = ...  # type: str
      def f(x: typing.List[A]) -> int: ...
      class A(object):
          pass
    """)

  def test_double_string(self):
    ty = self.Infer("""
      from typing import List
      def f(x: "List[\\"int\\"]") -> int:
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f(x: List[int]) -> int: ...
    """)

  def test_duplicate_identifier(self):
    ty = self.Infer("""
      t = int
      def f(x: t) -> int: pass
      def g(x: "t") -> int: pass
      t = float
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      t: Type[float]
      def f(x: int) -> int: ...
      def g(x: int) -> int: ...
    """)

  def test_ellipsis(self):
    ty, errors = self.InferWithErrors("""
      from typing import Dict, Tuple
      def f(x: ...): pass  # invalid-annotation[e1]
      def g(x: Tuple[str, ...]): pass
      def h(x: Dict[..., int]): pass  # invalid-annotation[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Tuple
      def f(x) -> None: ...
      def g(x: Tuple[str, ...]) -> None: ...
      def h(x: Dict[Any, int]) -> None: ...
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Ellipsis.*x", "e2": r"Ellipsis.*Dict"})

  def test_custom_container(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic
        T = TypeVar("T")
        T2 = TypeVar("T2")
        class Foo(Generic[T]):
          def __init__(self, x: T2):
            self = Foo[T2]
      """)
      _, errors = self.InferWithErrors("""
        import foo
        def f(x: foo.Foo[int]):
          pass
        f(foo.Foo(42))
        f(foo.Foo(""))  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"Foo\[int\].*Foo\[str\]"})

  def test_no_implicit_optional(self):
    ty, _ = self.InferWithErrors("""
      from typing import Optional, Union
      def f1(x: str = None):  # annotation-type-mismatch
        pass
      def f2(x: Optional[str] = None):
        pass
      def f3(x: Union[str, None] = None):
        pass
      def f4(x: Union[str, int] = None):  # annotation-type-mismatch
        pass
      f1(None)  # wrong-arg-types
      f2(None)
      f3(None)
      f4(None)  # wrong-arg-types
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      def f1(x: str = ...) -> None: ...
      def f2(x: Optional[str] = ...) -> None: ...
      def f3(x: Optional[str] = ...) -> None: ...
      def f4(x: Union[str, int] = ...) -> None: ...
    """)

  def test_infer_return(self):
    ty = self.Infer("""
      def f(x: int):
        return x
    """, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> int: ...
    """)

  def test_return_abstract_dict(self):
    self.Check("""
      from typing import Dict
      def f(x, y):
        pass
      def g() -> Dict:
        return {"y": None}
      def h():
        f(x=None, **g())
    """)

  def test_recursive_type_alias(self):
    ty, errors = self.InferWithErrors("""
      from typing import List
      Foo = List["Foo"]  # not-supported-yet[e]
    """)
    self.assertTypesMatchPytd(ty, "from builtins import list as Foo")
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def test_use_recursive_type_alias(self):
    errors = self.CheckWithErrors("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]  # not-supported-yet[e]
      def f(x: Foo):
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def test_mutually_recursive_type_aliases(self):
    ty, errors = self.InferWithErrors("""
      from typing import List
      X = List["Y"]
      Y = List["X"]  # not-supported-yet[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      X = List[Y]
      Y = List[list]
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Y"})

  def test_forward_reference_in_type_alias(self):
    self.Check("""
      from typing import List
      X = List["Y"]
      Y = List["Z"]
      Z = List[int]
    """)

  def test_fully_quoted_annotation(self):
    self.Check("""
      from typing import Optional
      class A(object):
        OBJ = ()
        def __init__(self, parent: "Optional[A]"):
          self.parent = (self.OBJ, parent)
    """)

  def test_quoted_generic_parameter(self):
    ty = self.Infer("""
      from typing import Callable, List
      def f(x: List["Callable[[int], str]"]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, List
      def f(x: List[Callable[[int], str]]) -> None: ...
    """)

  def test_late_annotation_non_name_error(self):
    self.CheckWithErrors("""
      class Foo(object):
        pass
      def f(x: "Foo.Bar"):  # attribute-error
        pass
    """)

  def test_keep_container_with_error(self):
    ty, _ = self.InferWithErrors("""
      from typing import Dict
      def f(x: "Dict[str, int.error]"):  # attribute-error
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      def f(x: Dict[str, Any]) -> None: ...
    """)

  def test_count_type_parameters(self):
    self.Check("""
      from typing import Callable, TypeVar
      T = TypeVar('T')
      def f() -> Callable[[Callable[..., T]], Callable[..., T]]:
        return __any_object__
    """)

  def test_set_annotated_attribute(self):
    self.Check("""
      from typing import Optional

      class A:
        def __init__(self):
          self.x = None  # type: Optional[str]

        def Set(self, x: str) -> None:
          if self.x is None:
            self.x = x

      x = None  # type: Optional[A]
    """)

  def test_nested_class_forward_ref(self):
    self.Check("""
      from typing import List
      def f():
        class Foo:
          X = List['int']
    """)

  def test_nested_forward_ref_to_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo: ...
      """)
      self.Check("""
        import foo
        from typing import Tuple
        def f(x: Tuple[str, 'foo.Foo']):
          pass
      """, pythonpath=[d.path])


class TestAnnotationsPython3Feature(test_base.TargetPython3FeatureTest):
  """Tests for PEP 484 style inline annotations."""

  def test_variable_annotations(self):
    ty = self.Infer("""
      a: int = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a: int
    """)

  def test_container_mutation(self):
    errors = self.CheckWithErrors("""
      from typing import List
      x: List[int] = []
      x.append("hello")  # container-type-mismatch[e]
    """)
    pattern = r"Annot.*List\[int\].*Contained.*int.*New.*Union\[int, str\]"
    self.assertErrorRegexes(errors, {"e": pattern})

  def test_varargs(self):
    ty, errors = self.InferWithErrors("""
      def quack(x, *args: int):
        return args
      quack("", 42)
      quack("", *[])
      quack("", *[42])
      quack("", *[42.0])  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      def quack(x, *args: int) -> Tuple[int, ...]: ...
    """)
    error = r"Expected.*Iterable\[int\].*Actually passed.*Tuple\[float\]"
    self.assertErrorRegexes(errors, {"e": error})

  def test_container_multiple_mutations(self):
    errors = self.CheckWithErrors("""
      from typing import Dict
      x: Dict[int, str] = {}
      x["hello"] = 1.0  # container-type-mismatch[e]
    """)
    pattern = (r"New container.*for x.*Dict\[int, str\].*Dict\[_K, _V\].*" +
               r"Contained.*_K.*int.*_V.*str.*"
               r"New.*_K.*Union\[int, str\].*_V.*Union\[float, str\]")
    self.assertErrorRegexes(errors, {"e": pattern})

  def test_allowed_container_mutation_subclass(self):
    self.Check("""
      from typing import List
      class A: pass
      class B(A): pass
      x: List[A] = []
      x.append(B())
    """)

  def test_allowed_container_mutation_builtins(self):
    self.Check("""
      from typing import List
      x: List[float] = []
      x.append(0)
    """)

  @test_utils.skipUnlessPy((3, 7), reason="__future__.annotations is 3.7+ and "
                           "is the default behavior in 3.8+")
  def test_postponed_evaluation(self):
    self.Check("""
      from __future__ import annotations
      def f() -> int:
        return 0
    """)

  @test_utils.skipUnlessPy((3, 7), reason="__future__.annotations is 3.7+ and "
                           "is the default behavior in 3.8+")
  def test_postponed_evaluation_error(self):
    self.CheckWithErrors("""
      from __future__ import annotations
      def f() -> str:
        return 0  # bad-return-type
    """)


test_base.main(globals(), __name__ == "__main__")
