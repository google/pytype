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

  def test_callable_parameter_in_function(self):
    # Tests that we don't mis-identify the defaultdict call as a decorator.
    self.Check("""
      import collections
      class C:
        def __init__(self):
          self.x = collections.defaultdict(
              lambda key: key)  # pytype: disable=wrong-arg-types
    """)

  def test_async_for(self):
    self.Check("""
      class Client:
        async def get_or_create_tensorboard(self):
          response = await __any_object__
          async for page in response.pages:
            if page.tensorboards:
              return response.tensorboards[0].name
    """)

  def test_yield_from(self):
    self.Check("""
      def f():
        yield 1
        return 'a', 'b'
      def g():
        a, b = yield from f()
        assert_type(a, str)
        assert_type(b, str)
      for x in g():
        assert_type(x, int)
    """)

  def test_splat(self):
    self.Check("""
      def f(value, g):
        converted = []
        if isinstance(value, (dict, *tuple({}))):
          converted.append(value)
        return g(*converted)
    """)


if __name__ == "__main__":
  test_base.main()
