"""Tests for typing.py."""

from pytype import utils
from pytype.pytd import pep484
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
      def f() -> List[int]
    """)

  def test_cast2(self):
    self.Check("""
      import typing
      foo = typing.cast(typing.Dict, {})
    """)

  def test_process_annotation_for_cast(self):
    ty, errors = self.InferWithErrors("""\
      import typing
      v1 = typing.cast(None, __any_object__)
      v2 = typing.cast(typing.Union, __any_object__)
      v3 = typing.cast("A", __any_object__)
      class A(object):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      typing = ...  # type: module
      v1 = ...  # type: None
      v2 = ...  # type: typing.Any
      v3 = ...  # type: typing.Any
      class A(object): ...
    """)
    self.assertErrorLogIs(errors, [(3, "invalid-annotation"),
                                   (4, "invalid-annotation")])

  def test_no_typevars_for_cast(self):
    _, errors = self.InferWithErrors("""\
        from typing import cast, AnyStr, Type, TypeVar, _T
        def f(x):
          return cast(AnyStr, x)
        f("hello")
        def g(x):
          return cast(AnyStr if __random__ else int, x)
        g("quack")
        """)
    self.assertErrorLogIs(errors,
                          [(3, "invalid-typevar"),
                           (6, "invalid-typevar")])

  def test_cast_args(self):
    self.assertNoCrash(self.Check, """\
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
    self.Check("""\
      from typing import Protocol
      class Foo(Protocol): pass
    """)

  def test_import_all(self):
    python = [
        "from typing import *  # pytype: disable=not-supported-yet",
    ] + pep484.PEP484_NAMES
    ty = self.Infer("\n".join(python), deep=False)
    self.assertTypesMatchPytd(ty, "")

  def test_recursive_tuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class Foo(Tuple[Foo]): ...
      """)
      self.Check("""\
        import foo
        foo.Foo()
      """, pythonpath=[d.path])

  def test_base_class(self):
    ty = self.Infer("""\
      from typing import Iterable
      class Foo(Iterable):
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterable
      class Foo(Iterable): ...
    """)

  def test_type_checking(self):
    self.Check("""\
      import typing
      if typing.TYPE_CHECKING:
          pass
      else:
          name_error
    """)

  def test_not_type_checking(self):
    self.Check("""\
      import typing
      if not typing.TYPE_CHECKING:
          name_error
      else:
          pass
    """)

  def test_new_type_arg_error(self):
    _, errors = self.InferWithErrors("""
      from typing import NewType
      MyInt = NewType(int, 'MyInt')
      MyStr = NewType(tp='str', name='MyStr')
      MyFunnyNameType = NewType(name=123 if __random__ else 'Abc', tp=int)
      MyFunnyType = NewType(name='Abc', tp=int if __random__ else 'int')
    """)
    self.assertErrorLogIs(
        errors,
        [(3, "wrong-arg-types",
          r".*Expected:.*str.*\nActually passed:.*Type\[int\].*"),
         (4, "wrong-arg-types",
          r".*Expected:.*type.*\nActually passed:.*str.*"),
         (5, "wrong-arg-types",
          r".*Expected:.*str.*\nActually passed:.*Union.*"),
         (6, "wrong-arg-types",
          r".*Expected:.*type.*\nActually passed:.*Union.*"),])

  def test_classvar(self):
    errors = self.CheckWithErrors("from typing import ClassVar")
    self.assertErrorLogIs(
        errors, [(1, "not-supported-yet", r"typing.ClassVar")])

  def test_pyi_classvar(self):
    with utils.Tempdir() as d:
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
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import ClassVar
        class X:
          v: ClassVar[int, int]
      """)
      errors = self.CheckWithErrors("""\
        import foo
      """, pythonpath=[d.path])
    self.assertErrorLogIs(errors, [(1, "pyi-error", r"ClassVar.*1.*2")])


test_base.main(globals(), __name__ == "__main__")
