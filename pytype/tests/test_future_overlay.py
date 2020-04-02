"""Tests for methods in six_overlay.py."""

from pytype import file_utils
from pytype.tests import test_base


class FutureUtilsTest(test_base.TargetIndependentTest):
  """Tests for future.utils and future_overlay."""

  def test_with_metaclass(self):
    with file_utils.Tempdir() as d:
      d.create_file(
          "future/utils.pyi",
          "def with_metaclass(meta: type, *bases: type) -> type: ...")
      self.Check("""
          import abc
          from future.utils import with_metaclass
          class A(object):
            def __init__(self):
              self.foo = "hello"
          class B(object):
            def bar(self):
              return 42
          class Foo(with_metaclass(abc.ABCMeta, A), B):
            @abc.abstractmethod
            def get_foo(self):
              pass
          class Bar(Foo):
            def get_foo(self):
              return self.foo
          x = Bar().get_foo()
          y = Bar().bar()
      """, pythonpath=[d.path])

  def test_missing_import(self):
    self.CheckWithErrors("""
      from future.utils import iteritems  # import-error
      from future.utils import with_metaclass  # import-error
    """)


test_base.main(globals(), __name__ == "__main__")
