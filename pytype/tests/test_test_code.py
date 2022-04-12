"""Tests for type checking test code."""

from pytype.tests import test_base


class AssertionTest(test_base.BaseTest):
  """Tests for test assertions."""

  def test_assert_not_none(self):
    self.Check("""
      import unittest
      from typing import Optional
      def foo():
        return '10' if __random__ else None
      class FooTest(unittest.TestCase):
        def test_foo(self):
          x = foo()
          assert_type(x, Optional[str])
          self.assertIsNotNone(x)
          assert_type(x, str)
    """)

  def test_assert_isinstance(self):
    self.Check("""
      import unittest
      from typing import Union
      def foo():
        return '10' if __random__ else 10
      class FooTest(unittest.TestCase):
        def test_foo(self):
          x = foo()
          assert_type(x, Union[int, str])
          self.assertIsInstance(x, str)
          assert_type(x, str)
    """)

  def test_new_type_from_assert_isinstance(self):
    # assertIsInstance should create a var with a new type even if it is not in
    # the original var's bindings.
    self.Check("""
      import unittest
      class A:
        pass
      class B(A):
        pass
      def foo() -> A:
        return B()
      class FooTest(unittest.TestCase):
        def test_foo(self):
          x = foo()
          assert_type(x, A)
          self.assertIsInstance(x, B)
          assert_type(x, B)
    """)

  def test_assert_isinstance_tuple(self):
    self.Check("""
      import unittest
      from typing import Union
      class FooTest(unittest.TestCase):
        def test_foo(self):
          x = None
          self.assertIsInstance(x, (int, str))
          assert_type(x, Union[int, str])
          self.assertIsInstance(x, (int,))
          assert_type(x, int)
    """)

  def test_instance_attribute(self):
    self.Check("""
      import unittest
      class Foo:
        def __init__(self, x):
          self.x = x
      class FooTest(unittest.TestCase):
        def test_foo(self):
          foo = __any_object__
          self.assertIsInstance(foo, Foo)
          print(foo.x)
    """)


class MockTest(test_base.BaseTest):
  """Tests for unittest.mock."""

  def test_patch(self):
    self.Check("""
      import unittest
      from unittest import mock
      foo = __any_object__
      bar = __any_object__
      class Foo(unittest.TestCase):
        def setUp(self):
          super().setUp()
          self.some_mock = mock.patch.object(foo, 'foo').start()
          self.some_mock.return_value = True
        def test_bar(self):
          other_mock = mock.patch.object(bar, 'bar').start()
          other_mock.return_value.__enter__ = lambda x: x
    """)


if __name__ == "__main__":
  test_base.main()
