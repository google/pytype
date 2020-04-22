"""Tests for reloading generated pyi."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class ReingestTest(test_base.TargetPython27FeatureTest):
  """Tests for reloading the pyi we generate."""

  def test_instantiate_pyi_class(self):
    foo = self.Infer("""
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          pass
      class Bar(Foo):
        def foo(self):
          pass
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      _, errors = self.InferWithErrors("""
        import foo
        foo.Foo()  # not-instantiable[e]
        foo.Bar()
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.Foo.*foo"})


test_base.main(globals(), __name__ == "__main__")
