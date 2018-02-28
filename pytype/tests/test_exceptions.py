"""Test exceptions for Byterun."""


from pytype import utils
from pytype.tests import test_base


class TestExceptions(test_base.BaseTest):
  """Exception tests."""

  def test_catching_exceptions(self):
    # TODO(kramm): Don't warn about NameErrors that are being caught.
    # Catch the exception precisely
    self.assertNoCrash(self.Check, """\
      try:
        x[1]
        print("Shouldn't be here...")
      except NameError:
        print("caught it!")
      """)
    # Catch the exception by a parent class
    self.assertNoCrash(self.Check, """\
      try:
        x[1]
        print("Shouldn't be here...")
      except Exception:
        print("caught it!")
      """)
    # Catch all exceptions
    self.assertNoCrash(self.Check, """\
      try:
        x[1]
        print("Shouldn't be here...")
      except:
        print("caught it!")
      """)

  def test_raise_exception(self):
    self.Check("raise Exception('oops')")

  def test_raise_exception_class(self):
    self.Check("raise ValueError")

  def test_raise_exception_2args(self):
    self.Check("raise ValueError, 'bad'")

  def test_raise_exception_3args(self):
    self.Check("""\
      from sys import exc_info
      try:
        raise Exception
      except:
        _, _, tb = exc_info()
      raise ValueError, "message", tb
      """)

  def test_raise_and_catch_exception(self):
    self.Check("""\
      try:
        raise ValueError("oops")
      except ValueError as e:
        print("Caught: %s" % e)
      print("All done")
      """)

  def test_raise_and_catch_exception_in_function(self):
    self.Check("""\
      def fn():
        raise ValueError("oops")

      try:
        fn()
      except ValueError as e:
        print("Caught: %s" % e)
      print("done")
      """)

  def test_global_name_error(self):
    errors = self.CheckWithErrors("fooey")
    self.assertErrorLogIs(errors, [(1, "name-error", r"fooey")])
    # TODO(kramm): Don't warn about NameErrors that are being caught.
    self.assertNoCrash(self.Check, """\
      try:
        fooey
        print("Yes fooey?")
      except NameError:
        print("No fooey")
    """)

  def test_local_name_error(self):
    errors = self.CheckWithErrors("""\
      def fn():
        fooey
      fn()
    """)
    self.assertErrorLogIs(errors, [(2, "name-error", r"fooey")])

  def test_catch_local_name_error(self):
    self.assertNoCrash(self.Check, """\
      def fn():
        try:
          fooey
          print("Yes fooey?")
        except NameError:
          print("No fooey")
      fn()
      """)

  def test_reraise(self):
    errors = self.CheckWithErrors("""\
      def fn():
        try:
          fooey
          print("Yes fooey?")
        except NameError:
          print("No fooey")
          raise
      fn()
    """)
    self.assertErrorLogIs(errors, [(3, "name-error", r"fooey")])

  def test_reraise_explicit_exception(self):
    self.Check("""\
      def fn():
        try:
          raise ValueError("ouch")
        except ValueError as e:
          print("Caught %s" % e)
          raise
      fn()
    """)

  def test_reraise_py3(self):
    # Test that we don't crash when trying to reraise a nonexistent exception.
    # (Causes a runtime error when actually run in python 3.6)
    self.assertNoCrash(self.Check, """
      raise
    """, python_version=(3, 6))

  def test_finally_while_throwing(self):
    self.Check("""\
      def fn():
        try:
          print("About to..")
          raise ValueError("ouch")
        finally:
          print("Finally")
      fn()
      print("Done")
    """)

  def test_coverage_issue_92(self):
    self.Check("""\
      l = []
      for i in range(3):
        try:
          l.append(i)
        finally:
          l.append('f')
        l.append('e')
      l.append('r')
      print(l)
      assert l == [0, 'f', 'e', 1, 'f', 'e', 2, 'f', 'e', 'r']
      """)

  def test_continue_in_except(self):
    self.Check("""\
      for i in range(3):
        try:
          pass
        except:
          print i
          continue
        print 'e'
      """)

  def test_loop_finally_except(self):
    self.Check("""
      def f():
        for s in (1, 2):
          try:
            try:
              break
            except:
              continue
          finally:
            pass
      """)

  def test_inherit_from_exception(self):
    ty = self.Infer("""
      class Foo(Exception):
        pass

      def bar(x):
        return Foo(x)
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(Exception):
        pass

      def bar(x) -> Foo
    """)

  def test_match_exception_type(self):
    with utils.Tempdir() as d:
      d.create_file("warnings.pyi", """
        from typing import Optional, Type, Union
        def warn(message: Union[str, Warning],
                 category: Optional[Type[Warning]] = ...,
                 stacklevel: int = ...) -> None: ...
      """)
      ty = self.Infer("""
        import warnings
        def warn():
          warnings.warn(
            "set_prefix() is deprecated; use the prefix property",
            DeprecationWarning, stacklevel=2)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        warnings = ...  # type: module
        def warn() -> None
      """)

  def test_end_finally(self):
    ty = self.Infer("""
      def foo():
        try:
          assert True
          return 42
        except Exception:
          return 42
    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> int
    """)

  def test_dead_except_block(self):
    ty = self.Infer("""
      def foo():
        try:
          return 42
        except Exception:
          return 1+3j
    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> int
    """)

  def test_assert(self):
    ty = self.Infer("""
      def foo():
        try:
          assert True
          return 42
        except:
          return 1+3j
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union

      def foo() -> Union[complex, int]
    """)

  def test_no_return(self):
    ty = self.Infer("""
      def f():
        raise ValueError()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn
      def f() -> NoReturn
    """)

  def test_reraise_no_return(self):
    ty = self.Infer("""
      import sys
      def f():
        try:
          raise ValueError()
        except:
          exc_info = sys.exc_info()
          raise exc_info[0], exc_info[1], exc_info[2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn
      sys = ...  # type: module
      def f() -> NoReturn
    """)

  def test_no_return_chain(self):
    ty = self.Infer("""
      def f():
        raise ValueError()
      def g():
        f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn
      def f() -> NoReturn
      def g() -> NoReturn
    """)

  def test_return_or_raise(self):
    ty = self.Infer("""
      def f():
        if __random__:
          return 42
        else:
          raise ValueError()
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int
    """)

  def test_return_or_call(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import NoReturn
      def f() -> NoReturn:
        raise ValueError()
      def g():
        if __random__:
          return f()
        else:
          return 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn
      def f() -> NoReturn: ...
      def g() -> int
    """)

  def test_combine_noreturn(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import NoReturn
      def f1() -> NoReturn:
        raise ValueError()
      def f2() -> int:
        return 42
      g1 = f1 if __random__ else f2
      def g2():
        return f1 if __random__ else f2
      v1 = g1()
      v2 = g2()()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, NoReturn
      def f1() -> NoReturn: ...
      def f2() -> int: ...
      def g1() -> int: ...
      def g2() -> Callable[[], int]: ...
      v1 = ...  # type: int
      v2 = ...  # type: int
    """)

  def test_combine_noreturn_different_argcount(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import NoReturn
      def f1(x) -> NoReturn:
        raise x
      def f2() -> int:
        return 42
      g1 = f1 if __random__ else f2
      def g2():
        return f1 if __random__ else f2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, NoReturn
      def f1(x) -> NoReturn: ...
      def f2() -> int: ...
      @overload
      def g1(x) -> NoReturn: ...
      @overload
      def g1() -> int: ...
      def g2() -> Callable[..., int]: ...
    """)

  def test_noreturn_callable(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import NoReturn
      def f() -> NoReturn:
        raise ValueError()
      def g():
        return f
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, NoReturn
      def f() -> NoReturn
      def g() -> Callable[[], nothing]
    """)

  def test_type_self(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, _):  # Add an arg so __init__ isn't optimized away.
          if type(self) is Foo:
            raise ValueError()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __init__(self, _) -> None: ...
    """)

  def test_bad_type_self(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def __init__(self):
          type(42, self)
    """)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-count", r"2.*3")])


if __name__ == "__main__":
  test_base.main()
