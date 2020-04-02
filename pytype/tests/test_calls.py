"""Tests for calling other functions, and the corresponding checks."""

from pytype import file_utils
from pytype.tests import test_base


class CallsTest(test_base.TargetIndependentTest):
  """Tests for checking function calls."""

  def testOptional(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(x: int, y: int = ..., z: int = ...) -> int
      """)
      self.Check("""
        import mod
        mod.foo(1)
        mod.foo(1, 2)
        mod.foo(1, 2, 3)
      """, pythonpath=[d.path])

  def testMissing(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(x, y) -> int
      """)
      self.InferWithErrors("""
        import mod
        mod.foo(1)  # missing-parameter
      """, pythonpath=[d.path])

  def testExtraneous(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(x, y) -> int
      """)
      self.InferWithErrors("""
        import mod
        mod.foo(1, 2, 3)  # wrong-arg-count
      """, pythonpath=[d.path])

  def testMissingKwOnly(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(x, y, *, z) -> int
      """)
      _, errors = self.InferWithErrors("""
        import mod
        mod.foo(1, 2)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"\bz\b"})

  def testExtraKeyword(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(x, y) -> int
      """)
      self.InferWithErrors("""
        import mod
        mod.foo(1, 2, z=3)  # wrong-keyword-args
      """, pythonpath=[d.path])

  def testVarArgsWithKwOnly(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(*args: int, z: int) -> int
      """)
      self.Check(
          """
        import mod
        mod.foo(1, 2, z=3)
      """, pythonpath=[d.path])

  def testVarArgsWithMissingKwOnly(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        def foo(*args: int, z: int) -> int
      """)
      _, errors = self.InferWithErrors("""
        import mod
        mod.foo(1, 2, 3)  # missing-parameter[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"\bz\b"})


test_base.main(globals(), __name__ == "__main__")
