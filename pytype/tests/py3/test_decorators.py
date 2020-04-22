"""Test decorators."""

from pytype.tests import test_base


class DecoratorsTest(test_base.TargetPython3BasicTest):
  """Test decorators."""

  def test_annotated_super_call_under_bad_decorator(self):
    self.InferWithErrors("""
      class Foo(object):
        def Run(self) -> None: ...
      class Bar(Foo):
        @bad_decorator  # name-error
        def Run(self):
          return super(Bar, self).Run()
    """)

  def test_replace_self_to_stararg(self):
    # Without decorator, `self` will be in `signature.param_names`.
    # But after replacing, `*args` won't be in `signature.param_names`.
    self.Check("""
      from typing import TypeVar

      T = TypeVar('T')
      def dec(func):
        def f(*args: T, **kwargs: T):
          pass

        return f

      class MyClass(object):
        @dec
        def func(self, x):
          pass

      x = MyClass()
      x.func(12)
    """)

test_base.main(globals(), __name__ == "__main__")
