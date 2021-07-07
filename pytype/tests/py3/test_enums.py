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
        assert_type(M[e.a_string].value, "Union[int, str]")
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

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_value_lookup(self):
    self.CheckWithErrors("""
      import enum
      from typing import Union
      class M(enum.Enum):
        A = 1
      assert_type(M(1), "M")
      assert_type(M(1).value, "int")
      assert_type(M(-500), "M")
      M("str")  # wrong-arg-types
      class N(enum.Enum):
        A = 1
        B = "str"
      assert_type(N(1), "N")
      assert_type(N("str"), "N")
      assert_type(N(499).value, "Union[int, str]")
      N(M.A)  # wrong-arg-types
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_value_lookup_pytd(self):
    with file_utils.Tempdir() as d:
      d.create_file("m.pyi", """
        enum: module
        class M(enum.Enum):
          A: int
        class N(enum.Enum):
          A: int
          B: str
      """)
      self.CheckWithErrors("""
        from typing import Union
        from m import M, N
        assert_type(M(1), "m.M")
        # assert_type(M(1).value, "int")
        assert_type(M(-500), "m.M")
        M("str")  # wrong-arg-types
        assert_type(N(1), "m.N")
        assert_type(N("str"), "m.N")
        # assert_type(N(499).value, "Union[int, str]")
        N(M.A)  # wrong-arg-types
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_value_lookup_no_members(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        pass
      x = M(1)
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_value_looku_no_members_pytd(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import enum
        class M(enum.Enum):
          ...
      """)
      self.Check("""
        import foo
        x = foo.M  # to force foo.M to be loaded by the overlay.
        y = foo.M(1)
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_enum_eq(self):
    # Note that this test only checks __eq__'s behavior. Though enums support
    # comparisons using `is`, pytype doesn't check `is` the same way as __eq__.
    self.Check("""
      import enum
      class M(enum.Enum):
        A = 1
      class N(enum.Enum):
        A = 1

      # Boolean values indicate the expected result.
      if M.A == N.A:
        a = None
      else:
        a = False

      if M.A == M.A:
        b = True
      else:
        b = None

      if M["A"] == M.A:
        c = True
      else:
        c = None
      assert_type(a, "bool")
      assert_type(b, "bool")
      assert_type(c, "bool")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_enum_pytd_eq(self):
    with file_utils.Tempdir() as d:
      d.create_file("m.pyi", """
        enum: module
        class M(enum.Enum):
          A: int
        class N(enum.Enum):
          A: int
      """)
      self.Check("""
        from m import M, N

        # Boolean values indicate the expected result.
        if M.A == N.A:
          a = None
        else:
          a = False

        if M.A == M.A:
          b = True
        else:
          b = None

        if M["A"] == M.A:
          c = True
        else:
          c = None
        assert_type(a, "bool")
        assert_type(b, "bool")
        assert_type(c, "bool")
      """, pythonpath=[d.path])

  def test_metaclass_methods(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):
        A = 1
      class N(enum.Enum):
        A = 1

      # __contains__
      M.A in M
      N.A in M
      1 in M  # unsupported-operands

      # __iter__
      assert_type([e for e in M], "List[M]")

      # __len__
      assert_type(len(M), "int")

      # __bool__
      assert_type(bool(M), "bool")
    """)

  def test_pytd_metaclass_methods(self):
    with file_utils.Tempdir() as d:
      d.create_file("m.pyi", """
        enum: module
        class M(enum.Enum):
          A: int
      """)
      self.CheckWithErrors("""
        import enum
        from m import M
        class N(enum.Enum):
          A = 1

        # __contains__
        M.A in M
        N.A in M
        1 in M  # unsupported-operands

        # __iter__
        assert_type([e for e in M], "List[m.M]")

        # __len__
        assert_type(len(M), "int")

        # __bool__
        assert_type(bool(M), "bool")
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_functional_api(self):
    self.Check("""
      import enum

      M = enum.Enum("M", "A, B")
      assert_type(M.B, "M")
      assert_type(M.B.value, "int")

      N = enum.Enum("N", ["A", "B"])
      assert_type(N.B, "N")
      assert_type(N.B.value, "int")

      class Marker: pass
      O = enum.Enum("O", [("A", Marker()), ("B", Marker())])
      assert_type(O.B, "O")
      assert_type(O.B.value, "Marker")

      P = enum.Enum("P", {"A": "a", "B": "b"})
      assert_type(P.B, "P")
      assert_type(P.B.value, "str")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_functional_api_errors(self):
    self.CheckWithErrors("""
      import enum

      enum.Enum(1)  # missing-parameter
      enum.Enum(1, "A")  # wrong-arg-types
      enum.Enum("X", [1, 2])  # wrong-arg-types
      enum.Enum("X", object())  # wrong-arg-types
      enum.Enum("Y", "A", start="4")  # wrong-arg-types
    """)

  def test_functional_no_constants(self):
    with file_utils.Tempdir() as d:
      d.create_file("m.pyi", "A: str")
      self.Check("""
        import enum
        import m
        F = enum.Enum("F", [(m.A, m.A)])
        for x in F:
          print(x)
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_basic(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        A = enum.auto()
      assert_type(M.A, "M")
      assert_type(M.A.value, "int")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_mixed(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        A = "hello"
        B = enum.auto()
      assert_type(M.A.value, "str")
      assert_type(M.B.value, "int")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_generate_basic(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        def _generate_next_value_(name, start, count, last_values):
          return name
        A = enum.auto()
      assert_type(M.A, "M")
      assert_type(M.A.value, "str")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_generate_staticmethod(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
          return name
        A = enum.auto()
      assert_type(M.A, "M")
      assert_type(M.A.value, "str")
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_generate_error(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):
        def _generate_next_value_(name, start, count, last_values):
          return name + count  # unsupported-operands
        A = enum.auto()
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_generate_wrong_annots(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):  # wrong-arg-types
        def _generate_next_value_(name: int, start: int, count: int, last_values: int):
          return name
        A = enum.auto()
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_generate_from_pyi_base(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import enum
        class Base(enum.Enum):
          def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str: ...
      """)
      self.Check("""
        import enum
        import foo
        class M(foo.Base):
          A = enum.auto()
        assert_type(M.A.value, "str")
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_generate_from_pyi_base_staticmethod(self):
    # It's possible that _generate_next_value_ will appear in a type stub as a
    # staticmethod. This should not change how pytype handles it.
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import enum
        class Base(enum.Enum):
          @staticmethod
          def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str: ...
      """)
      self.Check("""
        import enum
        import foo
        class M(foo.Base):
          A = enum.auto()
        assert_type(M.A.value, "str")
      """, pythonpath=[d.path])

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_auto_pytd(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import enum
        class M(enum.Enum):
          A: int
          B: int
          def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str: ...
      """)
      self.Check("""
        from typing import Callable
        from foo import M
        assert_type(M.A, "foo.M")
        assert_type(M.A.value, "int")
        assert_type(M.B.value, "int")
        assert_type(M._generate_next_value_, Callable[[str, int, int, list], str])
      """, pythonpath=[d.path])

test_base.main(globals(), __name__ == "__main__")
