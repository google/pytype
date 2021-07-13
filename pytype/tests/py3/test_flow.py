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

  def test_unsatisfiable_in_with_block(self):
    self.Check("""
      import threading

      _temporaries = {}
      _temporaries_lock = threading.RLock()

      def GetResourceFilename(name: str):
        with _temporaries_lock:
          filename = _temporaries.get(name)
          if filename:
            return filename
        return name

      x = GetResourceFilename('a')
      assert_type(x, str)
    """)

  @test_base.skip("Does not work. See b/193472939")
  def test_unsatisfiable_in_except_block(self):
    self.Check("""
      def raise_error(e):
        raise(e)

      _temporaries = {}

      def f():
        try:
          return "hello"
        except Exception as e:
          filename = _temporaries.get('hello')
          if filename:
            return filename
          raise_error(e)

      f().lower()  # f() should be str, not str|None
    """)


test_base.main(globals(), __name__ == "__main__")
