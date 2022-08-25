"""Tests for displaying errors."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ErrorTest(test_base.BaseTest):
  """Tests for errors."""

  def test_deduplicate(self):
    errors = self.CheckWithErrors("""
      def f(x):
        y = 42
        y.foobar  # attribute-error[e]
      f(3)
      f(4)
    """)
    self.assertErrorRegexes(errors, {"e": r"'foobar' on int$"})

  def test_unknown_global(self):
    errors = self.CheckWithErrors("""
      def f():
        return foobar()  # name-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"foobar"})

  def test_invalid_attribute(self):
    ty, errors = self.InferWithErrors("""
      class A:
        pass
      def f():
        (3).parrot  # attribute-error[e]
        return "foo"
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        pass

      def f() -> str: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"parrot.*int"})

  def test_import_error(self):
    self.InferWithErrors("""
      import rumplestiltskin  # import-error
    """)

  def test_import_from_error(self):
    errors = self.CheckWithErrors("""
      from sys import foobar  # import-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"sys\.foobar"})

  def test_name_error(self):
    self.InferWithErrors("""
      foobar  # name-error
    """)

  def test_wrong_arg_count(self):
    errors = self.CheckWithErrors("""
      hex(1, 2, 3, 4)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"expects 1.*got 4"})

  def test_wrong_arg_types(self):
    errors = self.CheckWithErrors("""
      hex(3j)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*complex"})

  def test_interpreter_function_name_in_msg(self):
    errors = self.CheckWithErrors("""
      class A(list): pass
      A.append(3)  # missing-parameter[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"function list\.append"})

  def test_pytd_function_name_in_msg(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", "class A(list): pass")
      errors = self.CheckWithErrors("""
        import foo
        foo.A.append(3)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"function list\.append"})

  def test_builtin_function_name_in_msg(self):
    errors = self.CheckWithErrors("""
      x = list
      x += (1,2)  # missing-parameter[e]
      """)
    self.assertErrorRegexes(errors, {"e": r"function list\.__iadd__"})

  def test_rewrite_builtin_function_name(self):
    """Should rewrite `function builtins.len` to `built-in function len`."""
    errors = self.CheckWithErrors("x = len(None)  # wrong-arg-types[e]")
    self.assertErrorRegexes(errors, {"e": r"Built-in function len"})

  def test_bound_method_name_in_msg(self):
    errors = self.CheckWithErrors("""
      "".join(1)  # wrong-arg-types[e]
      """)
    self.assertErrorRegexes(errors, {"e": r"Function str\.join"})

  def test_nested_class_method_name_is_msg(self):
    errors = self.CheckWithErrors("""
      class A:
        class B:
          def f(self):
            pass
      A.B().f("oops")  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Function B.f"})

  def test_pretty_print_wrong_args(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(a: int, b: int, c: int, d: int, e: int): ...
      """)
      errors = self.CheckWithErrors("""
        import foo
        foo.f(1, 2, 3, "four", 5)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
    self.assertErrorSequences(errors, {
        "e": ["a, b, c, d: int, ...", "a, b, c, d: str, ..."]})

  def test_invalid_base_class(self):
    self.InferWithErrors("""
      class Foo(3):  # base-class-error
        pass
    """)

  def test_invalid_iterator_from_import(self):
    with test_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Codec:
            def __init__(self) -> None: ...
      """)
      errors = self.CheckWithErrors("""
        import mod
        def f():
          for row in mod.Codec():  # attribute-error[e]
            pass
      """, pythonpath=[d.path])
      self.assertErrorSequences(
          errors, {"e": ["No attribute", "__iter__", "on mod.Codec"]})

  def test_invalid_iterator_from_class(self):
    errors = self.CheckWithErrors("""
      class A:
        pass
      def f():
        for row in A():  # attribute-error[e]
          pass
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__.*A"})

  def test_iter_on_module(self):
    errors = self.CheckWithErrors("""
      import sys
      for _ in sys:  # module-attr[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__.*module 'sys'"})

  def test_inherit_from_generic(self):
    with test_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]): ...
        class Bar(Foo[int]): ...
      """)
      errors = self.CheckWithErrors("""
        import mod
        chr(mod.Bar())  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      # "Line 3, in f: Can't retrieve item out of dict. Empty?"
      self.assertErrorRegexes(errors, {"e": r"int.*mod\.Bar"})

  def test_wrong_keyword_arg(self):
    with test_utils.Tempdir() as d:
      d.create_file("mycgi.pyi", """
        from typing import Union
        def escape(x: Union[str, int]) -> Union[str, int]: ...
      """)
      errors = self.CheckWithErrors("""
        import mycgi
        def foo(s):
          return mycgi.escape(s, quote=1)  # wrong-keyword-args[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"quote.*mycgi\.escape"})

  def test_missing_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def bar(xray, yankee, zulu) -> str: ...
      """)
      errors = self.CheckWithErrors("""
        import foo
        foo.bar(1, 2)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"zulu.*foo\.bar"})

  def test_bad_inheritance(self):
    self.InferWithErrors("""
      class X:
          pass
      class Bar(X):
          pass
      class Baz(X, Bar):  # mro-error
          pass
    """)

  def test_bad_call(self):
    with test_utils.Tempdir() as d:
      d.create_file("other.pyi", """
        def foo(x: int, y: str) -> str: ...
      """)
      errors = self.CheckWithErrors("""
        import other
        other.foo(1.2, [])  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"\(x: int"})

  def test_call_uncallable(self):
    errors = self.CheckWithErrors("""
      0()  # not-callable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int"})

  def test_super_error(self):
    errors = self.CheckWithErrors("""
      class A:
        def __init__(self):
          super(A, self, "foo").__init__()  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"2.*3"})

  def test_attribute_error(self):
    with test_utils.Tempdir() as d:
      d.create_file("modfoo.pyi", "")
      errors = self.CheckWithErrors("""
        class Foo:
          def __getattr__(self, name):
            return "attr"
        def f():
          return Foo.foo  # attribute-error[e1]
        def g(x):
          if x:
            y = None
          else:
            y = 1
          return y.bar  # attribute-error[e2]  # attribute-error[e3]
        def h():
          return Foo().foo  # No error
        import modfoo
        modfoo.baz  # module-attr[e4]
      """, pythonpath=[d.path])
      if self.python_version >= (3, 10):
        e2_msg = "No attribute 'bar' on None"
        e3_msg = "No attribute 'bar' on int"
      else:
        e2_msg = "No attribute 'bar' on int\nIn Optional[int]"
        e3_msg = "No attribute 'bar' on None\nIn Optional[int]"
      self.assertErrorSequences(errors, {
          "e1": ["No attribute 'foo' on Type[Foo]"],
          "e2": [e2_msg],
          "e3": [e3_msg],
          "e4": ["No attribute 'baz' on module 'modfoo'"]
      })

  def test_attribute_error_getattribute(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __getattribute__(self, name):
          return "attr"
      def f():
        return Foo().x  # There should be no error on this line.
      def g():
        return Foo.x  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x"})

  def test_none_attribute(self):
    errors = self.CheckWithErrors("""
      None.foo  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"foo"})

  def test_pyi_type(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: list[int]) -> int: ...
      """)
      errors = self.CheckWithErrors("""
        import foo
        foo.f([""])  # wrong-arg-types[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorSequences(errors, {"e": ["List[int]", "List[str]"]})

  def test_too_many_args(self):
    errors = self.CheckWithErrors("""
      def f():
        pass
      f(3)  # wrong-arg-count[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"0.*1"})

  def test_too_few_args(self):
    errors = self.CheckWithErrors("""
      def f(x):
        pass
      f()  # missing-parameter[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"x.*f"})

  def test_duplicate_keyword(self):
    errors = self.CheckWithErrors("""
      def f(x, y):
        pass
      f(3, x=3)  # duplicate-keyword-argument[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"f.*x"})

  def test_bad_import(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      self.InferWithErrors("""
        import a  # pyi-error
      """, pythonpath=[d.path])

  def test_bad_import_dependency(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from b import X
        class Y(X): ...
      """)
      self.InferWithErrors("""
        import a  # pyi-error
      """, pythonpath=[d.path])

  def test_bad_import_from(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
        def f() -> int: ...
        class f: ...
      """)
      d.create_file("foo/__init__.pyi", "")
      errors = self.CheckWithErrors("""
        from foo import a  # pyi-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.a"})

  def test_bad_import_from_dependency(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo/a.pyi", """
          from a import X
          class Y(X): ...
      """)
      d.create_file("foo/__init__.pyi", "")
      errors = self.CheckWithErrors("""
        from foo import a  # pyi-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.a"})

  def test_bad_container(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import SupportsInt
        class A(SupportsInt[int]): pass
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"SupportsInt is not a container"})

  def test_bad_type_parameter_order(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        K = TypeVar("K")
        V = TypeVar("V")
        class A(Generic[K, V]): pass
        class B(Generic[K, V]): pass
        class C(A[K, V], B[V, K]): pass
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"Illegal.*order.*a\.C"})

  def test_duplicate_type_parameter(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T, T]): pass
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"T"})

  def test_duplicate_generic_base_class(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        V = TypeVar("V")
        class A(Generic[T], Generic[V]): pass
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"inherit.*Generic"})

  def test_type_parameter_in_module_constant(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        x = ...  # type: T
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"a.*T.*a\.x"})

  def test_type_parameter_in_class_attribute(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]):
          x = ...  # type: T
      """)
      errors = self.CheckWithErrors("""
        import a
        def f():
          return a.A.x  # unbound-type-param[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"x.*A.*T"})

  def test_unbound_type_parameter_in_instance_attribute(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        class A:
          x = ...  # type: T
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, deep=True, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"a.*T.*a\.A\.x"})

  def test_print_union_arg(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Union
        def f(x: Union[int, str]) -> None: ...
      """)
      errors = self.CheckWithErrors("""
        import a
        x = a.f(4.2)  # wrong-arg-types[e]
      """, deep=True, pythonpath=[d.path])
      pattern = ["Expected", "Union[int, str]", "Actually passed"]
      self.assertErrorSequences(errors, {"e": pattern})

  def test_print_type_arg(self):
    errors = self.CheckWithErrors("""
      hex(int)  # wrong-arg-types[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Actually passed.*Type\[int\]"})

  def test_delete_from_set(self):
    errors = self.CheckWithErrors("""
      s = {1}
      del s[1]  # unsupported-operands[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"item deletion"})

  def test_bad_reference(self):
    ty, errors = self.InferWithErrors("""
      def main():
        x = foo  # name-error[e]
        for foo in []:
          pass
        return x
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"foo"})
    # Make sure we recovered from the error and got the right return type
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def main() -> Any: ...
    """)

  def test_set_int_attribute(self):
    errors = self.CheckWithErrors("""
      x = 42
      x.y = 42  # not-writable[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"y.*int"})

  def test_invalid_parameters_on_method(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A:
          def __init__(self, x: int) -> None: ...
      """)
      errors = self.CheckWithErrors("""
        import a
        x = a.A("")  # wrong-arg-types[e1]
        x = a.A("", 42)  # wrong-arg-count[e2]
        x = a.A(42, y="")  # wrong-keyword-args[e3]
        x = a.A(42, x=42)  # duplicate-keyword-argument[e4]
        x = a.A()  # missing-parameter[e5]
      """, pythonpath=[d.path])
      a = r"A\.__init__"
      self.assertErrorRegexes(
          errors, {"e1": a, "e2": a, "e3": a, "e4": a, "e5": a})

  def test_duplicate_keywords(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x, *args, y) -> None: ...
      """)
      self.InferWithErrors("""
        import foo
        foo.f(1, y=2)
        foo.f(1, 2, y=3)
        foo.f(1, x=1)  # duplicate-keyword-argument
        # foo.f(y=1, y=2)  # caught by compiler
      """, deep=True, pythonpath=[d.path])

  def test_invalid_parameters_details(self):
    errors = self.CheckWithErrors("""
      float(list())  # wrong-arg-types[e1]
      float(1, list(), foobar=str)  # wrong-arg-count[e2]
      float(1, foobar=list())  # wrong-keyword-args[e3]
      float(1, x="")  # duplicate-keyword-argument[e4]
      hex()  # missing-parameter[e5]
    """)
    self.assertErrorSequences(errors, {
        "e1": ["Actually passed:", "self, x: List[nothing]"],
        "e2": ["_, foobar"],
        "e3": ["Actually passed:", "self, x, foobar"],
        "e4": ["Actually passed:", "self, x, x"],
        "e5": ["Actually passed: ()"],
    })

  def test_bad_superclass(self):
    errors = self.CheckWithErrors("""
      class A:
        def f(self):
          return "foo"

      class B(A):
        def f(self):
          return super(self, B).f()  # should be super(B, self)  # wrong-arg-types[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"cls: type.*cls: B"})

  @test_base.skip("Need to type-check second argument to super")
  def test_bad_super_instance(self):
    errors = self.CheckWithErrors("""
      class A:
        pass
      class B(A):
        def __init__(self):
          super(B, A).__init__()  # A cannot be the second argument to super  # wrong-arg-types[e]
    """, deep=True)
    self.assertErrorSequences(errors, {"e": ["Type[B]", "Type[A]"]})

  def test_bad_name_import(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        import typing
        x = ...  # type: typing.Rumpelstiltskin
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorRegexes(errors, {"e": "Rumpelstiltskin"})

  def test_bad_name_import_from(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Rumpelstiltskin
        x = ...  # type: Rumpelstiltskin
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
        x = a.x
      """, pythonpath=[d.path], deep=True)
      self.assertErrorRegexes(errors, {"e": "Rumpelstiltskin"})

  def test_match_type(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type
        class A: ...
        class B(A): ...
        class C: ...
        def f(x: Type[A]) -> bool: ...
      """)
      ty, errors = self.InferWithErrors("""
        import a
        x = a.f(a.A)
        y = a.f(a.B)
        z = a.f(a.C)  # wrong-arg-types[e]
      """, pythonpath=[d.path], deep=True)
      error = ["Expected", "Type[a.A]", "Actual", "Type[a.C]"]
      self.assertErrorSequences(errors, {"e": error})
      self.assertTypesMatchPytd(ty, """
        import a
        from typing import Any
        x = ...  # type: bool
        y = ...  # type: bool
        z = ...  # type: Any
      """)

  def test_match_parameterized_type(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Type, TypeVar
        T = TypeVar("T")
        class A(Generic[T]): ...
        class B(A[str]): ...
        def f(x: Type[A[int]]): ...
      """)
      errors = self.CheckWithErrors("""
        import a
        x = a.f(a.B)  # wrong-arg-types[e]
      """, pythonpath=[d.path], deep=True)
      expected_error = ["Expected", "Type[a.A[int]]", "Actual", "Type[a.B]"]
      self.assertErrorSequences(errors, {"e": expected_error})

  def test_mro_error(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A: ...
        class B: ...
        class C(A, B): ...
        class D(B, A): ...
        class E(C, D): ...
      """)
      errors = self.CheckWithErrors("""
        import a
        x = a.E()  # mro-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"E"})

  def test_bad_mro(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(BaseException, ValueError): ...
      """)
      errors = self.CheckWithErrors("""
        import a
        class B(a.A): pass  # mro-error[e]
        raise a.A()
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"A"})

  def test_unsolvable_as_metaclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any: ...
      """)
      d.create_file("b.pyi", """
        from a import A
        class B(metaclass=A): ...
      """)
      errors = self.CheckWithErrors("""
        import b
        class C(b.B):
          def __init__(self):
            f = open(self.x, 'r')  # attribute-error[e]
      """, pythonpath=[d.path], deep=True)
      self.assertErrorRegexes(errors, {"e": r"x.*C"})

  def test_dont_timeout_on_complex(self):
    # Tests that we can solve a complex file without timing out.
    # Useful for catching large performance regressions.
    ty = self.Infer("""
      if __random__:
        x = [1]
      else:
        x = [1j]
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: Any
    """)

  def test_failed_function_call(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(x: str, y: int) -> bool: ...
        def f(x: str) -> bool: ...
      """)
      self.InferWithErrors("""
        import a
        x = a.f(0, "")  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_noncomputable_method(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        T = TypeVar("T")
        def copy(x: T) -> T: ...
      """)
      errors = self.CheckWithErrors("""
        import a
        class A:
          def __getattribute__(self, name):
            return a.copy(self)
        x = A()()  # not-callable[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"A"})

  def test_bad_type_name(self):
    errors = self.CheckWithErrors("""
      X = type(3, (int, object), {"a": 1})  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Actual.*int"})

  def test_bad_type_bases(self):
    errors = self.CheckWithErrors("""
      X = type("X", (42,), {"a": 1})  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(errors, {"e": ["Actual", "Tuple[int]"]})

  def test_half_bad_type_bases(self):
    errors = self.CheckWithErrors("""
      X = type("X", (42, object), {"a": 1})  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(
        errors, {"e": ["Actual", "Tuple[int, Type[object]]"]})

  def test_bad_type_members(self):
    errors = self.CheckWithErrors("""
      X = type("X", (int, object), {0: 1})  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(errors, {"e": ["Actual", "Dict[int, int]"]})

  def test_recursion(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(B): ...
        class B(A): ...
      """)
      ty, errors = self.InferWithErrors("""
        import a
        v = a.A()  # recursion-error[e]
        x = v.x  # No error because there is an Unsolvable in the MRO of a.A
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        from typing import Any
        v = ...  # type: a.A
        x = ...  # type: Any
      """)
      self.assertErrorRegexes(errors, {"e": r"a\.A"})

  def test_empty_union_or_optional(self):
    with test_utils.Tempdir() as d:
      d.create_file("f1.pyi", """
        def f(x: Union): ...
      """)
      d.create_file("f2.pyi", """
        def f(x: Optional): ...
      """)
      errors = self.CheckWithErrors("""
        import f1  # pyi-error[e1]
        import f2  # pyi-error[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e1": r"f1.*Union", "e2": r"f2.*Optional"})

  def test_bad_dict_attribute(self):
    errors = self.CheckWithErrors("""
      x = {"a": 1}
      y = x.a  # attribute-error[e]
    """)
    self.assertErrorSequences(errors, {"e": ["a", "Dict[str, int]"]})

  def test_bad_pyi_dict(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Dict
        x = ...  # type: Dict[str, int, float]
      """)
      errors = self.CheckWithErrors("""
        import a  # pyi-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"2.*3"})

  def test_call_none(self):
    self.InferWithErrors("""
      None()  # not-callable
    """)

  def test_in_none(self):
    self.InferWithErrors("""
      3 in None  # unsupported-operands
    """)

  def test_no_attr_error(self):
    self.InferWithErrors("""
      if __random__:
        y = 42
      else:
        y = "foo"
      y.upper  # attribute-error
    """)

  def test_attr_error(self):
    errors = self.CheckWithErrors("""
      if __random__:
        y = 42
      else:
        y = "foo"
      y.upper  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})

  def test_print_callable_instance(self):
    errors = self.CheckWithErrors("""
      from typing import Callable
      v = None  # type: Callable[[int], str]
      hex(v)  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(errors, {"e": ["Actual", "Callable[[int], str]"]})

  def test_same_name_and_line(self):
    errors = self.CheckWithErrors("""
      def f(x):
        return x + 42  # unsupported-operands[e1]  # unsupported-operands[e2]
      f("hello")
      f([])
    """)
    self.assertErrorRegexes(errors, {"e1": r"str.*int", "e2": r"List.*int"})

  def test_kwarg_order(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(*args, y, x, z: int): ...
        def g(x): ...
      """)
      errors = self.CheckWithErrors("""
        import foo
        foo.f(x=1, y=2, z="3")  # wrong-arg-types[e1]
        foo.g(42, v4="the", v3="quick", v2="brown", v1="fox")  # wrong-keyword-args[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(
          errors, {"e1": r"x, y, z.*x, y, z", "e2": r"v1, v2, v3, v4"})

  def test_bad_base_class(self):
    errors = self.CheckWithErrors("""
      class Foo(None): pass  # base-class-error[e]
    """)
    self.assertErrorSequences(errors, {"e": ["Invalid base class: None"]})

  @test_utils.skipFromPy((3, 10), "Pre-3.10: log one error for all bad options")
  def test_bad_ambiguous_base_class_pre310(self):
    errors = self.CheckWithErrors("""
      class Bar(None if __random__ else 42): pass  # base-class-error[e]
    """)
    self.assertErrorSequences(errors, {"e": ["Optional[<instance of int>]"]})

  @test_utils.skipBeforePy((3, 10), "3.10+: log one error per bad option")
  def test_bad_ambiguous_base_class(self):
    errors = self.CheckWithErrors("""
      class Bar(None if __random__ else 42): pass  # base-class-error[e1]  # base-class-error[e2]
    """)
    self.assertErrorSequences(errors, {
        "e1": ["Invalid base class: None"],
        "e2": ["Invalid base class: <instance of int>"]})

  def test_callable_in_unsupported_operands(self):
    errors = self.CheckWithErrors("""
      def f(x, y=None): pass
      f in f  # unsupported-operands[e]
    """)
    typ = "Callable[[Any, Any], Any]"
    self.assertErrorSequences(errors, {"e": [typ, typ]})

  def test_clean_pyi_namedtuple_names(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import NamedTuple
        X = NamedTuple("X", [])
        def f(x: int): ...
      """)
      errors = self.CheckWithErrors("""
        import foo
        foo.f(foo.X())  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo.X"})

  def test_bad_annotation(self):
    errors = self.CheckWithErrors("""
      list[0]  # not-indexable[e1]
      dict[1, 2]  # invalid-annotation[e2]  # invalid-annotation[e3]
      class A: pass
      A[3]  # not-indexable[e4]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"class list", "e2": r"1.*Not a type", "e3": r"2.*Not a type",
        "e4": r"class A"})

  def test_reveal_type(self):
    errors = self.CheckWithErrors("""
      class Foo:
        pass
      reveal_type(Foo)  # reveal-type[e1]
      reveal_type(Foo())  # reveal-type[e2]
      reveal_type([1,2,3])  # reveal-type[e3]
    """)
    self.assertErrorSequences(errors, {
        "e1": ["Type[Foo]"], "e2": ["Foo"], "e3": ["List[int]"]
    })

  def test_reveal_type_expression(self):
    errors = self.CheckWithErrors("""
      x = 42
      y = "foo"
      reveal_type(x or y)  # reveal-type[e]
    """)
    self.assertErrorSequences(errors, {"e": ["Union[int, str]"]})

  def test_not_protocol(self):
    errors = self.CheckWithErrors("""
      a = []
      a.append(1)
      a = "".join(a)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\(.*List\[int\]\)$"})  # no protocol details

  def test_protocol_signatures(self):
    errors = self.CheckWithErrors("""
      from typing import Sequence

      class Foo:
        def __len__(self):
          return 0
        def __getitem__(self, x: int) -> int:
          return 0

      def f(x: Sequence[int]):
        pass

      foo = Foo()
      f(foo)  # wrong-arg-types[e]
    """)
    expected = [
        ["Method __getitem__", "protocol Sequence[int]", "signature in Foo"],
        ["def __getitem__(self: Sequence"],
        ["def __getitem__(self, x: int)"]
    ]
    for pattern in expected:
      self.assertErrorSequences(errors, {"e": pattern})

  def test_hidden_error(self):
    self.CheckWithErrors("""
      use_option = False
      def f():
        if use_option:
          name_error  # name-error
    """)

  def test_unknown_in_error(self):
    errors = self.CheckWithErrors("""
      def f(x):
        y = x if __random__ else None
        return y.groups()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Optional\[Any\]"})


class OperationsTest(test_base.BaseTest):
  """Test operations."""

  def test_binary(self):
    errors = self.CheckWithErrors("""
      def f(): return 3 ** 'foo'  # unsupported-operands[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["**", "int", "str", "__pow__ on", "int"]})

  def test_unary(self):
    errors = self.CheckWithErrors("""
      def f(): return ~None  # unsupported-operands[e]
    """)
    self.assertErrorSequences(
        errors, {"e": ["~", "None", "'__invert__' on None"]})

  def test_op_and_right_op(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' ^ 3  # unsupported-operands[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["^", "str", "int", "'__xor__' on", "str", "'__rxor__' on", "int"]
    })

  def test_var_name_and_pyval(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' ^ 3  # unsupported-operands[e]
    """)
    self.assertErrorSequences(errors, {"e": ["^", "'foo': str", "3: int"]})


class InPlaceOperationsTest(test_base.BaseTest):
  """Test in-place operations."""

  def test_iadd(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; v += 3  # unsupported-operands[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["+=", "List", "int", "__iadd__ on List", "Iterable"]})


class NoSymbolOperationsTest(test_base.BaseTest):
  """Test operations with no native symbol."""

  def test_getitem(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; return v['foo']  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"item retrieval.*List.*str.*__getitem__ on List.*int"})

  def test_delitem(self):
    errors = self.CheckWithErrors("""
      def f(): v = {'foo': 3}; del v[3]  # unsupported-operands[e]
    """)
    d = "Dict[str, int]"
    self.assertErrorSequences(errors, {
        "e": ["item deletion", d, "int", f"__delitem__ on {d}", "str"]})

  def test_setitem(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; v['foo'] = 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"item assignment.*List.*str.*__setitem__ on List.*int"})

  def test_contains(self):
    errors = self.CheckWithErrors("""
      def f(): return 'foo' in 3  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"'in'.*int.*str.*'__contains__' on.*int"})

  def test_recursion(self):
    self.CheckWithErrors("""
      def f():
        if __random__:
          f()
          name_error  # name-error
    """)


if __name__ == "__main__":
  test_base.main()
