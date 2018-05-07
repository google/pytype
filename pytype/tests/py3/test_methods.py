"""Test methods."""

from pytype.tests import test_base


class TestMethods(test_base.TargetPython3BasicTest):
  """Tests for class methods"""

  def testFunctionInit(self):
    ty = self.Infer("""
            def __init__(self: int):
        return self
    """)
    self.assertTypesMatchPytd(ty, """
      def __init__(self: int) -> int
    """)

  def testAnnotatedSelf(self):
    errors = self.CheckWithErrors("""\
            class Foo(object):
        def __init__(x: int):
          pass
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation", r"int.*x")])

  def testLateAnnotatedSelf(self):
    errors = self.CheckWithErrors("""\
            class Foo(object):
        def __init__(x: "X"):
          pass
      class X(object):
        pass
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation", r"X.*x")])

  def testAttributeWithAnnotatedSelf(self):
    errors = self.CheckWithErrors("""\
            class Foo(object):
        def __init__(self: int):
          self.x = 3
        def foo(self):
          return self.x
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation", r"int.*self")])

  def testAttributeWithAnnotatedSelfAndFunctionInit(self):
    errors = self.CheckWithErrors("""\
            class Foo(object):
        def __init__(self: int):
          self.x = 3
      def __init__(self: int):
        pass
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation", r"int.*self")])


if __name__ == "__main__":
  test_base.main()
