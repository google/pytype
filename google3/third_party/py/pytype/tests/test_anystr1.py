"""Tests for typing.AnyStr."""

from pytype.tests import test_base
from pytype.tests import test_utils


class AnyStrTest(test_base.BaseTest):
  """Tests for issues related to AnyStr."""

  def test_type_parameters(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr: ...
      """)
      ty = self.Infer("""
        import a
        if a.f(""):
          x = 3
        if a.f("hello"):
          y = 3
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        x = ...  # type: int
        y = ...  # type: int
      """)

  def test_format(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr: ...
      """)
      self.Check("""
        import foo
        foo.f("" % __any_object__)
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
