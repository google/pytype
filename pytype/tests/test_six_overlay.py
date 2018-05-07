"""Tests for methods in six_overlay.py."""

from pytype.tests import test_base


class SixTests(test_base.TargetIndependentTest):
  """Tests for six and six_overlay."""

  def test_six_moves_import(self):
    self.Check("""
      import six
      def use_range():
        for x in six.moves.range(1, 10):
          x
    """)

  def test_add_metaclass(self):
    """Like the test in test_abc but without a fake six.pyi."""
    self.Check("""
      import abc
      import six
      class A(object):
        def __init__(self):
          self.foo = "hello"
      @six.add_metaclass(abc.ABCMeta)
      class Foo(A):
        @abc.abstractmethod
        def get_foo(self):
          pass
      class Bar(Foo):
        def get_foo(self):
          return self.foo
      x = Bar().get_foo()
    """)

  def test_with_metaclass(self):
    self.Check("""
      import abc
      import six
      class A(object):
        def __init__(self):
          self.foo = "hello"
      class B(object):
        def bar(self):
          return 42
      class Foo(six.with_metaclass(abc.ABCMeta, A), B):
        @abc.abstractmethod
        def get_foo(self):
          pass
      class Bar(Foo):
        def get_foo(self):
          return self.foo
      x = Bar().get_foo()
      y = Bar().bar()
    """)


if __name__ == "__main__":
  test_base.main()
