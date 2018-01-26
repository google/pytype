"""Tests for methods in six_overlay.py."""

from pytype import utils
from pytype.tests import test_base


class SixTests(test_base.BaseTest):
  """Tests for six and six_overlay."""

  def test_six_moves_import(self):
    self.Check("""
      import six
      def use_range():
        for x in six.moves.range(1, 10):
          print x
    """)

  def test_add_metaclass(self):
    """Like the test in test_abc but without a fake six.pyi."""
    with utils.Tempdir() as d:
      self.Check("""
        import abc
        import six
        @six.add_metaclass(abc.ABCMeta)
        class Foo(object):
          @abc.abstractmethod
          def foo(self):
            pass
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
