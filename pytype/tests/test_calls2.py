"""Tests for python3 function call features."""

from pytype.tests import test_base


class TestCalls(test_base.BaseTest):
  """Tests for checking function calls."""

  def test_starstarargs_with_kwonly(self):
    """Args defined as kwonly should be removed from **kwargs."""
    self.Check("""
      def f(a):
        return a
      def g(*args, kw=False, **kwargs):
        # When called from h, **kwargs should not include `kw=True`
        return f(*args, **kwargs)
      def h():
        return g(1, kw=True)
    """)


if __name__ == "__main__":
  test_base.main()
