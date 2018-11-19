"""Tests for mixin.py."""

from pytype import mixin
import six
import unittest


class MixinMetaTest(unittest.TestCase):

  def test_mixin_super(self):
    """Test the imitation 'super' method on MixinMeta."""
    # pylint: disable=g-wrong-blank-lines
    class A(object):
      def f(self, x):
        return x
    @six.add_metaclass(mixin.MixinMeta)
    class MyMixin(object):
      overloads = ("f",)
      def f(self, x):
        if x == 0:
          return "hello"
        return MyMixin.super(self.f)(x)
    class B(A, MyMixin):
      pass
    # pylint: enable=g-wrong-blank-lines
    b = B()
    v_mixin = b.f(0)
    v_a = b.f(1)
    self.assertEqual(v_mixin, "hello")
    self.assertEqual(v_a, 1)


if __name__ == "__main__":
  unittest.main()
