"""Test comparison operators."""

from pytype.tests import test_base


class InstanceUnequalityTest(test_base.BaseTest):

  def test_is(self):
    """SomeType is not be the same as AnotherType."""
    self.Check("""
      from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is None:
          return x
        else:
          return None
      """)


class ContainsFallbackTest(test_base.BaseTest):
  """Tests the __contains__ -> __iter__ -> __getitem__ fallbacks."""

  def test_overload_contains(self):
    self.CheckWithErrors("""
      class F:
        def __contains__(self, x: int):
          if not isinstance(x, int):
            raise TypeError("__contains__ only takes int")
          return True
      1 in F()
      "not int" in F()  # unsupported-operands
    """)

  def test_fallback_iter(self):
    self.Check("""
      class F:
        def __iter__(self):
          pass
      1 in F()
      "not int" in F()
    """)

  def test_fallback_getitem(self):
    self.Check("""
      class F:
        def __getitem__(self, key):
          pass
      1 in F()
      "not int" in F()
    """)


class NotImplementedTest(test_base.BaseTest):
  """Tests handling of the NotImplemented builtin."""

  def test_return_annotation(self):
    self.Check("""
      class Foo:
        def __eq__(self, other) -> bool:
          if isinstance(other, Foo):
            return id(self) == id(other)
          else:
            return NotImplemented
    """)

  def test_infer_return_type(self):
    ty = self.Infer("""
      class Foo:
        def __eq__(self, other):
          if isinstance(other, Foo):
            return id(self) == id(other)
          else:
            return NotImplemented
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __eq__(self, other) -> bool: ...
    """)


class CmpErrorTest(test_base.BaseTest):
  """Tests comparisons with type errors."""

  def test_compare_types(self):
    ty, _ = self.InferWithErrors("""
      res = (1).__class__ < ''.__class__  # unsupported-operands
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      res: Any
    """)

  def test_failed_override(self):
    # Check that we add a return value binding and raise the error.
    self.CheckWithErrors("""
      import datetime
      a = datetime.timedelta(0)
      b = bool(a > 0)  # unsupported-operands
    """)

  def test_compare_primitives(self):
    self.CheckWithErrors("""
      100 < 'a'  # unsupported-operands
      'a' <= 1.0  # unsupported-operands
      10 < 10.0
      10.0 >= 10
      def f(x: int, y: str) -> bool:
        return x < y  # unsupported-operands
    """)


class MetaclassTest(test_base.BaseTest):
  """Tests comparisons on class objects with a custom metaclass."""

  def test_compare_types(self):
    # See b/205755440 - this is the wrong error message to be raising, and the
    # test should fail once the bug is fixed. For now we test that we don't
    # crash due to b/205333186.
    self.CheckWithErrors("""
      class Meta(type):
        def __gt__(self, other):
          return True
          # return self.__name__ > other.__name__

      class A(metaclass=Meta): pass
      class B(metaclass=Meta): pass

      print(A > B)  # missing-parameter
    """)


if __name__ == "__main__":
  test_base.main()
