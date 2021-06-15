"""Tests for the enum overlay."""

from pytype import file_utils
from pytype.tests import test_base


class EnumOverlayTest(test_base.TargetPython3FeatureTest):
  """Tests the overlay."""

  def test_can_import_module_members(self):
    self.Check("""
      import enum
      enum.Enum
      enum.IntEnum
      enum.IntFlag
      enum.Flag
      enum.unique
      enum.auto
    """)

  def test_create_basic_enum(self):
    self.Check("""
      import enum
      class Colors(enum.Enum):
        RED = 1
        GREEN = 2
        BLUE = 3
      _ = (Colors.RED, Colors.GREEN, Colors.BLUE)
      _ = Colors.RED.name
      _ = Colors.RED.value
    """)

  def test_output_basic_enum(self):
    ty = self.Infer("""
      import enum
      class Colors(enum.Enum):
        RED = 1
        GREEN = 2
        BLUE = 3
      """)
    self.assertTypesMatchPytd(ty, """
      enum: module
      class Colors(enum.Enum):
        BLUE: int
        GREEN: int
        RED: int
      """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_access_members_and_values(self):
    self.CheckWithErrors("""
      import enum
      class Colors(enum.Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

      ### Will pass:
      assert_type(Colors.RED.value, "int")
      assert_type(Colors.BLUE, "Colors")
      ### Will fail:
      assert_type(Colors.RED, "int")  # assert-type
      assert_type(Colors.GREEN.value, "Colors")  # assert-type
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_basic_enum_from_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("e.pyi", """
        enum: module
        class Colors(enum.Enum):
          RED: int
          BLUE: int
          GREEN: int
      """)
      ty = self.Infer("""
        import e
        c = e.Colors.RED
        n = e.Colors.BLUE.name
        v = e.Colors.GREEN.value
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        e: module
        c: e.Colors
        n: str
        v: int
      """)


test_base.main(globals(), __name__ == "__main__")
