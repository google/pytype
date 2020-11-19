"""Tests for typing.py."""

from pytype import file_utils
from pytype.tests import test_base


class TypingTest(test_base.TargetIndependentTest):
  """Tests for typing.py."""

  def test_all(self):
    ty = self.Infer("""
      import typing
      x = typing.__all__
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      typing = ...  # type: module
      x = ...  # type: List[str]
    """)

  def test_cast1(self):
    # The return type of f should be List[int]. See b/33090435.
    ty = self.Infer("""
      import typing
      def f():
        return typing.cast(typing.List[int], [])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      typing = ...  # type: module
      def f() -> List[int]: ...
    """)

  def test_cast2(self):
    self.Check("""
      import typing
      foo = typing.cast(typing.Dict, {})
    """)

  def test_process_annotation_for_cast(self):
    ty, _ = self.InferWithErrors("""
      import typing
      v1 = typing.cast(None, __any_object__)
      v2 = typing.cast(typing.Union, __any_object__)  # invalid-annotation
      v3 = typing.cast("A", __any_object__)
      class A(object):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      typing: module
      v1: None
      v2: typing.Any
      v3: A
      class A(object): ...
    """)

  def test_no_typevars_for_cast(self):
    self.InferWithErrors("""
        from typing import cast, AnyStr, Type, TypeVar, _T, Union
        def f(x):
          return cast(AnyStr, x)  # invalid-typevar
        f("hello")
        def g(x):
          return cast(Union[AnyStr, _T], x)  # invalid-typevar
        g("quack")
        """)

  def test_cast_args(self):
    self.assertNoCrash(self.Check, """
      import typing
      typing.cast(typing.AnyStr)
      typing.cast("str")
      typing.cast()
      typing.cast(typ=typing.AnyStr, val=__any_object__)
      typing.cast(typ=str, val=__any_object__)
      typing.cast(typ="str", val=__any_object__)
      typing.cast(val=__any_object__)
      typing.cast(typing.List[typing.AnyStr], [])
      """)

  def test_generate_type_alias(self):
    ty = self.Infer("""
      from typing import List
      MyType = List[str]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      MyType = List[str]
    """)

  def test_protocol(self):
    self.Check("""
      from typing_extensions import Protocol
      class Foo(Protocol): pass
    """)

  def test_recursive_tuple(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class Foo(Tuple[Foo]): ...
      """)
      self.Check("""
        import foo
        foo.Foo()
      """, pythonpath=[d.path])

  def test_base_class(self):
    ty = self.Infer("""
      from typing import Iterable
      class Foo(Iterable):
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable
      class Foo(Iterable): ...
    """)

  def test_type_checking(self):
    self.Check("""
      import typing
      if typing.TYPE_CHECKING:
          pass
      else:
          name_error
    """)

  def test_not_type_checking(self):
    self.Check("""
      import typing
      if not typing.TYPE_CHECKING:
          name_error
      else:
          pass
    """)

  def test_new_type_arg_error(self):
    _, errors = self.InferWithErrors("""
      from typing import NewType
      MyInt = NewType(int, 'MyInt')  # wrong-arg-types[e1]
      MyStr = NewType(tp='str', name='MyStr')  # wrong-arg-types[e2]
      MyFunnyNameType = NewType(name=123 if __random__ else 'Abc', tp=int)  # wrong-arg-types[e3]
      MyFunnyType = NewType(name='Abc', tp=int if __random__ else 'int')  # wrong-arg-types[e4]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r".*Expected:.*str.*\nActually passed:.*Type\[int\].*",
        "e2": r".*Expected:.*type.*\nActually passed:.*str.*",
        "e3": r".*Expected:.*str.*\nActually passed:.*Union.*",
        "e4": r".*Expected:.*type.*\nActually passed:.*Union.*"})

  def test_classvar(self):
    ty = self.Infer("""
      from typing import ClassVar
      class A(object):
        x = 5  # type: ClassVar[int]
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x: int = ...
    """)

  def test_pyi_classvar(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import ClassVar
        class X:
          v: ClassVar[int]
      """)
      self.Check("""
        import foo
        foo.X.v + 42
      """, pythonpath=[d.path])

  def test_pyi_classvar_argcount(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import ClassVar
        class X:
          v: ClassVar[int, int]
      """)
      errors = self.CheckWithErrors("""
        import foo  # pyi-error[e]
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e": r"ClassVar.*1.*2"})

  def test_not_supported_yet(self):
    # Tests that typing_extension members not implemented in
    # typing_extensions_overlay are reported as [not-supported-yet]. If this
    # test starts failing due to this specific member gaining support, just pick
    # an unsupported member to replace it with from
    # https://github.com/python/typeshed/blob/master/third_party/2and3/typing_extensions.pyi
    self.CheckWithErrors("""
      from typing_extensions import TypedDict  # not-supported-yet
    """)

  def test_reuse_name(self):
    ty = self.Infer("""
      from typing import Sequence as Sequence_
      Sequence = Sequence_[int]
    """)
    self.assertTypesMatchPytd(ty, """
      import typing
      from typing import Any
      Sequence = typing.Sequence[int]
      Sequence_: Any
    """)


class LiteralTest(test_base.TargetIndependentTest):
  """Tests for typing.Literal."""

  def test_pyi_parameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        def f(x: Literal[True]) -> int: ...
        def f(x: Literal[False]) -> float: ...
        def f(x: bool) -> complex: ...
      """)
      ty = self.Infer("""
        import foo
        x = None  # type: bool
        v1 = foo.f(True)
        v2 = foo.f(False)
        v3 = foo.f(x)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo: module
        x: bool
        v1: int
        v2: float
        v3: complex
      """)

  def test_pyi_return(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        def okay() -> Literal[True]: ...
      """)
      ty = self.Infer("""
        import foo
        if not foo.okay():
          x = "oh no"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, "foo: module")

  def test_pyi_variable(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        OKAY: Literal[True]
      """)
      ty = self.Infer("""
        import foo
        if not foo.OKAY:
          x = "oh no"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, "foo: module")

  def test_pyi_typing_extensions(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing_extensions import Literal
        OKAY: Literal[True]
      """)
      ty = self.Infer("""
        import foo
        if not foo.OKAY:
          x = "oh no"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, "foo: module")

  # TODO(b/123775699): Include enums once we support looking up local enums.
  def test_pyi_value(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal

        def f1(x: Literal[True]) -> None: ...
        def f2(x: Literal[2]) -> None: ...
        def f3(x: Literal[None]) -> None: ...
        def f4(x: Literal['hello']) -> None: ...
        def f5(x: Literal[b'hello']) -> None: ...
        def f6(x: Literal[u'hello']) -> None: ...
      """)
      self.Check("""
        import foo
        foo.f1(True)
        foo.f2(2)
        foo.f3(None)
        foo.f4('hello')
        foo.f5(b'hello')
        foo.f6(u'hello')
      """, pythonpath=[d.path])

  def test_pyi_multiple(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        def f(x: Literal[False, None]) -> int: ...
        def f(x) -> str: ...
      """)
      ty = self.Infer("""
        import foo
        v1 = foo.f(False)
        v2 = foo.f(None)
        v3 = foo.f(True)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo: module
        v1: int
        v2: int
        v3: str
      """)

  def test_reexport(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        x: Literal[True]
        y: Literal[None]
      """)
      ty = self.Infer("""
        import foo
        x = foo.x
        y = foo.y
      """, pythonpath=[d.path])
      # TODO(b/123775699): The type of x should be Literal[True].
      self.assertTypesMatchPytd(ty, """
        foo: module
        x: bool
        y: None
      """)

  def test_string(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import IO, Literal
        def open(f: str, mode: Literal["r", "rt"]) -> str: ...
        def open(f: str, mode: Literal["rb"]) -> int: ...
      """)
      ty = self.Infer("""
        import foo
        def f1(f):
          return foo.open(f, mode="r")
        def f2(f):
          return foo.open(f, mode="rt")
        def f3(f):
          return foo.open(f, mode="rb")
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo: module
        def f1(f) -> str: ...
        def f2(f) -> str: ...
        def f3(f) -> int: ...
      """)

  def test_unknown(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        def f(x: Literal[True]) -> int: ...
        def f(x: Literal[False]) -> str: ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.f(__any_object__)
      """, pythonpath=[d.path])
      # Inference completing without type errors shows that `__any_object__`
      # matched both Literal[True] and Literal[False].
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo: module
        v: Any
      """)

  def test_literal_constant(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal, overload
        x: Literal["x"]
        y: Literal["y"]
        @overload
        def f(arg: Literal["x"]) -> int: ...
        @overload
        def f(arg: Literal["y"]) -> str: ...
      """)
      ty = self.Infer("""
        import foo
        def f1():
          return foo.f(foo.x)
        def f2():
          return foo.f(foo.y)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo: module
        def f1() -> int: ...
        def f2() -> str: ...
      """)


test_base.main(globals(), __name__ == "__main__")
