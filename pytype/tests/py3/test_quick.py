"""Tests for --quick."""

from pytype import file_utils
from pytype.tests import test_base


class QuickTest(test_base.TargetPython3BasicTest):
  """Tests for --quick."""

  def test_multiple_returns(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def add(x: int, y: int) -> int: ...
        def add(x: int,  y: float) -> float: ...
      """)
      self.Check("""
        import foo
        def f1():
          f2()
        def f2() -> int:
          return foo.add(42, f3())
        def f3():
          return 42
      """, pythonpath=[d.path], quick=True)

  def test_multiple_returns_container(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        def concat(x: int, y: int) -> Tuple[int, int]: ...
        def concat(x: int, y: float) -> Tuple[int, float]: ...
      """)
      self.Check("""
        from typing import Tuple
        import foo
        def f1():
          f2()
        def f2() -> Tuple[int, int]:
          return foo.concat(42, f3())
        def f3():
          return 42
      """, pythonpath=[d.path], quick=True)


test_base.main(globals(), __name__ == "__main__")
