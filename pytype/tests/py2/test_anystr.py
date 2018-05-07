"""Tests for typing.AnyStr."""

from pytype import utils
from pytype.tests import test_base


class AnyStrTest(test_base.TargetPython27FeatureTest):
  """Tests for issues related to AnyStr."""

  def testAnyStrFunctionImport(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr
      """)
      ty = self.Infer("""
        from a import f
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypesVar
        AnyStr = TypeVar("AnyStr", str, unicode)
        def f(x: AnyStr) -> AnyStr
      """)


if __name__ == "__main__":
  test_base.main()
