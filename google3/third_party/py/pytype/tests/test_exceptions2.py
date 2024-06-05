"""Test exceptions."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestExceptionsPy3(test_base.BaseTest):
  """Exception tests."""

  def test_reraise(self):
    # Test that we don't crash when trying to reraise a nonexistent exception.
    # (Causes a runtime error when actually run)
    self.assertNoCrash(self.Check, """
      raise
    """)

  def test_raise_exception_from(self):
    self.Check("raise ValueError from NameError")

  def test_exception_message(self):
    # This attribute was removed in Python 3.
    self.CheckWithErrors("ValueError().message  # attribute-error")

  def test_suppress_context(self):
    self.Check("ValueError().__suppress_context__")

  def test_return_or_call_to_raise(self):
    ty = self.Infer("""
      from typing import NoReturn
      def e() -> NoReturn:
        raise ValueError('this is an error')
      def f():
        if __random__:
          return 16
        else:
          e()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Never

      def e() -> Never: ...
      def f() -> int: ...
    """)

  def test_union(self):
    self.Check("""
      from typing import Type, Union
      class Foo:
        @property
        def exception_types(self) -> Type[Union[ValueError, IndexError]]:
          return ValueError
      def f(x: Foo):
        try:
          pass
        except x.exception_types as e:
          return e
    """)

  def test_bad_union(self):
    errors = self.CheckWithErrors("""
      from typing import Type, Optional
      class Foo:
        @property
        def exception_types(self) -> Type[Optional[ValueError]]:
          return ValueError
      def f(x: Foo):
        try:
          print(x)
        except x.exception_types as e:  # mro-error[e]
          return e
    """)
    self.assertErrorRegexes(
        errors, {"e": "NoneType does not inherit from BaseException"})

  @test_utils.skipIfPy(
      (3, 8), reason="failing, not worth fixing since this works again in 3.9")
  def test_no_return_in_finally(self):
    # Tests that pytype is okay with the finally block not returning anything.
    self.Check("""
      import array
      import os
      def f(fd) -> int:
        try:
          buf = array.array("l", [0])
          return buf[0]
        except (IOError, OSError):
          return 0
        finally:
          os.close(fd)
    """)

  def test_contextmanager(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __enter__(self):
          return self
        def __exit__(self, exc_type, exc_value, tb):
          reveal_type(exc_type)  # reveal-type[e]
          return False
      with Foo():
        print(0)
    """)
    self.assertErrorSequences(errors, {"e": ["Optional[Type[BaseException]]"]})

  def test_yield_from(self):
    self.Check("""
      def f():
        yield from g()
      def g():
        try:
          __any_object__()
        except Exception as e:
          print(any(s in str(e) for s in 'abcde'))
        yield None
    """)

  def test_raise_exc_info(self):
    self.Check("""
      import sys
      exception = sys.exc_info()
      exception_type = exception[0]
      if exception_type:
        raise exception_type()
    """)


if __name__ == "__main__":
  test_base.main()
