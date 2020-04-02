"""Tests for control flow (with statements, loops, exceptions, etc.)."""

from pytype.tests import test_base


class FlowTest(test_base.TargetPython3BasicTest):
  """Tests for control flow.

  These tests primarily test instruction ordering and CFG traversal of the
  bytecode interpreter, i.e., their primary focus isn't the inferred types.
  Even though they check the validity of the latter, they're mostly smoke tests.
  """

  def test_loop_and_if(self):
    self.Check("""
      import typing
      def foo() -> str:
        while True:
          y = None
          z = None
          if __random__:
            y = "foo"
            z = "foo"
          if y:
            return z
        return "foo"
    """)

  def test_cfg_cycle_singlestep(self):
    self.Check("""
      import typing
      class Foo(object):
        x = ...  # type: typing.Optional[int]
        def __init__(self):
          self.x = None
        def X(self) -> int:
          return self.x or 4
        def B(self) -> None:
          self.x = 5
          if __random__:
            self.x = 6
        def C(self) -> None:
          self.x = self.x
    """)


test_base.main(globals(), __name__ == "__main__")
