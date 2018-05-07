"""Test methods."""

from pytype.tests import test_base


class TestMethods(test_base.TargetPython27FeatureTest):
  """Tests for class methods"""

  # TODO(sivachandra): Make this a target independent test after b/78792372 is
  # fixed.
  def testAttributeInInheritedNew(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls, name):
          self = super(Foo, cls).__new__(cls)
          self.name = name
          return self
      class Bar(Foo):
        def __new__(cls):
          return super(Bar, cls).__new__(cls, "")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type, TypeVar
      _TFoo = TypeVar("_TFoo", bound=Foo)
      _TBar = TypeVar("_TBar", bound=Bar)
      class Foo(object):
        name = ...  # type: Any
        def __new__(cls: Type[_TFoo], name) -> _TFoo
      class Bar(Foo):
        name = ...  # type: str
        def __new__(cls: Type[_TBar]) -> _TBar
    """)


if __name__ == "__main__":
  test_base.main()
