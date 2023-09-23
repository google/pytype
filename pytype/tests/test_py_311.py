"""Tests for 3.11 support.

These tests are separated into their own file because the main test suite
doesn't pass under python 3.11 yet; this lets us tests individual features as we
get them working.
"""

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy((3, 11), "Tests specifically for 3.11 support")
class TestPy311(test_base.BaseTest):
  """Tests for python 3.11 support."""

  def test_binop(self):
    self.Check("""
      def f(x: int | str):
        pass

      def g(x: int, y: int) -> int:
        return x & y

      def h(x: int, y: int):
        x ^= y
    """)

  def test_method_call(self):
    self.Check("""
      class A:
        def f(self):
          return 42

      x = A().f()
      assert_type(x, int)
    """)

  def test_global_call(self):
    self.Check("""
      def f(x):
        return any(x)
    """)

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

  def test_deref1(self):
    self.Check("""
      def f(*args):
        def rmdirs(
            unlink,
            dirname,
            removedirs,
            enoent_error,
            directory,
            files,
        ):
          for path in [dirname(f) for f in files]:
            removedirs(path, directory)
        rmdirs(*args)
    """)

  def test_deref2(self):
    self.Check("""
      def f(x):
        y = x
        x = lambda: y

        def g():
          return x
    """)

  def test_super(self):
    self.Check("""
      class A:
        def __init__(self):
          super(A, self).__init__()
    """)

  def test_call_function_ex(self):
    self.Check("""
      import datetime
      def f(*args):
        return g(datetime.datetime(*args), 10)
      def g(x, y):
        return (x, y)
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


if __name__ == "__main__":
  test_base.main()
