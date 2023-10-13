"""Tests for control flow cases that involve the exception table in 3.11+.

Python 3.11 changed the way exceptions and some other control structures were
compiled, and in particular some of them require examining the exception table
as well as the bytecode.
"""

from pytype.tests import test_base


class TestPy311(test_base.BaseTest):
  """Tests for python 3.11 support."""

  def test_context_manager(self):
    self.Check("""
      class A:
        def __enter__(self):
          pass
        def __exit__(self, a, b, c):
          pass

      lock = A()

      def f() -> str:
        path = ''
        with lock:
          try:
            pass
          except:
            pass
          return path
    """)

  def test_exception_type(self):
    self.Check("""
      class FooError(Exception):
        pass
      try:
        raise FooError()
      except FooError as e:
        assert_type(e, FooError)
    """)

  def test_try_with(self):
    self.Check("""
      def f(obj, x):
        try:
          with __any_object__:
            obj.get(x)
        except:
          pass
    """)

  def test_try_if_with(self):
    self.Check("""
      from typing import Any
      import os
      pytz: Any
      def f():
        tz_env = os.environ.get('TZ')
        try:
          if tz_env == 'localtime':
            with open('localtime') as localtime:
              return pytz.tzfile.build_tzinfo('', localtime)
        except IOError:
          return pytz.UTC
    """)

  def test_try_finally(self):
    self.Check("""
      import tempfile
      dir_ = None
      def f():
        global dir_
        try:
          if dir_:
            return dir_
          dir_ = tempfile.mkdtemp()
        finally:
          print(dir_)
    """)

  def test_nested_try_in_for(self):
    self.Check("""
      def f(x):
        for i in x:
          fd = __any_object__
          try:
            try:
              if __random__:
                return True
            except ValueError:
              continue
          finally:
            fd.close()
    """)

  def test_while_and_nested_try(self):
    self.Check("""
      def f(p):
        try:
          while __random__:
            try:
              return p.communicate()
            except KeyboardInterrupt:
              pass
        finally:
          pass
    """)

  def test_while_and_nested_try_2(self):
    self.Check("""
      def f():
        i = j = 0
        while True:
          try:
            try:
              i += 1
            finally:
              j += 1
          except:
            break
        return
    """)

  def test_while_and_nested_try_3(self):
    self.Check("""
      import os

      def RmDirs(dir_name):
        try:
          parent_directory = os.path.dirname(dir_name)
          while parent_directory:
            try:
              os.rmdir(parent_directory)
            except OSError as err:
              pass
            parent_directory = os.path.dirname(parent_directory)
        except OSError as err:
          pass
    """)


if __name__ == "__main__":
  test_base.main()
