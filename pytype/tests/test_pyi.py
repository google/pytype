"""Tests for handling PYI code."""

import unittest


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
          def g(x: int) -> str
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

  @unittest.skip("pytd matching needs to understand inheritance")
  def testClasses(self):
    with utils.Tempdir() as d:
      d.create_file("classes.pytd", """
        class A(object):
          def foo(self) -> A
        class B(A):
          pass
      """)
      with self.Infer("""\
        import classes
        x = classes.B().foo()
      """, deep=False, solve_unknowns=False, pythonpath=[d.path]) as ty:
        self.assertTypesMatchPytd(ty, """
          classes = ...  # type: module
          x = ...  # type: int
        """)

if __name__ == "__main__":
  test_inference.main()
