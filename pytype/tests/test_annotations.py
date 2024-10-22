"""Tests for inline annotations."""

from pytype.tests import test_base
from pytype.tests import test_utils


class AnnotationTest(test_base.BaseTest):
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
         return 0
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def bar(p1: str, p2: complex) -> int: ...
    """,
    )

  def test_deep(self):
    ty = self.Infer("""
      def bar(p1: str, p2: complex) -> None:
         pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def bar(p1: str, p2: complex) -> None: ...
    """,
    )

  def test_union(self):
    ty = self.Infer("""
      import typing
      def foo(x: typing.Union[int, float], y: int):
        return x + y
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      import typing
      from typing import Union
      def foo(x: Union[int, float], y:int) -> Union[int, float]: ...
    """,
    )

  def test_call_error(self):
    _, errors = self.InferWithErrors("""
      s = {1}
      def foo(x: int):
        s.intersection([x])
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
        f(x)  # TODO(b/63407497): should be wrong-arg-types
    """)
    # The error should be ["Expected: (x: int)",
    #                      "Actually passed: (x: Union[complex, int, str])"]

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
    self.assertTypesMatchPytd(
        ty,
        """
        from typing import List
        def foo(l1: List[int], l2: List[str], b) -> None: ...
    """,
    )

  def test_analyze_init(self):
    ty = self.Infer("""
      from typing import List
      class Foo:
        def f(self, x: List[int]):
          pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List
      class Foo:
        def f(self, x: List[int]) -> None: ...
    """,
    )

  def test_string_annotation(self):
    ty = self.Infer("""
      def f(c: "int") -> "None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def f(c: int) -> None: ...
    """,
    )

  def test_unicode_annotation(self):
    ty = self.Infer("""
      def f(c: u"int") -> u"None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def f(c: int) -> None: ...
    """,
    )

  def test_future_unicode_literal_annotation(self):
    ty = self.Infer("""
      from __future__ import unicode_literals
      def f(c: "int") -> "None":
        c += 1
        return
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def f(c: int) -> None: ...
    """,
    )

  def test_typing_only_import(self):
    ty = self.Infer("""
      import typing
      if typing.TYPE_CHECKING:
        import calendar
      def f(c: "calendar.Calendar") -> int:
        return c.getfirstweekday()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      import calendar
      import typing
      def f(c: calendar.Calendar) -> int: ...
    """,
    )

  def test_ambiguous_annotation(self):
    _, errors = self.InferWithErrors("""
      def foo(x: int if __random__ else float):  # invalid-annotation[e1]
        return x
      def foo(x: "int if __random__ else float"):  # invalid-annotation[e2]
        return x
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"float or int.*x.*constant",
            # For a late annotation, we print the string literal, which is why the
            # types below are not in alphabetical order.
            "e2": r"int.*float.*x.*constant",
        },
    )

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
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"Expected.*int.*Actual.*str",
            "e2": r"Expected.*int.*Actual.*complex",
        },
    )

  @test_utils.skipIfPy(
      (3, 10),
      (3, 12),
      reason="Logs one error for all bad returns in <=3.9, =3.11",
  )
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
        errors, {"e": r"Expected.*int.*Actual.*Union(?=.*complex).*str"}
    )

  @test_utils.skipUnlessPy(
      (3, 10),
      (3, 12),
      reason="Logs one error per bad return in 3.10 and 3.12",
  )
  def test_ambiguous_return_310_312(self):
    _, errors = self.InferWithErrors("""
      def foo(x: str) -> int:
        if x:
          y = "foo"
        else:
          y = 3j
        return y  # bad-return-type[e1]  # bad-return-type[e2]
    """)
    self.assertErrorSequences(
        errors,
        {
            "e1": ["Expected: int", "Actually returned: str"],
            "e2": ["Expected: int", "Actually returned: complex"],
        },
    )

  def test_default_return(self):
    ty = self.Infer("""
      class Foo:
        def bar(self, x: float, default="") -> str:
          default.upper
          return default
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo:
        def bar(self, x: float, default=...) -> str: ...
    """,
    )

  def test_nocompat_bool(self):
    self.CheckWithErrors("""
      def bar(x: bool) -> bool:
        return None  # bad-return-type
      bar(None)  # wrong-arg-types
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
    self.assertNoCrash(
        self.Check,
        """
      import unknown_module
      def f(x: unknown_module.Iterable):
        pass
    """,
    )

  def test_any(self):
    ty = self.Infer("""
      from typing import Any
      def f(x: Any):
        pass
      x = f(3)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def f(x) -> None: ...
      x = ...  # type: None
    """,
    )

  def test_dict(self):
    self.InferWithErrors("""
      from typing import Dict, List
      def keys(d: Dict[str, int]):
        return
      keys({"foo": 3})
      keys({})  # ok
      keys({3: 3})  # wrong-arg-types
    """)

  def test_sequence(self):
    self.InferWithErrors("""
      from typing import Sequence
      def f(s: Sequence):
        return s
      f([1,2,3])
      f((1,2,3))
      f({1,2,3})  # wrong-arg-types
      f(1)  # wrong-arg-types
    """)

  def test_optional(self):
    self.InferWithErrors("""
      from typing import Optional
      def f(s: Optional[int]):
        return s
      f(1)
      f(None)
      f("foo")  # wrong-arg-types
    """)

  def test_set(self):
    self.InferWithErrors("""
      from typing import Set
      def f(d: Set[str]):
        return
      f({"foo"})  # ok
      f(set())  # ok
      f({})  # {} isn't a set  # wrong-arg-types
      f({3})  # wrong-arg-types
    """)

  def test_frozenset(self):
    self.InferWithErrors("""
      from typing import FrozenSet
      def f(d: FrozenSet[str]):
        return
      f(frozenset(["foo"]))  # ok
      f(frozenset())  # ok
      f(frozenset([3]))  # wrong-arg-types
    """)

  def test_generic_and_typevar(self):
    self.assertNoCrash(
        self.Check,
        """
      import typing
      _T = typing.TypeVar("_T")
      class A(typing.Generic[_T]):
        ...
    """,
    )

  def test_jump_into_class_through_annotation(self):
    self.Check("""
      class Foo:
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

      class B:
        pass
    """)
    self.Check("""
      def f(a) -> "B":
        return B()

      class B:
        pass
    """)

  def test_without_forward_decl(self):
    _, errorlog = self.InferWithErrors("""
      def f(a) -> Bar:  # name-error[e]
        return Bar()

      class Bar:
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Bar"})

  def test_invalid_forward_decl(self):
    self.Check("""
      def f(a) -> "Foo":
        return Foo()

      class Foo:
        pass
    """)
    _, errorlog = self.InferWithErrors("""
      def f(a: "Foo"):  # name-error[e]
        return B()

      class B:
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e": r"Foo"})

  def test_forward_decl_bad_return(self):
    _, errorlog = self.InferWithErrors("""
        def f() -> "Foo":
          return 1  # bad-return-type[e]

        class Foo:
          pass
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorRegexes(errorlog, {"e": r"return type.*int"})

  def test_confusing_forward_decl(self):
    _, errorlog = self.InferWithErrors("""
        class Foo:
          def foo(self):
            return 4

        def f() -> "Foo":
          return Foo()

        class Foo:
          def bar(self):
            return 2

        def g():
          return f().bar()  # attribute-error[e]
    """)
    # Error message along the lines: No attribute 'bar' on Foo
    self.assertErrorRegexes(errorlog, {"e": r"\'bar\'.*Foo"})

  def test_return_type_error(self):
    _, errors = self.InferWithErrors("""
      class FooBar: pass
      def f() -> FooBar:
        return 3  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected: FooBar"})

  def test_unknown_argument(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
        def factory() -> type: ...
      """,
      )
      ty = self.Infer(
          """
        import a
        A = a.factory()
        def f(x: A):
          return x.name
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        from typing import Any
        A = ...  # type: Any
        def f(x) -> Any: ...
      """,
      )

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
    self.assertTypesMatchPytd(
        ty,
        """
      def foo() -> None: ...
      def bar(path: str, **kwargs) -> str: ...
    """,
    )
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

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
    self.assertTypesMatchPytd(
        ty,
        """
      def foo() -> None: ...
      def bar(path: str, **kwargs) -> str: ...
    """,
    )
    error = r"Actually passed:.*path: None"
    self.assertErrorRegexes(errors, {"e": error})

  def test_skip_functions_with_annotations(self):
    ty = self.Infer(
        """
      _analyzed_baz = None
      class Foo:
        def __init__(self):
          self._executed_init = True
        def bar(self, x: int) -> None:
          self._analyzed_bar = True
      def baz(x: int) -> None:
        global _analyzed_baz
        _analyzed_baz = 3
    """,
        analyze_annotated=False,
    )
    self.assertTypesMatchPytd(
        ty,
        """
      _analyzed_baz = ... # type: None
      class Foo:
        # We expect to *not* see _analyzed_bar here, because it's an attribute
        # initialized by a function we're not analyzing.
        _executed_init = ...  # type: bool
        def __init__(self) -> None: ...
        def bar(self, x: int) -> None: ...
      def baz(x: int) -> None: ...
    """,
    )

  def test_annotated_init(self):
    ty = self.Infer("""
      class A:
        def __init__(self, x: str):
          self.x = x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class A:
        x = ...  # type: str
        def __init__(self, x: str) -> None: ...
    """,
    )

  def test_union_instantiation(self):
    # If unions are not instantiated properly, the call to x.value will
    # cause an error and Infer will fail.
    self.Infer("""
      from typing import Union

      class Container1:
        def __init__(self, value):
          self.value1 = value

      class Container2:
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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Union
      class A: ...
      class B:
        x = ...  # type: int
      def f(v: Union[A, B]) -> int: ...
    """,
    )
    self.assertErrorRegexes(errors, {"e": r"x.*A"})

  def test_tuple(self):
    ty = self.Infer("""
      def f():
        return (0, "")
      def g(x: str):
        return x
      x = g(f()[1])
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Tuple
      def f() -> Tuple[int, str]: ...
      def g(x: str) -> str: ...
      x = ...  # type: str
    """,
    )

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
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"list\[int\] or list\[str\].*constant",
            "e2": r"int or str.*constant",
        },
    )

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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict
      def f(x, **kwargs: int) -> Dict[str, int]: ...
      def g() -> Dict[str, float]: ...
      def h() -> Dict[float, int]: ...
    """,
    )
    error1 = (
        r"Expected.*Mapping\[str, int\].*"
        r"Actually passed.*dict\[str, float\]"
    )
    error2 = (
        r"Expected.*Mapping\[str, int\].*"
        r"Actually passed.*dict\[float, int\]"
    )
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
      class A:
        pass
      def f(*args: A):
        return args[0]
      def g(**kwargs: A):
        return kwargs["x"]
      v1 = f()
      v2 = g()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class A: ...
      def f(*args: A) -> A: ...
      def g(**kwargs: A) -> A: ...
      v1 = ...  # type: A
      v2 = ...  # type: A
    """,
    )

  def test_use_varargs_and_kwargs_in_forward_references(self):
    self.Check("""
      class Foo:
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
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List, Union
      class A:
        x = ...  # type: int
      def f() -> Union[A, None]: ...
      def g() -> List[None]: ...
      v1 = ...  # type: int
      v2 = ...  # type: None
    """,
    )
    self.assertErrorRegexes(errors, {"e": r"x.*None"})

  def test_match_late_annotation(self):
    _, errors = self.InferWithErrors("""
      class A:
        def f(self, x: "A"):
          pass
      def f():
        A().f(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*int"})

  def test_recursive_forward_reference(self):
    _, errors = self.InferWithErrors("""
      class A:
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
      class A:
        def f(self, x: "A"):
          pass
      A().f(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"A.*int"})

  def test_return_annotation1(self):
    ty = self.Infer("""
      class A:
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      x = A.New().x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class A:
        x = ...  # type: int
        def __init__(self) -> None: ...
        @staticmethod
        def New() -> A: ...
      x = ...  # type: int
    """,
    )

  def test_return_annotation2(self):
    ty = self.Infer("""
      class A:
        def __init__(self):
          self.x = 42
        @staticmethod
        def New() -> "A":
          return A()
      def f():
        return A.New().x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class A:
        x = ...  # type: int
        def __init__(self) -> None: ...
        @staticmethod
        def New() -> A: ...
      def f() -> int: ...
    """,
    )

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
      class X:
        def __init__(self) -> None:
          self.foo = 1
      def get_foo() -> int:
        return new_x().foo
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      def new_x() -> X: ...
      def get_foo() -> int: ...

      class X:
        foo = ...  # type: int
        def __init__(self) -> None: ...
    """,
    )

  def test_change_annotated_arg(self):
    ty, _ = self.InferWithErrors("""
      from typing import Dict
      def f(x: Dict[str, str]):
        x[True] = 42  # container-type-mismatch[e]
        return x
      v = f({"a": "b"})
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict, Union
      def f(x: Dict[str, str]) -> Dict[Union[str, bool], Union[str, int]]: ...
      v = ...  # type: Dict[Union[str, bool], Union[str, int]]
    """,
    )

  def test_inner_string_annotation(self):
    ty = self.Infer("""
      from typing import List
      def f(x: List["A"]) -> int:
        return 0
      class A:
        pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List

      def f(x: List[A]) -> int: ...

      class A: ...
    """,
    )

  def test_type_alias_annotation(self):
    ty = self.Infer("""
      from typing import List
      TypeA = "A"
      ListA = "List[A]"
      def f(x: "ListA") -> int:
        return 0
      class A:
        pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List
      ListA = ...  # type: str
      TypeA = ...  # type: str
      def f(x: typing.List[A]) -> int: ...
      class A:
          pass
    """,
    )

  def test_double_string(self):
    ty = self.Infer("""
      from typing import List
      def f(x: "List[\\"int\\"]") -> int:
        return 0
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List
      def f(x: List[int]) -> int: ...
    """,
    )

  def test_duplicate_identifier(self):
    ty = self.Infer("""
      t = int
      def f(x: t) -> int: return 0
      def g(x: "t") -> int: return 0
      t = float
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Type
      t: Type[float]
      def f(x: int) -> int: ...
      def g(x: int) -> int: ...
    """,
    )

  def test_ellipsis(self):
    ty, errors = self.InferWithErrors("""
      from typing import Dict, Tuple
      def f(x: ...): pass  # experimental "inferred type": see b/213607272
      def g(x: Tuple[str, ...]): pass
      def h(x: Dict[..., int]): pass  # invalid-annotation[e]
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Dict, Tuple
      def f(x) -> None: ...
      def g(x: Tuple[str, ...]) -> None: ...
      def h(x: Dict[Any, int]) -> None: ...
    """,
    )
    self.assertErrorRegexes(errors, {"e": r"Ellipsis.*Dict"})

  def test_custom_container(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        from typing import Generic
        T = TypeVar("T")
        T2 = TypeVar("T2")
        class Foo(Generic[T]):
          def __init__(self, x: T2):
            self = Foo[T2]
      """,
      )
      _, errors = self.InferWithErrors(
          """
        import foo
        def f(x: foo.Foo[int]):
          pass
        f(foo.Foo(42))
        f(foo.Foo(""))  # wrong-arg-types[e]
      """,
          pythonpath=[d.path],
      )
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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Optional, Union
      def f1(x: str = ...) -> None: ...
      def f2(x: Optional[str] = ...) -> None: ...
      def f3(x: Optional[str] = ...) -> None: ...
      def f4(x: Union[str, int] = ...) -> None: ...
    """,
    )

  def test_infer_return(self):
    ty = self.Infer(
        """
      def f(x: int):
        return x
    """,
        analyze_annotated=False,
    )
    self.assertTypesMatchPytd(
        ty,
        """
      def f(x: int) -> int: ...
    """,
    )

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
      class A:
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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Callable, List
      def f(x: List[Callable[[int], str]]) -> None: ...
    """,
    )

  def test_late_annotation_non_name_error(self):
    self.CheckWithErrors("""
      class Foo:
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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Dict
      def f(x: Dict[str, Any]) -> None: ...
    """,
    )

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
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        class Foo: ...
      """,
      )
      self.Check(
          """
        import foo
        from typing import Tuple
        def f(x: Tuple[str, 'foo.Foo']):
          pass
      """,
          pythonpath=[d.path],
      )

  def test_tuple_container_check(self):
    # Regression test for a container_type_mismatch crash that was caused by
    # two tuples having the same type key and one of them therefore being
    # omitted from argument views.
    self.Check("""
      from typing import Dict, Tuple

      _FilesMap = Dict[Tuple[int, int], int]

      class ShardinfoGen:
        def _GenerateFiles(self):
          def _GenerateService():
            d2f = {}  # type: _FilesMap
            d2f[(0, 1)] = 3
            d2f[(4, 5)] = 6
            files.update(d2f)
          files = {}  # type: _FilesMap
          for _ in __any_object__:
            _GenerateService()
    """)

  def test_newtype_container_check(self):
    errors = self.CheckWithErrors("""
      from typing import Dict, NewType, Set
      ClusterInfoConfig = NewType('ClusterInfoConfig', Dict[str, int])
      class CommonConfigBuilder:
        def _AddMachines(self, cluster_info_config: ClusterInfoConfig):
          cluster_info_config[''] = {}  # container-type-mismatch[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Container: dict\[_K, _V\].*_V: int.*_V: dict"}
    )

  def test_check_defaults(self):
    # Because 0.0 == False in Python, previously buggy caching led to `False`
    # being converted to the cached abstract value for `0.0`.
    self.Check("""
      def f(x=0.0):
        pass
      def g(y: bool = False):
        pass
    """)

  def test_circular_ref(self):
    with self.DepTree([(
        "foo.pyi",
        """
      from typing import Callable, Generic, Sequence, TypeVar
      T = TypeVar('T')
      class BaseRegion(Generic[T]):
        @property
        def zones(self) -> Sequence[T]: ...
      class BaseZone(Generic[T]):
        @property
        def region(self) -> T: ...
    """,
    )]):
      ty = self.Infer("""
        import foo
        class Region(foo.BaseRegion['Zone']):
          pass
        class Zone(foo.BaseZone['Region']):
          pass
      """)
      self.assertTypesMatchPytd(
          ty,
          """
        import foo
        class Region(foo.BaseRegion[Zone]): ...
        class Zone(foo.BaseZone[Region]): ...
      """,
      )

  def test_recursion_in_parent(self):
    self.Check("""
      class C(dict[str, tuple['C', 'C']]):
        def f(self):
          pass
      C()
    """)

  def test_recursion_in_imported_class(self):
    with self.DepTree([(
        "foo.pyi",
        """
      from typing import MutableMapping, TypeVar, Union
      T = TypeVar('T')
      class NestedDict(MutableMapping[str, Union[T, "NestedDict"]]): ...
      class Array: ...
      class SpecDict(NestedDict[Array]): ...
    """,
    )]):
      self.Check("""
        import foo
        def f() -> foo.SpecDict:
          return foo.SpecDict()
      """)

  def test_forward_ref_determinism(self):
    # Repeat this test 20 times to check that the result is deterministic.
    for _ in range(20):
      self.Check("""
        import dataclasses
        from typing import List

        @dataclasses.dataclass
        class ChatMessage:
          speaker: 'ChatUser'

        class ChatUser:
          def __init__(self, name: str, chat_room: 'ChatRoom'):
            self.name = name
            self.chat_room = chat_room
            if self.name in self.chat_room.user_map:
              raise ValueError()

        class ChatRoom:
          def __init__(self, users: List[ChatUser]):
            self.user_map = {u.name: u for u in users}
      """)


class TestAnnotationsPython3Feature(test_base.BaseTest):
  """Tests for PEP 484 style inline annotations."""

  def test_variable_annotations(self):
    ty = self.Infer("""
      a: int = 42
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      a: int
    """,
    )

  def test_container_mutation(self):
    errors = self.CheckWithErrors("""
      from typing import List
      x: List[int] = []
      x.append("hello")  # container-type-mismatch[e]
    """)
    pattern = r"Container.*list\[_T\].*Allowed.*int.*New.*str"
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
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Tuple
      def quack(x, *args: int) -> Tuple[int, ...]: ...
    """,
    )
    error = r"Expected.*Iterable\[int\].*Actually passed.*tuple\[float\]"
    self.assertErrorRegexes(errors, {"e": error})

  def test_container_multiple_mutations(self):
    errors = self.CheckWithErrors("""
      from typing import Dict
      x: Dict[int, str] = {}
      x["hello"] = 1.0  # container-type-mismatch[e]
    """)
    pattern = (
        r"New container.*for x.*dict\[_K, _V\].*"
        + r"Allowed.*_K.*int.*_V.*str.*"
        r"New.*_K.*str.*_V.*float"
    )
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

  def test_anystr_error(self):
    errors = self.CheckWithErrors("""
      from typing import AnyStr, List, Union
      x: Union[List[AnyStr], List[int]]  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": "'AnyStr' not in scope"})

  def test_protocol_container(self):
    self.Check("""
      import functools
      from typing import Any, Callable, List
      x: List[Callable[..., Any]] = []
      x.append(functools.partial(int, '42'))
    """)

  def test_container_if_splitting(self):
    self.Check("""
      from typing import List, Optional
      def f() -> Optional[str]:
        return __any_object__
      lst: List[str] = []
      x = f()
      if x is not None:
        lst.append(x)
    """)

  def test_imported_container_type(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        from typing import Dict, List, Union
        MyDict = Dict[str, int]
        def f() -> Union[List[MyDict], MyDict]: ...
      """,
      )
      errors = self.CheckWithErrors(
          """
        import foo
        from typing import List
        x: List[foo.MyDict] = []
        x.append(foo.f())  # container-type-mismatch[e]
      """,
          pythonpath=[d.path],
      )
      self.assertErrorRegexes(
          errors,
          {
              "e": (
                  r"Allowed contained types.*dict\[str, int\].*"
                  r"New contained types.*list\[dict\[str, int\]\]"
              )
          },
      )


class TestStringifiedAnnotations(test_base.BaseTest):
  """Tests for stringified annotations."""

  def test_postponed_evaluation(self):
    self.Check("""
      from __future__ import annotations
      def f() -> int:
        return 0
    """)

  def test_postponed_evaluation_error(self):
    self.CheckWithErrors("""
      from __future__ import annotations
      def f() -> str:
        return 0  # bad-return-type
    """)

  def test_forward_reference(self):
    self.Check("""
      from __future__ import annotations
      from typing import Optional
      class A:
        b: Optional[B] = None
      class B:
        pass
      assert_type(A().b, Optional[B])
    """)

  def test_explicit_forward_reference(self):
    # Check that explicit string annotations still work.
    self.Check("""
      from __future__ import annotations
      from typing import Optional
      class A:
        b: Optional['B'] = None
        c: "Optional['B']" = None
      class B:
        pass
      assert_type(A().b, Optional[B])
      assert_type(A().c, Optional[B])
    """)

  def test_generic_forward_reference_to_collection(self):
    # Makes sure that we don't get an error when set[int] is converted to
    # typing.Set[int] (since typing.Set is not imported).
    ty = self.Infer("""
      from __future__ import annotations
      from typing import Generic, TypeVar

      T = TypeVar("T")

      class A(Generic[T]):
        def f(self) -> A[set[int]]:
          return self
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Generic, Set, TypeVar
      T = TypeVar('T')
      class A(Generic[T]):
        def f(self) -> A[Set[int]]: ...
   """,
    )


class EllipsisTest(test_base.BaseTest):
  """Tests usage of '...' to mean "inferred type".

  This is an experimental feature that makes it possible to explicitly annotate
  a type as inferred. See b/213607272.
  """

  def test_variable(self):
    ty = self.Infer("x: ... = 0")
    self.assertTypesMatchPytd(ty, "x: int")

  def test_function(self):
    ty = self.Infer("""
      def f(x: ...) -> ...:
        return x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      _T0 = TypeVar('_T0')
      def f(x: _T0) -> _T0: ...
    """,
    )

  def test_class(self):
    ty = self.Infer("""
      class Foo:
        x: ...
        def f(self):
          self.x = 5
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      class Foo:
        x: int
        def f(self) -> None: ...
    """,
    )

  def test_future(self):
    ty = self.Infer("""
      from __future__ import annotations
      x: ...
      x = 5
      def f(x: ...): pass
      class Foo:
        x: ...
        def f(self):
          self.x = 5
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      x: int
      def f(x) -> None: ...
      class Foo:
        x: int
        def f(self) -> None: ...
    """,
    )

  def test_try_except_block(self):
    # Regression test - the first except line puts a `STORE_NAME e` opcode in
    # the next line, and the annotation on `a: int` therefore has two STORE ops
    # in its line. This test confirms that the `int` annotation gets put on
    # `STORE_NAME a` rather than `STORE_NAME e`
    self.Check("""
      try:
        1
      except Exception as e:
        a: int = 10

      try:
        x = 1
      except Exception as e:
        pass
    """)


class BareAnnotationTest(test_base.BaseTest):
  """Tests variable annotations without assignment."""

  def test_bare_annotations(self):
    ty = self.Infer("""
      class Foo:
        a: bool
        def __init__(self):
          self.x: int
          self.y: list[
                    int]
          z: str
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List
      class Foo:
        a: bool
        x: int
        y: List[int]
        def __init__(self) -> None: ...
    """,
    )

  def test_global(self):
    self.Check("""
      x: int
      def f() -> int:
        return x
    """)


if __name__ == "__main__":
  test_base.main()
