"""Tests of special builtins (special_builtins.py."""


from pytype.tests import test_inference


class SpecialBuiltinsTest(test_inference.InferenceTest):
  """Tests for special_builtins.py."""

  def testNext(self):
    self.assertNoCrash("""
      next(None)
    """)

  def testNext2(self):
    self.assertNoCrash("""
      class Foo(object):
        def a(self):
          self._foo = None
        def b(self):
          self._foo = __any_object__
        def c(self):
          next(self._foo)
    """)

  def testAbs(self):
    self.assertNoCrash("""
      abs(None)
    """)


if __name__ == "__main__":
  test_inference.main()
