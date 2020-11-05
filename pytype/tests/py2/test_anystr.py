"""Tests for typing.AnyStr."""

from pytype import file_utils
from pytype.tests import test_base


class AnyStrTest(test_base.TargetPython27FeatureTest):
  """Tests for issues related to AnyStr."""

  def test_anystr_function_import(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr: ...
      """)
      ty = self.Infer("""
        from a import f
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypesVar
        AnyStr = TypeVar("AnyStr", str, unicode)
        def f(x: AnyStr) -> AnyStr: ...
      """)

  def test_custom_generic(self):
    ty = self.Infer("""
      from typing import AnyStr, Generic
      class Foo(Generic[AnyStr]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      AnyStr = TypeVar('AnyStr', bytes, unicode)
      class Foo(Generic[AnyStr]): ...
    """)


test_base.main(globals(), __name__ == "__main__")
