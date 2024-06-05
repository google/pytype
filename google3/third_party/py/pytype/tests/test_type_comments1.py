"""Tests for type comments."""

from pytype.tests import test_base
from pytype.tests import test_utils


class FunctionCommentTest(test_base.BaseTest):
  """Tests for type comments."""

  def test_function_unspecified_args(self):
    ty = self.Infer("""
      def foo(x):
        # type: (...) -> int
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> int: ...
    """)

  def test_function_return_space(self):
    ty = self.Infer("""
      from typing import Dict
      def foo(x):
        # type: (...) -> Dict[int, int]
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def foo(x) -> Dict[int, int]: ...
    """)

  def test_function_zero_args(self):
    # Include some stray whitespace.
    ty = self.Infer("""
      def foo():
        # type: (  ) -> int
        return 0
    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> int: ...
    """)

  def test_function_one_arg(self):
    # Include some stray whitespace.
    ty = self.Infer("""
      def foo(x):
        # type: ( int ) -> int
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int) -> int: ...
    """)

  def test_function_several_args(self):
    ty = self.Infer("""
      def foo(x, y, z):
        # type: (int, str, float) -> None
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str, z: float) -> None: ...
    """)

  def test_function_several_lines(self):
    ty = self.Infer("""
      def foo(x,
              y,
              z):
        # type: (int, str, float) -> None
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str, z: float) -> None: ...
    """)

  def test_function_comment_on_colon(self):
    self.InferWithErrors("""
      def f(x) \\
        : # type: (None) -> None
        return True  # bad-return-type
    """)

  def test_function_comment_on_def_line(self):
    ty = self.Infer("""
      def f(x):  # type: (int) -> int
        return x
    """)
    self.assertTypesMatchPytd(ty, "def f(x: int) -> int: ...")

  def test_multiple_function_comments(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        # type: (None) -> bool
        # type: (str) -> str  # ignored-type-comment[e]
        return True
    """)
    self.assertErrorRegexes(errors, {"e": r"Stray type comment:.*str"})

  def test_function_none_in_args(self):
    ty = self.Infer("""
      def foo(x, y, z):
        # type: (int, str, None) -> None
        return z
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str, z: None) -> None: ...
    """)

  def test_self_is_optional(self):
    ty = self.Infer("""
      class Foo:
        def f(self, x):
          # type: (int) -> None
          pass

        def g(self, x):
          # type: (Foo, int) -> None
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def f(self, x: int) -> None: ...
        def g(self, x: int) -> None: ...
    """)

  def test_cls_is_optional(self):
    ty = self.Infer("""
      class Foo:
        @classmethod
        def f(cls, x):
          # type: (int) -> None
          pass

        @classmethod
        def g(cls, x):
          # type: (Foo, int) -> None
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        @classmethod
        def f(cls, x: int) -> None: ...
        @classmethod
        def g(cls: Foo, x: int) -> None: ...
    """)

  def test_function_stararg(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self, *args):
          # type: (int) -> None
          self.value = args[0]
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        value = ...  # type: int
        def __init__(self, *args: int) -> None: ...
    """)

  def test_function_starstararg(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self, **kwargs):
          # type: (int) -> None
          self.value = kwargs['x']
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        value = ...  # type: int
        def __init__(self, **kwargs: int) -> None: ...
    """)

  @test_utils.skipFromPy(
      (3, 10),
      "In 3.10+, we can't associate the function type comment to the function "
      "because the function body opcodes have line number 1 instead of 3. "
      "Since function type comments are long-deprecated, we don't bother "
      "trying to make this work.")
  def test_function_without_body(self):
    ty = self.Infer("""
      def foo(x, y):
        # type: (int, str) -> None
        '''Docstring but no body.'''
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x: int, y: str) -> None: ...
    """)

  def test_filter_out_class_constructor(self):
    # We should not associate the typecomment with the function A()
    self.Check("""
      class A:
        x = 0 # type: int
    """)

  def test_type_comment_after_docstring(self):
    """Type comments after the docstring should not be picked up."""
    self.InferWithErrors("""
      def foo(x, y):
        '''Ceci n'est pas une type.'''
        # type: (int, str) -> None  # ignored-type-comment
    """)

  def test_function_no_return(self):
    self.InferWithErrors("""
      def foo():
        # type: () ->  # invalid-function-type-comment
        pass
    """)

  def test_function_too_many_args(self):
    _, errors = self.InferWithErrors("""
      def foo(x):
        # type: (int, str) -> None  # invalid-function-type-comment[e]
        y = x
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 1 args, 2 given"})

  def test_function_too_few_args(self):
    _, errors = self.InferWithErrors("""
      def foo(x, y, z):
        # type: (int, str) -> None  # invalid-function-type-comment[e]
        y = x
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 3 args, 2 given"})

  def test_function_too_few_args_do_not_count_self(self):
    _, errors = self.InferWithErrors("""
      def foo(self, x, y, z):
        # type: (int, str) -> None  # invalid-function-type-comment[e]
        y = x
        return x
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected 3 args, 2 given"})

  def test_function_missing_args(self):
    self.InferWithErrors("""
      def foo(x):
        # type: () -> int  # invalid-function-type-comment
        return x
    """)

  def test_invalid_function_type_comment(self):
    self.InferWithErrors("""
      def foo(x):
        # type: blah blah blah  # invalid-function-type-comment
        return x
    """)

  def test_invalid_function_args(self):
    _, errors = self.InferWithErrors("""
      def foo(x):
        # type: (abc def) -> int  # invalid-function-type-comment[e]
        return x
    """)
    if self.python_version >= (3, 10):
      error_reason = "invalid syntax"
    else:
      error_reason = "unexpected EOF"
    self.assertErrorRegexes(errors, {"e": rf"abc def.*{error_reason}"})

  def test_ambiguous_annotation(self):
    _, errors = self.InferWithErrors("""
      def foo(x):
        # type: (int if __random__ else str) -> None  # invalid-function-type-comment[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str.*constant"})

  @test_utils.skipFromPy(
      (3, 10),
      "In 3.10+, we can't associate the function type comment to function g "
      "because the opcodes in the body of g have line number 2 instead of 4. "
      "Since function type comments are long-deprecated, we don't bother "
      "trying to make this work.")
  def test_one_line_function(self):
    ty = self.Infer("""
      def f(): return 0
      def g():
        # type: () -> None
        '''Docstring.'''
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
      def g() -> None: ...
    """)

  def test_comment_after_type_comment(self):
    ty = self.Infer("""
      def f(x):
        # type: (...) -> type
        # comment comment comment
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> type: ...
    """)


class AssignmentCommentTest(test_base.BaseTest):
  """Tests for type comments applied to assignments."""

  def test_class_attribute_comment(self):
    ty = self.Infer("""
      class Foo:
        s = None  # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        s = ...  # type: str
    """)

  def test_instance_attribute_comment(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self):
          self.s = None  # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        s = ...  # type: str
        def __init__(self) -> None: ...
    """)

  def test_global_comment(self):
    ty = self.Infer("""
      X = None  # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: str
    """)

  def test_global_comment2(self):
    ty = self.Infer("""
      X = None  # type: str
      def f(): global X
    """)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: str
      def f() -> None: ...
    """)

  def test_local_comment(self):
    ty = self.Infer("""
      X = None

      def foo():
        x = X  # type: str
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: None
      def foo() -> str: ...
    """)

  def test_cellvar_comment(self):
    """Type comment on an assignment generating the STORE_DEREF opcode."""
    ty = self.Infer("""
      from typing import Mapping
      def f():
        map = dict()  # type: Mapping
        return (map, {x: map.get(y) for x, y in __any_object__})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Mapping, Tuple
      def f() -> Tuple[Mapping, dict]: ...
    """)

  def test_bad_comment(self):
    ty, errors = self.InferWithErrors("""
      X = None  # type: abc def  # invalid-annotation[e]
    """)
    if self.python_version >= (3, 10):
      error_reason = "invalid syntax"
    else:
      error_reason = "unexpected EOF"
    self.assertErrorRegexes(errors, {"e": rf"abc def.*{error_reason}"})
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def test_conversion_error(self):
    ty, errors = self.InferWithErrors("""
      X = None  # type: 1 if __random__ else 2  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"X.*Must be constant"})
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def test_name_error_inside_comment(self):
    _, errors = self.InferWithErrors("""
      X = None  # type: Foo  # name-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Foo"})

  def test_warn_on_ignored_type_comment(self):
    _, errors = self.InferWithErrors("""
      X = []
      X[0] = None  # type: str  # ignored-type-comment[e1]
      # type: int  # ignored-type-comment[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"str", "e2": r"int"})

  def test_attribute_initialization(self):
    ty = self.Infer("""
      class A:
        def __init__(self):
          self.x = 42
      a = None  # type: A
      x = a.x
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x = ...  # type: int
        def __init__(self) -> None: ...
      a = ...  # type: A
      x = ...  # type: int
    """)

  def test_none_to_none_type(self):
    ty = self.Infer("""
      x = None  # type: None
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: None
    """)

  def test_module_instance_as_bad_type_comment(self):
    _, errors = self.InferWithErrors("""
      import sys
      x = None  # type: sys  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"instance of module.*x"})

  def test_forward_reference(self):
    ty, errors = self.InferWithErrors("""
      a = None  # type: "A"
      b = None  # type: "Nonexistent"  # name-error[e]
      class A:
        def __init__(self):
          self.x = 42
        def f(self):
          return a.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A:
        x = ...  # type: int
        def __init__(self) -> None: ...
        def f(self) -> int: ...
      a = ...  # type: A
      b = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"Nonexistent"})

  def test_class_variable_forward_reference(self):
    ty = self.Infer("""
      class A:
        a = None  # type: 'A'
        def __init__(self):
          self.x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        a: A
        x: int
        def __init__(self) -> None: ...
    """)

  def test_use_forward_reference(self):
    ty = self.Infer("""
      a = None  # type: "A"
      x = a.x
      class A:
        def __init__(self):
          self.x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A:
        x = ...  # type: int
        def __init__(self) -> None: ...
      a = ...  # type: A
      x = ...  # type: Any
    """)

  def test_use_class_variable_forward_reference(self):
    # Attribute accesses for A().a all get resolved to Any (b/134706992)
    ty = self.Infer("""
      class A:
        a = None  # type: 'A'
        def f(self):
          return self.a
      x = A().a
      def g():
        return A().a
      y = g()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      _TA = TypeVar('_TA', bound=A)
      class A:
        a: A
        def f(self: _TA) -> _TA: ...
      x: A
      y: A
      def g() -> A: ...
    """)

  def test_class_variable_forward_reference_error(self):
    self.InferWithErrors("""
      class A:
        a = None  # type: 'A'
      g = A().a.foo()  # attribute-error
    """)

  def test_multiline_value(self):
    ty, errors = self.InferWithErrors("""
      v = [
        {
        "a": 1  # type: complex  # ignored-type-comment[e1]

        }  # type: dict[str, int]  # ignored-type-comment[e2]
      ]  # type: list[dict[str, float]]
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: list[dict[str, float]]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Stray type comment: complex",
        "e2": r"Stray type comment: dict\[str, int\]"})

  def test_multiline_value_with_blank_lines(self):
    ty = self.Infer("""
      a = [[

      ]

      ]  # type: list[list[int]]
    """)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: list[list[int]]
    """)

  def test_type_comment_name_error(self):
    _, errors = self.InferWithErrors("""
      def f():
        x = None  # type: Any  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"not defined$"})

  def test_type_comment_invalid_syntax(self):
    _, errors = self.InferWithErrors("""
      def f():
        x = None  # type: y = 1  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"invalid syntax$"})

  def test_discarded_type_comment(self):
    """Discard the first whole-line comment, keep the second."""
    ty = self.Infer("""
        # We want either # type: ignore or # type: int
        def hello_world():
          # type: () -> str
          return 'hello world'
    """)
    self.assertTypesMatchPytd(ty, """
      def hello_world() -> str: ...
    """)

  def test_multiple_type_comments(self):
    """We should not allow multiple type comments on one line."""
    _, errors = self.InferWithErrors("""
      a = 42  # type: int  # type: float  # invalid-directive[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Multiple"})

  def test_nested_comment_alias(self):
    ty = self.Infer("""
      class A: pass
      class B:
        C = A
        x = None  # type: C
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A: pass
      class B:
        C: Type[A]
        x: A
      """)

  def test_nested_classes_comments(self):
    ty = self.Infer("""
      class A:
        class B: pass
        x = None  # type: B
      """)
    self.assertTypesMatchPytd(ty, """
      class A:
        class B: ...
        x: A.B
      """)

  def test_list_comprehension_comments(self):
    ty, errors = self.InferWithErrors("""
      from typing import List
      def f(x):
        # type: (str) -> None
        pass
      def g(xs):
        # type: (List[str]) -> List[str]
        ys = [f(x) for x in xs]  # type: List[str]  # annotation-type-mismatch[e]
        return ys
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f(x: str) -> None: ...
      def g(xs: List[str]) -> List[str]: ...
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Annotation: List\[str\].*Assignment: List\[None\]"})

  def test_multiple_assignments(self):
    ty = self.Infer("""
      a = 1; b = 2; c = 4  # type: float
    """)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: float
    """)

  def test_instantiate_fully_quoted_type(self):
    ty, errors = self.InferWithErrors("""
      from typing import Optional
      x = None  # type: "Optional[A]"
      class A:
        a = 0
      y = x.a  # attribute-error[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      x: Optional[A]
      class A:
        a: int
      y: int
    """)
    self.assertErrorRegexes(errors, {"e": r"a.*None"})

  def test_do_not_resolve_late_type_to_function(self):
    ty = self.Infer("""
      v = None  # type: "A"
      class A:
        def A(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      v: A
      class A:
        def A(self) -> None: ...
    """)

  def test_illegal_function_late_type(self):
    self.CheckWithErrors("""
      v = None  # type: "F"  # invalid-annotation
      def F(): pass
    """)

  def test_bad_type_comment_in_constructor(self):
    self.CheckWithErrors("""
      class Foo:
        def __init__(self):
          self.x = None  # type: "Bar"  # name-error
    """)

  def test_dict_type_comment(self):
    self.Check("""
      from typing import Any, Callable, Dict, Tuple
      d = {
          'a': 'long'
               'string'
               'value'
      }  # type: Dict[str, str]
    """)

  def test_break_on_period(self):
    self.Check("""
      really_really_really_long_module_name = None  # type: module
      d = {}
      v = d.get('key', (really_really_really_long_module_name.
                        also_long_attribute_name))  # type: int
    """)

  def test_assignment_between_functions(self):
    ty = self.Infer("""
      def f(): pass
      x = 0  # type: int
      def g():
        '''Docstring.'''
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> None: ...
      x: int
      def g() -> None: ...
    """)

  def test_type_comment_on_class(self):
    # What error is reported differs depending on whether directors.py is using
    # libcst (host 3.8-) or ast (host 3.9+) and the target version. All we care
    # about is that the type comment is not ignored.
    self.CheckWithErrors("""
      class Foo(  # annotation-type-mismatch<3.9
          int):  # type: str  # ignored-type-comment>=3.9
        pass
    """)


if __name__ == "__main__":
  test_base.main()
