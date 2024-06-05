"""Test exceptions."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestExceptions(test_base.BaseTest):
  """Exception tests."""

  def test_exceptions(self):
    ty = self.Infer("""
      def f():
        try:
          raise ValueError()  # exercise byte_RAISE_VARARGS
        except ValueError as e:
          x = "s"
        finally:  # exercise byte_POP_EXCEPT
          x = 3
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_catching_exceptions(self):
    self.assertNoCrash(self.Check, """
      try:
        x[1]
        print("Shouldn't be here...")
      except NameError:
        print("caught it!")
      """)
    # Catch the exception by a base class
    self.assertNoCrash(self.Check, """
      try:
        x[1]
        print("Shouldn't be here...")
      except Exception:
        print("caught it!")
      """)
    # Catch all exceptions
    self.assertNoCrash(self.Check, """
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

  def test_raise_and_catch_exception(self):
    self.Check("""
      try:
        raise ValueError("oops")
      except ValueError as e:
        print("Caught: %s" % e)
      print("All done")
      """)

  def test_raise_and_catch_exception_in_function(self):
    self.Check("""
      def fn():
        raise ValueError("oops")

      try:
        fn()
      except ValueError as e:
        print("Caught: %s" % e)
      print("done")
      """)

  def test_global_name_error(self):
    self.CheckWithErrors("fooey  # name-error")
    # TODO(b/159068542): Don't warn about NameErrors that are being caught.
    self.assertNoCrash(self.Check, """
      try:
        fooey
        print("Yes fooey?")
      except NameError:
        print("No fooey")
    """)

  def test_local_name_error(self):
    self.CheckWithErrors("""
      def fn():
        fooey  # name-error
      fn()
    """)

  def test_catch_local_name_error(self):
    self.assertNoCrash(self.Check, """
      def fn():
        try:
          fooey
          print("Yes fooey?")
        except NameError:
          print("No fooey")
      fn()
      """)

  def test_reraise(self):
    self.CheckWithErrors("""
      def fn():
        try:
          fooey  # name-error
          print("Yes fooey?")
        except NameError:
          print("No fooey")
          raise
      fn()
    """)

  def test_reraise_explicit_exception(self):
    self.Check("""
      def fn():
        try:
          raise ValueError("ouch")
        except ValueError as e:
          print("Caught %s" % e)
          raise
      fn()
    """)

  def test_reraise_in_function_call(self):
    self.Check("""
      def raise_error(e):
        raise(e)

      def f():
        try:
          return "hello"
        except Exception as e:
          raise_error(e)

      f().lower()  # f() should be str, not str|None
    """)

  def test_finally_while_throwing(self):
    self.Check("""
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
    self.Check("""
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
    self.Check("""
      for i in range(3):
        try:
          pass
        except:
          print(i)
          continue
        print('e')
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

      def bar(x) -> Foo: ...
    """)

  def test_match_exception_type(self):
    with test_utils.Tempdir() as d:
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
        import warnings
        def warn() -> None: ...
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
      def foo() -> int: ...
    """)

  @test_utils.skipFromPy(
      (3, 11), reason="Code gets eliminated very early, not worth fixing")
  def test_dont_eliminate_except_block(self):
    # Testing for dead code is imprecise, so do not do it at all unless we add
    # special cases for code analysis within try blocks.
    ty = self.Infer("""
      def foo():
        try:
          return 42
        except Exception:
          return 1+3j
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo() -> Union[int, complex]: ...
    """)

  @test_utils.skipBeforePy((3, 11), reason="New behaviour in 3.11")
  def test_eliminate_except_block(self):
    # The dead except block gets eliminated in 3.11
    ty = self.Infer("""
      def foo():
        try:
          return 42
        except Exception:
          return 1+3j
    """)
    self.assertTypesMatchPytd(ty, """
      def foo() -> int: ...
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

      def foo() -> Union[complex, int]: ...
    """)

  def test_never(self):
    ty = self.Infer("""
      def f():
        raise ValueError()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Never
      def f() -> Never: ...
    """)

  def test_never_chain(self):
    ty = self.Infer("""
      def f():
        raise ValueError()
      def g():
        f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Never
      def f() -> Never: ...
      def g() -> Never: ...
    """)

  def test_try_except_never(self):
    ty = self.Infer("""
      def f():
        try:
          raise ValueError()
        except ValueError as e:
          raise ValueError(str(e))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Never
      def f() -> Never: ...
    """)

  def test_callable_noreturn(self):
    self.Check("""
      from typing import Callable, NoReturn
      def f(x: Callable[[], NoReturn]) -> NoReturn:
        x()
    """)

  def test_callable_noreturn_branch(self):
    self.Check("""
      from typing import Callable, NoReturn
      def f(x: Callable[[], NoReturn], y: int) -> int:
        if y % 2:
          return y
        else:
          x()
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
      def f() -> int: ...
    """)

  def test_return_or_raise_set_attribute(self):
    self.CheckWithErrors("""
      def f():
        raise ValueError()
      def g():
        return ""
      def h():
        func = f if __random__ else g
        v = func()
        v.attr = None  # not-writable
    """)

  def test_bad_type_self(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __init__(self):
          type(42, self)  # wrong-arg-count[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"2.*3"})

  def test_value(self):
    ty = self.Infer("""
      def f():
        try:
          raise KeyError()
        except KeyError as e:
          return e
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> KeyError: ...
    """)

  def test_value_from_tuple(self):
    ty = self.Infer("""
      from typing import Tuple, Type
      def f():
        try:
          raise KeyError()
        except (KeyError, ValueError) as e:
          return e
      def g():
        try:
          raise KeyError()
        except ((KeyError,),) as e:
          return e
      def h():
        tup = None  # type: Tuple[Type[KeyError], ...]
        try:
          raise KeyError()
        except tup as e:
          return e
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f() -> Union[KeyError, ValueError]: ...
      def g() -> KeyError: ...
      def h() -> KeyError: ...
    """)

  def test_bad_type(self):
    errors = self.CheckWithErrors("""
      try:
        x = 1
      except None:  # mro-error[e1]
        pass
      try:
        x = 2
      except type(None):  # mro-error[e2]
        pass
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Not a class", "e2": r"None.*BaseException"})

  def test_unknown_type(self):
    self.Check("""
      try:
        pass
      except __any_object__:
        pass
    """)

  def test_attribute(self):
    ty = self.Infer("""
      class MyException(BaseException):
        def __init__(self):
          self.x = ""
      def f():
        try:
          raise MyException()
        except MyException as e:
          return e.x
    """)
    self.assertTypesMatchPytd(ty, """
      class MyException(BaseException):
        x: str
        def __init__(self) -> None: ...
      def f() -> str: ...
    """)

  def test_reuse_name(self):
    self.Check("""
      def f():
        try:
          pass
        except __any_object__ as e:
          return e
        try:
          pass
        except __any_object__ as e:
          return e
    """)

  def test_unknown_base(self):
    self.Check("""
      class MyException(__any_object__):
        pass
      try:
        pass
      except MyException:
        pass
    """)

  def test_contextmanager(self):
    # Tests that the with block doesn't get mistaken for an exception.
    ty = self.Infer("""
      _temporaries = {}
      def f(name):
        with __any_object__:
          filename = _temporaries.get(name)
          (filename, data) = __any_object__
          if not filename:
            assert data is not None
        return filename
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      _temporaries: Dict[nothing, nothing]
      def f(name) -> Any: ...
    """)

  def test_no_except(self):
    # Tests inference for a finally block without an except.
    ty = self.Infer("""
      def f():
        try:
          if __random__:
            raise ValueError()
        finally:
          __any_object__()
        return 0
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_traceback(self):
    # Check that with_traceback() preserves the exception type.
    self.Check("""
      class Foo(Exception):
        pass
      x = Foo().with_traceback(None)
      assert_type(x, Foo)
    """)


if __name__ == "__main__":
  test_base.main()
