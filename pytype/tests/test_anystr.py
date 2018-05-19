"""Tests for typing.AnyStr."""

from pytype import file_utils
from pytype.tests import test_base


class AnyStrTest(test_base.TargetIndependentTest):
  """Tests for issues related to AnyStr."""

  def testTypeParameters(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr
      """)
      ty = self.Infer("""
        import a
        if a.f(""):
          x = 3
        if a.f("hello"):
          y = 3
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
        y = ...  # type: int
      """)


test_base.main(globals(), __name__ == "__main__")
