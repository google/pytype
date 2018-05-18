"""Test comparison operators."""

from pytype.tests import test_base


class DecoratorsTest(test_base.TargetPython3BasicTest):

  def testAnnotatedSuperCallUnderBadDecorator(self):
    _, errors = self.InferWithErrors("""\
            class Foo(object):
        def Run(self) -> None: ...
      class Bar(Foo):
        @bad_decorator  # line 5
        def Run(self):
          return super(Bar, self).Run()
    """)
    self.assertErrorLogIs(errors, [(5, "name-error", r"bad_decorator")])


test_base.main(globals(), __name__ == "__main__")
