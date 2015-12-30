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

  def testSolve(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pytd", """
        def f(node: int, *args, **kwargs) -> str
      """)
      with self.Infer("""\
        import mod
        def g(x):
          return mod.f(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          mod = ...  # type: module
          def g(x: bool or int) -> str
        """)

  def testTyping(self):
    with utils.Tempdir() as d:
      d.create_file("mod.pytd", """
        from typing import Optional, List, Any, IO
        def split(s: Optional[float]) -> List[str, ...]: ...
      """)
      with self.Infer("""\
        import mod
        def g(x):
          return mod.split(x)
      """, deep=True, solve_unknowns=True, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          mod = ...  # type: module
          def g(x: NoneType or float) -> List[str, ...]
        """)

if __name__ == "__main__":
  test_inference.main()
