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

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_name_lookup(self):
    with file_utils.Tempdir() as d:
      d.create_file("e.pyi", "a_string: str")
      self.CheckWithErrors("""
        import enum
        import e
        class M(enum.Enum):
          A = 1
          B = "b"
        assert_type(M["A"].value, "int")
        assert_type(M["B"].value, "str")
        assert_type(M[e.a_string].value, "Any")
        _ = M["C"]  # attribute-error
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_name_lookup_pytd(self):
    with file_utils.Tempdir() as d:
      d.create_file("e.pyi", """
        enum: module
        a_string: str
        class M(enum.Enum):
          A: int
          B: str
      """)
      self.CheckWithErrors("""
        import e
        assert_type(e.M["A"].value, "int")
        assert_type(e.M["B"].value, "str")
        # Canonical PyTD enums are missing name/value fields.
        # assert_type(e.M[e.a_string].value, "Any")
        _ = e.M["C"]  # attribute-error
      """, pythonpath=[d.path])

  def test_bad_name_lookup(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):
        A = 1
      M[1]  # unsupported-operands
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_enum_named_name(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        name = 1
        value = "hello"
      assert_type(M.name, "M")
      assert_type(M.name.name, "str")
      assert_type(M.name.value, "int")
      assert_type(M.value, "M")
      assert_type(M.value.name, "str")
      assert_type(M.value.value, "str")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_enum_pytd_named_name(self):
    with file_utils.Tempdir() as d:
      d.create_file("m.pyi", """
        enum: module
        class M(enum.Enum):
          name: int
          value: str
      """)
      self.Check("""
        from m import M
        assert_type(M.name, "m.M")
        assert_type(M.name.name, "str")
        assert_type(M.name.value, "int")
        assert_type(M.value, "m.M")
        assert_type(M.value.name, "str")
        assert_type(M.value.value, "str")
      """, pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
