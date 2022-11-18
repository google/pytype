"""Tests for typing.py."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TypingTest(test_base.BaseTest):
  """Tests for typing.py."""

  def test_all(self):
    ty = self.Infer("""
      import typing
      x = typing.__all__
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      import typing
      from typing import List
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
      import typing
      from typing import Any, List
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
      class A:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      import typing
      v1: None
      v2: typing.Any
      v3: A
      class A: ...
    """)

  def test_no_typevars_for_cast(self):
    self.InferWithErrors("""
        from typing import cast, AnyStr, Type, TypeVar, _T, Union
        def f(x):
          return cast(AnyStr, x)  # invalid-annotation
        f("hello")
        def g(x):
          return cast(Union[AnyStr, _T], x)  # invalid-annotation
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
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class Foo(Tuple[Foo]): ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.Foo()[0]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        x: foo.Foo
      """)

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
      class A:
        x = 5  # type: ClassVar[int]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import ClassVar
      class A:
        x: ClassVar[int]
    """)

  def test_pyi_classvar(self):
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import ClassVar
        class X:
          v: ClassVar[int, int]
      """)
      errors = self.CheckWithErrors("""
        import foo  # pyi-error[e]
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e": r"ClassVar.*1.*2"})

  def test_reuse_name(self):
    ty = self.Infer("""
      from typing import Sequence as Sequence_
      Sequence = Sequence_[int]
    """)
    self.assertTypesMatchPytd(ty, """
      import typing
      from typing import Any
      Sequence = typing.Sequence[int]
      Sequence_: type
    """)

  def test_type_checking_local(self):
    self.Check("""
      from typing import TYPE_CHECKING
      def f():
        if not TYPE_CHECKING:
          name_error  # should be ignored
    """)


class LiteralTest(test_base.BaseTest):
  """Tests for typing.Literal."""

  def test_pyi_parameter(self):
    with test_utils.Tempdir() as d:
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
        import foo
        x: bool
        v1: int
        v2: float
        v3: complex
      """)

  def test_pyi_return(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        def okay() -> Literal[True]: ...
      """)
      ty = self.Infer("""
        import foo
        if not foo.okay():
          x = "oh no"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, "import foo")

  def test_pyi_variable(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        OKAY: Literal[True]
      """)
      ty = self.Infer("""
        import foo
        if not foo.OKAY:
          x = "oh no"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, "import foo")

  def test_pyi_typing_extensions(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing_extensions import Literal
        OKAY: Literal[True]
      """)
      ty = self.Infer("""
        import foo
        if not foo.OKAY:
          x = "oh no"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, "import foo")

  def test_pyi_value(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import enum
        from typing import Literal

        class Color(enum.Enum):
          RED: str

        def f1(x: Literal[True]) -> None: ...
        def f2(x: Literal[2]) -> None: ...
        def f3(x: Literal[None]) -> None: ...
        def f4(x: Literal['hello']) -> None: ...
        def f5(x: Literal[b'hello']) -> None: ...
        def f6(x: Literal[u'hello']) -> None: ...
        def f7(x: Literal[Color.RED]) -> None: ...
      """)
      self.Check("""
        import foo
        foo.f1(True)
        foo.f2(2)
        foo.f3(None)
        foo.f4('hello')
        foo.f5(b'hello')
        foo.f6(u'hello')
        foo.f7(foo.Color.RED)
      """, pythonpath=[d.path])

  def test_pyi_multiple(self):
    with test_utils.Tempdir() as d:
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
        import foo
        v1: int
        v2: int
        v3: str
      """)

  def test_reexport(self):
    with test_utils.Tempdir() as d:
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
        import foo
        x: bool
        y: None
      """)

  def test_string(self):
    with test_utils.Tempdir() as d:
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
        import foo
        def f1(f) -> str: ...
        def f2(f) -> str: ...
        def f3(f) -> int: ...
      """)

  def test_unknown(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any
        v: Any
      """)

  def test_literal_constant(self):
    with test_utils.Tempdir() as d:
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
        import foo
        def f1() -> int: ...
        def f2() -> str: ...
      """)

  def test_illegal_literal_class(self):
    # This should be a pyi-error, but checking happens during conversion.
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal
        class NotEnum:
          A: int
        x: Literal[NotEnum.A]
      """)
      self.CheckWithErrors("""
        import foo  # pyi-error
      """, pythonpath=[d.path])

  def test_illegal_literal_class_indirect(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class NotEnum:
          A: int
      """)
      d.create_file("bar.pyi", """
        from typing import Literal
        import foo
        y: Literal[foo.NotEnum.A]
      """)
      self.CheckWithErrors("""
        import bar  # pyi-error
      """, pythonpath=[d.path])

  def test_missing_enum_member(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import enum
        from typing import Literal
        class M(enum.Enum):
          A: int
        x: Literal[M.B]
      """)
      self.CheckWithErrors("""
        import foo  # pyi-error
      """, pythonpath=[d.path])

  def test_illegal_literal_typevar(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Literal, TypeVar
        T = TypeVar('T')
        x: Literal[T]
      """)
      self.CheckWithErrors("""
        import foo  # pyi-error
      """, pythonpath=[d.path])


class NotSupportedYetTest(test_base.BaseTest):
  """Tests for importing typing constructs only present in some Python versions.

  We want pytype to behave as follows:

  Is the construct supported by pytype?
  |
  -> No: Log a plain [not supported-yet] error.
  |
  -> Yes: Is the construct being imported from typing_extensions or typing?
     |
     -> typing_extensions: Do not log any errors.
     |
     -> typing: Is the construct present in the runtime typing module?
        |
        -> No: Log [not-supported-yet] with a hint to use typing_extensions.
        |
        -> Yes: Do not log any errors.

  These tests currently use Self (added in 3.11) as the unsupported
  construct and Final (added in 3.8) as the supported construct. Replace them as
  needed as pytype's supported features and runtime versions change.
  """

  def test_unsupported_extension(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Self  # not-supported-yet[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"typing.Self not supported yet$"})

  def test_unsupported_construct(self):
    errors = self.CheckWithErrors("""
      from typing import Self  # not-supported-yet[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"typing.Self not supported yet$"})

  def test_supported_extension(self):
    self.Check("""
      from typing_extensions import Final
    """)

  @test_utils.skipFromPy((3, 8), "Final is added to typing in 3.8")
  def test_supported_construct_in_unsupported_version(self):
    errors = self.CheckWithErrors("""
      from typing import Final  # not-supported-yet[e]
    """)
    self.assertErrorSequences(
        errors, {"e": ["Import Final from typing_extensions", "before 3.8"]})

  @test_utils.skipBeforePy((3, 8), "Final is added to typing in Python 3.8")
  def test_supported_construct_in_supported_version(self):
    self.Check("""
      from typing import Final
    """)


if __name__ == "__main__":
  test_base.main()
