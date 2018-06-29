"""Test decorators."""

from pytype.tests import test_base


class DecoratorsTest(test_base.TargetPython3BasicTest):
  """Test decorators."""

  def testAnnotatedSuperCallUnderBadDecorator(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def Run(self) -> None: ...
      class Bar(Foo):
        @bad_decorator  # line 4
        def Run(self):
          return super(Bar, self).Run()
    """)
    self.assertErrorLogIs(errors, [(4, "name-error", r"bad_decorator")])


test_base.main(globals(), __name__ == "__main__")
