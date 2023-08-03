"""Tests for the @typing.dataclass_transform decorator."""

from pytype.tests import test_base


class TestDataclassTransform(test_base.BaseTest):
  """Tests for @dataclass_transform."""

  def test_passthrough(self):
    # Test that @dataclass_transform just returns its decorated class.
    self.CheckWithErrors("""
      import typing_extensions

      class MetaDataclassArray(type):
        def __getitem__(cls, spec):
          pass

      @typing_extensions.dataclass_transform()  # not-supported-yet
      class DataclassArray(metaclass=MetaDataclassArray):
          def f(self) -> int:
            return 42

      x: DataclassArray = DataclassArray()
      y = x.f()
      assert_type(x, DataclassArray)
      assert_type(y, int)
    """)

  def test_invalid_target(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform  # not-supported-yet
      x = 10
      dataclass_transform()(x) # dataclass-error
    """)

  def test_py_function(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform  # not-supported-yet

      # NOTE: The decorator overrides the function body and makes `dc` a
      # dataclass decorator.
      @dataclass_transform()
      def dc(cls):
        return cls

      @dc
      class A:
        x: int

      a = A(x=10)
      assert_type(a, A)
    """)

  def test_write_pyi(self):
    ty, _ = self.InferWithErrors("""
      from typing_extensions import dataclass_transform  # not-supported-yet

      @dataclass_transform(eq_default=True)
      def dc(f):
        return f
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, dataclass_transform

      @dataclass_transform
      def dc(f) -> Any: ...
    """)

  def test_pyi_function(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar, dataclass_transform

      _T0 = TypeVar('_T0')

      @dataclass_transform
      def dc(cls: _T0) -> _T0: ...
    """)]):
      self.CheckWithErrors("""
        import foo

        @foo.dc
        class A:
          x: int

        a = A(x=10)
        b = A() # missing-parameter
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing import TypeVar
      from typing_extensions import dataclass_transform # pytype: disable=not-supported-yet

      @dataclass_transform()
      def dc(f):
        return f
    """)]):
      self.CheckWithErrors("""
        import foo

        @foo.dc
        class A:
          x: int

        a = A(x=10)
        b = A() # missing-parameter
      """)

if __name__ == "__main__":
  test_base.main()
