"""Tests for handling PYI code."""


from pytype import utils
from pytype.tests import test_inference


class PYITest(test_inference.InferenceTest):
  """Tests for PYI."""

  def testOptional(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pytd", """
        def f(x: int = ...) -> None
      """)
      with self.Infer("""\
        import mod
        def f():
          return mod.f()
        def g():
          return mod.f(3)
      """, deep=True, solve_unknowns=False,
                      extract_locals=True,  # TODO(kramm): Shouldn't need this.
                      pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          mod = ...  # type: module
          def f() -> NoneType
          def g() -> NoneType
        """)


if __name__ == "__main__":
  test_inference.main()
