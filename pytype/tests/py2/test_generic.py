"""Tests for handling GenericType."""

from pytype import file_utils
from pytype.tests import test_base


class GenericFeatureTest(test_base.TargetPython27FeatureTest):
  """Tests for User-defined Generic Type."""

  def test_type_parameter_duplicated(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Dict, TypeVar
        T = TypeVar("T")
        class A(Dict[T, T], Generic[T]): pass
      """)
      ty = self.Infer("""
        import a
        def f():
          x = a.A()
          x[1] = 2
          return x

        d = None  # type: a.A[int]
        ks, vs = d.keys(), d.values()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        from typing import List

        a = ...  # type: module
        d = ...  # type: a.A[int]
        ks = ...  # type: List[int]
        vs = ...  # type: List[int]

        def f() -> a.A[int]: ...
      """)


test_base.main(globals(), __name__ == "__main__")
