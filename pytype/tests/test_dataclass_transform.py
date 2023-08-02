"""Tests for the @typing.dataclass_transform decorator."""

from pytype.tests import test_base


class TestDataclassTransform(test_base.BaseTest):
  """Tests for @dataclass_transform."""

  def test_passthrough(self):
    # Test that @dataclass_transform just returns its decorated object.
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


if __name__ == "__main__":
  test_base.main()
