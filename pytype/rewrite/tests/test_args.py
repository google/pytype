"""Tests for function call arguments."""

from pytype.rewrite.tests import test_utils
from pytype.tests import test_base


class RewriteTest(test_base.BaseTest):

  def setUp(self):
    super().setUp()
    self.options.tweak(use_rewrite=True)


class FunctionCallTest(RewriteTest):
  """Basic function call tests."""

  def test_function_parameter(self):
    self.Check("""
      def f(x):
        return x
      f(0)
    """)

  @test_utils.skipBeforePy((3, 11), 'Relies on 3.11+ bytecode')
  def test_function_kwargs(self):
    self.Check("""
      def f(x, *, y):
        return x
      f(0, y=1)
    """)

  @test_utils.skipBeforePy((3, 11), 'Relies on 3.11+ bytecode')
  def test_function_varargs(self):
    self.Check("""
      def foo(x: str, *args):
        pass
      def bar(*args):
        foo('abc', *args)
    """)

  def test_function_only_varargs(self):
    self.Check("""
      def foo(*args):
        pass
      def bar(*args):
        foo(*args)
    """)

  def test_capture_varargs(self):
    self.Check("""
      def f(*args, **kwargs):
        g(args, kwargs)
      def g(x, y):
        pass
      a = (1, 2)
      b = {'x': 1, 'y': 2}
      f(*a, **b)
    """)

  def test_forward_varargs(self):
    self.Check("""
      def f(*args, **kwargs):
        g(*args, **kwargs)
      def g(a, b, x, y):
        pass
      a = (1, 2)
      b = {'x': 1, 'y': 2}
      f(*a, **b)
    """)

  @test_base.skip('Does not yet work with fake args.')
  def test_unpack_posargs(self):
    self.Check("""
      def f(x, y, z):
        g(*x, *y, *z)

      def g(*args):
        h(*args)

      def h(p, q, r, s, t, u):
        return u

      ret = f((1, 2), (3, 4), (5, 6))
      assert_type(ret, int)
    """)


if __name__ == '__main__':
  test_base.main()
