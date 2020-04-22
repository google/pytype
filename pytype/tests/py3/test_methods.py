"""Test methods."""

from pytype.tests import test_base


class TestMethods(test_base.TargetPython3BasicTest):
  """Tests for class methods."""

  def test_function_init(self):
    ty = self.Infer("""
      def __init__(self: int):
        return self
    """)
    self.assertTypesMatchPytd(ty, """
      def __init__(self: int) -> int
    """)

  def test_annotated_self(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __init__(x: int):
          pass  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*x"})

  def test_late_annotated_self(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __init__(x: "X"):
          pass  # invalid-annotation[e]
      class X(object):
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"X.*x"})

  def test_attribute_with_annotated_self(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __init__(self: int):
          self.x = 3  # invalid-annotation[e]
        def foo(self):
          return self.x
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*self"})

  def test_attribute_with_annotated_self_and_function_init(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __init__(self: int):
          self.x = 3  # invalid-annotation[e]
      def __init__(self: int):
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*self"})


test_base.main(globals(), __name__ == "__main__")
