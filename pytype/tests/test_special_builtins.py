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

  def testPropertyMatching(self):
    self.assertNoErrors("""
      class A():
        def setter(self, other):
          pass
        def getter(self):
          return 42
        def create_property(self, cls, property_name):
          setattr(cls, property_name, property(self.getter, self.setter))
    """)


if __name__ == "__main__":
  test_inference.main()
