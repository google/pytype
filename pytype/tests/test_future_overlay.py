"""Tests for methods in six_overlay.py."""

from pytype import file_utils
from pytype.tests import test_base


class FutureUtilsTest(test_base.TargetIndependentTest):
  """Tests for future.utils and future_overlay."""

  @classmethod
  def setUpClass(cls):
    super(FutureUtilsTest, cls).setUpClass()
    cls._tempdir = file_utils.Tempdir().__enter__()
    cls._tempdir.create_file(
        "future/utils.pyi",
        "def with_metaclass(meta: type, *bases: type) -> type: ...")
    cls.pythonpaths = [cls._tempdir.path]

  @classmethod
  def tearDownClass(cls):
    cls.pythonpaths = None
    cls._tempdir.__exit__(None, None, None)
    cls._tempdir = None
    super(FutureUtilsTest, cls).tearDownClass()

  def test_with_metaclass(self):
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
    """, pythonpath=self.pythonpaths)


test_base.main(globals(), __name__ == "__main__")
