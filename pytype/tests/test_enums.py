"""Tests for the enum overlay."""

from pytype.tests import test_base
from pytype.tests import test_utils


class EnumOverlayTest(test_base.BaseTest):
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
    self.assertTypesMatchPytd(
        ty,
        """
      import enum
      from typing import Literal
      class Colors(enum.Enum):
          BLUE: Literal[3]
          GREEN: Literal[2]
          RED: Literal[1]
      """,
    )

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

  def test_sunderscore_name_value(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        A = 1
      assert_type(M.A._name_, str)
      assert_type(M.A._value_, int)
      def f(m: M):
        assert_type(m._name_, str)
        assert_type(m._value_, int)
    """)

  def test_sunderscore_name_value_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class M(enum.Enum):
          A: int
      """,
      )
      self.Check(
          """
        from typing import Any
        import foo
        assert_type(foo.M.A._name_, str)
        assert_type(foo.M.A._value_, int)
        def f(m: foo.M):
          assert_type(m._name_, str)
          assert_type(m._value_, Any)
      """,
          pythonpath=[d.path],
      )

  def test_basic_enum_from_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "e.pyi",
          """
        import enum
        class Colors(enum.Enum):
          RED: int
          BLUE: int
          GREEN: int
      """,
      )
      ty = self.Infer(
          """
        import e
        c = e.Colors.RED
        n = e.Colors.BLUE.name
        v = e.Colors.GREEN.value
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import e
        c: e.Colors
        n: str
        v: int
      """,
      )

  def test_enum_from_pyi_recur(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class Recur(enum.Enum):
          A: Recur
      """,
      )
      self.Check(
          """
        import foo
        Recur = foo.Recur
      """,
          pythonpath=[d.path],
      )

  def test_canonical_enum_members(self):
    # Checks that enum members created by instantiate() behave similarly to
    # real enum members.
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class F(enum.Enum):
          X: int
      """,
      )
      self.Check(
          """
        import enum
        from foo import F
        class M(enum.Enum):
          A = 1
        def get_name(x: M) -> str:
          return x.name
        def get_pyi_name(x: F) -> str:
          return x.name
        def get_value(x: M) -> int:
          return x.value
        def get_pyi_value(x: F) -> int:
          return x.value
      """,
          pythonpath=[d.path],
      )

  def test_pytd_returns_enum(self):
    # Ensure that canonical enums created by PytdSignature.instantiate_return
    # have name and value fields.
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class M(enum.Enum):
          A: int
        def get_m(name: str) -> M: ...
      """,
      )
      self.CheckWithErrors(
          """
        import foo
        def print_m(name: str):
          print(foo.get_m(name).name)
          print(foo.get_m(name).value)
      """,
          pythonpath=[d.path],
      )

  def test_name_value_overlap(self):
    # Make sure enum members named "name" and "value" work correctly.
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

  def test_name_value_overlap_pyi(self):
    # Make sure enum members named "name" and "value" work correctly.
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class M(enum.Enum):
          name: int
          value: str
      """,
      )
      self.Check(
          """
        import foo
        assert_type(foo.M.name, "foo.M")
        assert_type(foo.M.name.name, "str")
        assert_type(foo.M.name.value, "int")
        assert_type(foo.M.value, "foo.M")
        assert_type(foo.M.value.name, "str")
        assert_type(foo.M.value.value, "str")
      """,
          pythonpath=[d.path],
      )

  def test_name_lookup(self):
    with test_utils.Tempdir() as d:
      d.create_file("e.pyi", "a_string: str")
      self.CheckWithErrors(
          """
        import enum
        import e
        class M(enum.Enum):
          A = 1
          B = "b"
        assert_type(M["A"].value, "int")
        assert_type(M["B"].value, "str")
        assert_type(M[e.a_string].value, "Union[int, str]")
        _ = M["C"]  # attribute-error
      """,
          pythonpath=[d.path],
      )

  def test_name_lookup_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "e.pyi",
          """
        import enum
        a_string: str
        class M(enum.Enum):
          A: int
          B: str
      """,
      )
      self.CheckWithErrors(
          """
        import e
        assert_type(e.M["A"].value, "int")
        assert_type(e.M["B"].value, "str")
        assert_type(e.M[e.a_string].value, "Any")
        _ = e.M["C"]  # attribute-error
      """,
          pythonpath=[d.path],
      )

  def test_name_lookup_from_canonical(self):
    # Canonical enum members should have non-atomic names.
    self.Check("""
      import enum
      class M(enum.Enum):
        A = 1
      def get(m: M):
        m = M[m.name]
    """)

  def test_bad_name_lookup(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):
        A = 1
      M[1]  # unsupported-operands
    """)

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

  def test_enum_pytd_named_name(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "m.pyi",
          """
        import enum
        class M(enum.Enum):
          name: int
          value: str
      """,
      )
      self.Check(
          """
        from m import M
        assert_type(M.name, "m.M")
        assert_type(M.name.name, "str")
        assert_type(M.name.value, "int")
        assert_type(M.value, "m.M")
        assert_type(M.value.name, "str")
        assert_type(M.value.value, "str")
      """,
          pythonpath=[d.path],
      )

  def test_value_lookup(self):
    self.CheckWithErrors("""
      import enum
      from typing import Union
      class M(enum.Enum):
        A = 1
      assert_type(M(1), "M")
      assert_type(M(1).value, "int")
      assert_type(M(-500), "M")
      assert_type(M(M.A), "M")
      M("str")  # wrong-arg-types
      class N(enum.Enum):
        A = 1
        B = "str"
      assert_type(N(1), "N")
      assert_type(N("str"), "N")
      assert_type(N(499).value, "Union[int, str]")
      N(M.A)  # wrong-arg-types
    """)

  def test_value_lookup_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "m.pyi",
          """
        import enum
        class M(enum.Enum):
          A: int
        class N(enum.Enum):
          A: int
          B: str
      """,
      )
      self.CheckWithErrors(
          """
        from typing import Union
        from m import M, N
        assert_type(M(1), "m.M")
        assert_type(M(M.A), "m.M")
        # assert_type(M(1).value, "int")
        assert_type(M(-500), "m.M")
        M("str")  # wrong-arg-types
        assert_type(N(1), "m.N")
        assert_type(N("str"), "m.N")
        # assert_type(N(499).value, "Union[int, str]")
        N(M.A)  # wrong-arg-types
      """,
          pythonpath=[d.path],
      )

  def test_value_lookup_no_members(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        pass
      x = M(1)
    """)

  def test_value_lookup_no_members_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class M(enum.Enum):
          ...
      """,
      )
      self.Check(
          """
        import foo
        x = foo.M  # to force foo.M to be loaded by the overlay.
        y = foo.M(1)
      """,
          pythonpath=[d.path],
      )

  def test_reingest_literal_members(self):
    with self.DepTree([(
        "foo.py",
        """
      import enum
      class A(enum.Enum):
        FOO = 1
        BAR = 2
    """,
    )]):
      self.Check("""
        from typing import Literal
        from foo import A
        def f(x: Literal[1]): ...
        def g(x: int):
          a = A(x)  # this should take a non-concrete int
        b = f(A.FOO.value)  # this should preserve the concrete pyval
      """)

  @test_base.skip("Stricter equality disabled due to b/195136939")
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

  @test_base.skip("Stricter equality disabled due to b/195136939")
  def test_enum_pytd_eq(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "m.pyi",
          """
        import enum
        class M(enum.Enum):
          A: int
        class N(enum.Enum):
          A: int
      """,
      )
      self.Check(
          """
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
      """,
          pythonpath=[d.path],
      )

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
      assert_type([e for e in M], "list[M]")

      # __len__
      assert_type(len(M), "int")

      # __bool__
      assert_type(bool(M), "bool")
    """)

  def test_pytd_metaclass_methods(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "m.pyi",
          """
        import enum
        class M(enum.Enum):
          A: int
      """,
      )
      self.CheckWithErrors(
          """
        import enum
        from m import M
        class N(enum.Enum):
          A = 1

        # __contains__
        M.A in M
        N.A in M
        1 in M  # unsupported-operands

        # __iter__
        assert_type([e for e in M], "list[m.M]")

        # __len__
        assert_type(len(M), "int")

        # __bool__
        assert_type(bool(M), "bool")
      """,
          pythonpath=[d.path],
      )

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

  def test_functional_api_empty_enum(self):
    # Empty enums can be extended (subclassed) so they can be used for the
    # functional api.
    self.Check("""
      import enum
      class Pretty(enum.Enum):
        def __str__(self) -> str:
          return self.name.replace("_", " ").title()
      M = Pretty("M", "A B C")
    """)

  def test_functional_api_empty_pytd_enum(self):
    # Empty enums can be extended (subclassed) so they can be used for the
    # functional api.
    with test_utils.Tempdir() as d:
      d.create_file(
          "pretty.pyi",
          """
        enum: module
        class Pretty(enum.Enum):
          def __str__(self) -> str: ...
      """,
      )
      self.Check(
          """
        from pretty import Pretty
        M = Pretty("M", "A B C")
      """,
          pythonpath=[d.path],
      )

  def test_functional_api_errors(self):
    self.CheckWithErrors("""
      import enum

      enum.Enum(1, "A")  # wrong-arg-types
      enum.Enum("X", [1, 2])  # wrong-arg-types
      enum.Enum("X", object())  # wrong-arg-types
      enum.Enum("Y", "A", start="4")  # wrong-arg-types
    """)

  def test_functional_api_no_constants(self):
    with test_utils.Tempdir() as d:
      d.create_file("m.pyi", "A: str")
      self.Check(
          """
        import enum
        import m
        F = enum.Enum("F", [(m.A, m.A)])
        for x in F:
          print(x)
      """,
          pythonpath=[d.path],
      )

  def test_functional_api_intenum(self):
    # Technically, any subclass of Enum without any members can be used for the
    # functional API. This is annoying and hard to detect, but we should support
    # it for the other classes in the enum library.
    self.Check("""
      import enum
      FI = enum.IntEnum("FI", ["A", "B", "C"])
      assert_type(FI.A, FI)
      assert_type(FI.A.value, int)
    """)

  def test_functional_api_actually_lookup(self):
    # Sometimes a Type[Enum] will be called to lookup a value, which will go
    # to EnumBuilder.call instead of a specific EnumInstance.__new__.
    self.Check("""
      import enum
      from typing import Type
      def just_a_lookup(name: str, category: Type[enum.Enum]):
        category(name)
    """)

  def test_auto_basic(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        A = enum.auto()
      assert_type(M.A, "M")
      assert_type(M.A.value, "int")
    """)

  def test_auto_mixed(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        A = "hello"
        B = enum.auto()
      assert_type(M.A.value, "str")
      assert_type(M.B.value, "int")
    """)

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

  def test_auto_generate_error(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):
        def _generate_next_value_(name, start, count, last_values):
          return name + count  # unsupported-operands
        A = enum.auto()
    """)

  def test_auto_generate_wrong_annots(self):
    self.CheckWithErrors("""
      import enum
      class M(enum.Enum):  # wrong-arg-types
        def _generate_next_value_(name: int, start: int, count: int, last_values: int):
          return name
        A = enum.auto()
    """)

  def test_auto_generate_from_pyi_base(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class Base(enum.Enum):
          def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str: ...
      """,
      )
      self.Check(
          """
        import enum
        import foo
        class M(foo.Base):
          A = enum.auto()
        assert_type(M.A.value, "str")
      """,
          pythonpath=[d.path],
      )

  def test_auto_generate_from_pyi_base_staticmethod(self):
    # It's possible that _generate_next_value_ will appear in a type stub as a
    # staticmethod. This should not change how pytype handles it.
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class Base(enum.Enum):
          @staticmethod
          def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str: ...
      """,
      )
      self.Check(
          """
        import enum
        import foo
        class M(foo.Base):
          A = enum.auto()
        assert_type(M.A.value, "str")
      """,
          pythonpath=[d.path],
      )

  def test_auto_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class M(enum.Enum):
          A: int
          B: int
          def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str: ...
      """,
      )
      self.Check(
          """
        from typing import Callable
        from foo import M
        assert_type(M.A, "foo.M")
        assert_type(M.A.value, "int")
        assert_type(M.B.value, "int")
        assert_type(M._generate_next_value_, Callable[[str, int, int, list], str])
      """,
          pythonpath=[d.path],
      )

  def test_auto_flag(self):
    # Flag enums can be defined using bitwise ops, even when using auto.
    self.Check("""
      from enum import auto, Flag
      class Color(Flag):
        RED = auto()
        BLUE = auto()
        GREEN = auto()
        WHITE = RED | BLUE | GREEN
      assert_type(Color.RED, Color)
      assert_type(Color.BLUE, Color)
      assert_type(Color.GREEN, Color)
      assert_type(Color.WHITE, Color)
      assert_type(Color.RED.value, int)
      assert_type(Color.BLUE.value, int)
      assert_type(Color.GREEN.value, int)
      assert_type(Color.WHITE.value, int)
    """)

  def test_subclassing_simple(self):
    self.Check("""
      import enum
      class Base(enum.Enum): pass
      class M(Base):
        A = 1
      assert_type(M.A, "M")
      assert_type(M.A.name, "str")
      assert_type(M.A.value, "int")
      assert_type(M["A"], "M")
      assert_type(M(1), "M")
    """)

  def test_subclassing_pytd_simple(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class Base(enum.Enum): ...
        class M(Base):
          A: int
      """,
      )
      self.Check(
          """
        from foo import M
        assert_type(M.A, "foo.M")
        assert_type(M.A.name, "str")
        assert_type(M.A.value, "int")
        assert_type(M["A"], "foo.M")
        assert_type(M(1), "foo.M")
      """,
          pythonpath=[d.path],
      )

  def test_subclassing_pytd_cross_file(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class Base(enum.Enum): ...
      """,
      )
      self.Check(
          """
        from foo import Base
        class M(Base):
          A = 1
        assert_type(M.A, "M")
        assert_type(M.A.name, "str")
        assert_type(M.A.value, "int")
        assert_type(M["A"], "M")
        assert_type(M(1), "M")
      """,
          pythonpath=[d.path],
      )

  def test_subclassing_base_types(self):
    self.Check("""
      import enum

      class Base(enum.Enum): pass
      class M(Base):
        A = 1
      assert_type(M.A, M)
      assert_type(M.A.value, int)

      class F(float, enum.Enum):
        A = 1
      assert_type(F.A.value, float)

      class C(complex, enum.Enum): pass
      class C2(C):
        A = 1
      assert_type(C2.A.value, complex)

      class D(str, enum.Enum): pass
      class D1(D): pass
      class D2(D1):
        A = 1
      assert_type(D2.A.value, str)

      class X(D):
        def _generate_next_value(n, s, c, l):
          return float(c)
        A = enum.auto()
      assert_type(X.A.value, str)
    """)

  def test_subclassing_base_types_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class NoBase(enum.Enum): ...
        class StrBase(str, enum.Enum): ...
        class OnceRemoved(StrBase): ...
      """,
      )
      self.Check(
          """
        import enum
        import foo

        class M(foo.NoBase):
          A = 1
        assert_type(M.A.value, int)

        class N(float, foo.NoBase):
          A = 1
        assert_type(N.A.value, float)

        class O(foo.NoBase): pass
        class O2(O):
          A = 1
        assert_type(O2.A.value, int)

        class P(foo.StrBase):
          A = 1
        assert_type(P.A.value, str)

        class Q(foo.StrBase): pass
        class Q2(Q):
          A = 1
        assert_type(Q2.A.value, str)

        class R(foo.OnceRemoved):
          A = 1
        assert_type(R.A.value, str)

        class Y(foo.StrBase):
          def _generate_next_value(n, s, c, l):
            return float(c)
          A = enum.auto()
        assert_type(Y.A.value, str)
      """,
          pythonpath=[d.path],
      )

  def test_base_types(self):
    self.CheckWithErrors("""
      import enum
      from typing import Tuple
      class T(tuple, enum.Enum):
        A = (1, 2)
      assert_type(T.A.value, Tuple[int, ...])

      class S(str, enum.Enum):  # wrong-arg-types
        A = (1, 2)
    """)

  def test_submeta(self):
    self.Check("""
      import enum
      from typing import Any
      class Custom(enum.EnumMeta): pass
      class Base(enum.Enum, metaclass=Custom): pass
      class M(Base):
        A = 1
      # Ideally, this would be "M" and "int", but M is a dynamic enum.
      assert_type(M.A, Any)
      assert_type(M.A.value, Any)
      def take_m(m: M):
        print(m.value)
    """)

  def test_submeta_withmetaclass(self):
    # Ensure six.with_metaclass works with enums, even with a custom metaclass.
    self.Check("""
      import enum
      import six
      from typing import Any
      class Custom(enum.EnumMeta): pass
      class C(six.with_metaclass(Custom, enum.Enum)): pass
      class C2(C):
        A = 1
      # Ideally, this would be "C2" and "int", but C2 is a dynamic enum.
      assert_type(C2.A, Any)
      assert_type(C2.A.value, Any)
      def print_c(c: C):
        print(c.value)
    """)

  @test_base.skip("Fails due to __getattr__ in pytd.")
  def test_dynamic_attributes(self):
    self.CheckWithErrors("""
      import enum
      class Normal(enum.Enum):
        A = 1
      Normal.B  # attribute-error

      class Custom(enum.EnumMeta):
        def __new__(cls, name, bases, dct):
          for name in ["FOO", "BAR", "QUUX"]:
            dct[name] = name
          return super().__new__(cls, name, bases, dct)
      class Yes(enum.Enum, metaclass=Custom):
        A = 1
      Yes.B
    """)

  def test_dynamic_attributes_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class Normal:
          A: int
        class Custom(enum.EnumMeta):
          def __new__(cls, name, bases, dct): ...
        class Yes(enum.Enum, metaclass=Custom):
          A: int
      """,
      )
      self.CheckWithErrors(
          """
        import foo
        foo.Normal.B  # attribute-error
        foo.Yes.B
      """,
          pythonpath=[d.path],
      )

  def test_typical_subclassed_meta(self):
    # The typical pattern when subclassing EnumMeta is to create a base enum
    # using that metaclass, then subclass that enum in other files.
    # In this case, all enums that have the custom metaclass should be dynamic.
    with test_utils.Tempdir() as d:
      d.create_file(
          "base_enum.pyi",
          """
        import enum
        class CustomMeta(enum.EnumMeta): pass
        class Base(enum.Enum, metaclass=CustomMeta): pass
      """,
      )
      self.Check(
          """
        import base_enum
        class M(base_enum.Base):
          A = 1
        M.A
        M.B
        base_enum.Base.A
      """,
          pythonpath=[d.path],
      )

  def test_intenum_basic(self):
    self.Check("""
      import enum
      class I(enum.IntEnum):
        A = 1
    """)

  def test_flag_basic(self):
    self.Check("""
      import enum
      class F(enum.Flag):
        A = 1
    """)

  def test_intflag_basic(self):
    self.Check("""
      import enum
      class IF(enum.IntFlag):
        A = 1
    """)

  def test_strenum(self):
    self.Check("""
      import enum
      class MyEnum(enum.StrEnum):
        A = 'A'
      for x in MyEnum:
        assert_type(x, MyEnum)
    """)

  def test_unique_enum_in_dict(self):
    # Regression test for a recursion error in matcher.py
    self.assertNoCrash(
        self.Check,
        """
      import enum
      from typing import Dict, Generic, TypeVar

      Feature = enum.unique(enum.Enum)
      F = TypeVar('F', bound=Feature)

      class Features(Dict[F, bool], Generic[F]):
        def __setitem__(self, feature: F, on: bool):
          super(Features, self).__setitem__(feature, on)

      class _FeaturesParser(Generic[F]):
        def parse(self) -> Features[F]:
          result = Features()
          result[Feature('')] = True
          return result
    """,
    )

  def test_if_statement(self):
    # See b/195136939
    self.Check("""
      import enum
      class M(enum.Enum):
        A = 1
        B = 2

      def f(m: M) -> int:
        if m == M.A:
          x = 1
        elif m == M.B:
          x = 2
        else:
          x = 3
        return x + 1

      class A:
        def __init__(self, m: M):
          if m == M.A:
            self._x = 1
          elif m == M.B:
            self._x = 2

        def do(self):
          return self._x + 1
    """)

  def test_own_init_simple(self):
    self.Check("""
      from enum import Enum
      class M(Enum):
        A = 1
        def __init__(self, a):
          self._value_ = str(a + self._value_)

      assert_type(M.A, M)
      assert_type(M.A.value, str)
    """)

  def test_own_init_tuple_value(self):
    # https://docs.python.org/3/library/enum.html#planet
    self.Check("""
      from enum import Enum
      from typing import Tuple

      class Planet(Enum):
        MERCURY = (3.303e+23, 2.4397e6)
        VENUS   = (4.869e+24, 6.0518e6)
        EARTH   = (5.976e+24, 6.37814e6)
        MARS    = (6.421e+23, 3.3972e6)
        JUPITER = (1.9e+27,   7.1492e7)
        SATURN  = (5.688e+26, 6.0268e7)
        URANUS  = (8.686e+25, 2.5559e7)
        NEPTUNE = (1.024e+26, 2.4746e7)
        def __init__(self, mass, radius):
          self.mass = mass       # in kilograms
          self.radius = radius   # in meters
        @property
        def surface_gravity(self):
          # universal gravitational constant  (m3 kg-1 s-2)
          G = 6.67300E-11
          return G * self.mass / (self.radius * self.radius)

      assert_type(Planet.EARTH, Planet)
      assert_type(Planet.EARTH.name, str)
      assert_type(Planet.EARTH.value, Tuple[float, float])
      assert_type(Planet.EARTH.mass, float)
      assert_type(Planet.EARTH.radius, float)
      assert_type(Planet.EARTH.surface_gravity, float)
    """)

  def test_own_init_canonical(self):
    self.Check("""
      import enum

      class Protocol(enum.Enum):
        ssh = 22
        def __init__(self, port_number):
          self.port_number = port_number

      def get_port(protocol: str) -> int:
        return Protocol[protocol].port_number
    """)

  def test_own_init_errors(self):
    self.CheckWithErrors("""
      import enum
      class X(enum.Enum):  # missing-parameter
        A = 1
        def __init__(self, a, b, c):
          self.x = a + b + c
    """)

  def test_own_new_with_base_type(self):
    self.Check("""
      import enum

      class M(str, enum.Enum):
        def __new__(cls, value, a, b, c, d):
          obj = str.__new__(cls, [value])
          obj._value_ = value
          obj.a = a
          obj.b = b
          obj.c = c
          obj.d = d
          return obj

        A = ('a', 1, 2, 3, 4)
        B = ('b', 2, 3, 4, 5)


      def lookup(m: M):
        m = M(m)
    """)

  def test_own_member_new(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        from typing import Annotated, Any, Type, TypeVar

        _TOrderedEnum = TypeVar('_TOrderedEnum', bound=OrderedEnum)

        class OrderedEnum(enum.Enum):
            _pos: Annotated[int, 'property']
            @classmethod
            def __new_member__(cls: Type[_TOrderedEnum], value: Any) -> _TOrderedEnum: ...
      """,
      )
      self.Check(
          """
        import foo
        class Stage(foo.OrderedEnum):
          DEMAND = 1
          QUOTA = 2
          AGGREGATION = 3
          HEADROOM = 4
          ORDER = 5
      """,
          pythonpath=[d.path],
      )

  def test_dynamic_base_enum(self):
    self.Check("""
      import enum
      class DynBase(enum.Enum):
        _HAS_DYNAMIC_ATTRIBUTES = True

      class M(DynBase):
        A = 1
      M.B
    """)

  def test_dynamic_base_enum_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        class DynBase(enum.Enum):
          _HAS_DYNAMIC_ATTRIBUTES = True
      """,
      )
      self.Check(
          """
        import foo
        class M(foo.DynBase):
          A = 1
        M.B
      """,
          pythonpath=[d.path],
      )

  def test_instance_attrs_property_output(self):
    ty = self.Infer("""
      import enum
      class M(enum.Enum):
        A = 1
        def __init__(self, val):
          self.str_v = str(val)
        @property
        def combo(self) -> str:
          return f"{self.str_v}+{self.value}"
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      import enum
      from typing import Annotated, Literal
      class M(enum.Enum):
        A: Literal[1]
        combo: Annotated[str, 'property']
        str_v: Annotated[str, 'property']
        def __init__(self, val) -> None: ...
    """,
    )

  def test_instance_attrs_property_input(self):
    # Instance attributes are marked using @property.
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        from typing import Annotated
        class Fn(enum.Enum):
          A: int
          @property
          def x(self) -> str: ...
        class NoFn(enum.Enum):
          A: int
          x: Annotated[str, 'property']
      """,
      )
      self.CheckWithErrors(
          """
        import foo
        assert_type(foo.Fn.A.value, int)
        assert_type(foo.Fn.A.x, str)
        assert_type(foo.NoFn.A.value, int)
        assert_type(foo.NoFn.A.x, str)
        # These should be attribute errors but pytype does not differentiate
        # between class and instance attributes for PyTDClass.
        foo.Fn.x
        foo.NoFn.x
      """,
          pythonpath=[d.path],
      )

  def test_instance_attrs_canonical(self):
    # Test that canonical instances have instance attributes.
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        import enum
        from typing import Annotated
        class F(enum.Enum):
          A: str
          x = Annotated[int, 'property']
      """,
      )
      self.Check(
          """
        import enum
        import foo
        class M(enum.Enum):
          A = 'a'
          @property
          def x(self) -> int:
            return 1
        def take_f(f: foo.F):
          return f.x
        def take_m(m: M):
          return m.x
      """,
          pythonpath=[d.path],
      )

  def test_instance_attrs_self_referential(self):
    self.Check("""
      from dataclasses import dataclass
      from enum import Enum
      from typing import Optional

      @dataclass
      class O:
        thing: Optional["Thing"] = None

      class Thing(Enum):
        A = O()

        def __init__(self, o: O):
          self.b = o.thing
    """)

  def test_enum_bases(self):
    self.CheckWithErrors("""
      import enum
      class BadBaseOrder(enum.Enum, int):  # base-class-error
        A = 1
    """)

  def test_multiple_value_bindings(self):
    self.Check("""
      import enum
      class M(str, enum.Enum):
        A = (__any_object__ or '') + "1"
    """)

  def test_classvar_attributes_out(self):
    ty = self.Infer("""
      import enum
      class M(enum.Enum):
        A = 1
      M.class_attr = 2
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      import enum
      from typing import ClassVar, Literal
      class M(enum.Enum):
        A: Literal[1]
        class_attr: ClassVar[int]
    """,
    )

  def test_classvar_attributes_in(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        from typing import ClassVar
        import enum
        class M(enum.Enum):
          A: int
          class_attr: ClassVar[int]
      """,
      )
      self.Check(
          """
        from foo import M
        assert_type(M.A, M)
        assert_type(M.class_attr, int)
        assert_type(M.A.class_attr, int)
      """,
          pythonpath=[d.path],
      )

  def test_namedtuple_base_type(self):
    # This is a fun case for the base type. The value for A is an Item, but
    # the enum has a base type, which is also Item.
    # When there's a base type, the enum std lib calls the base's `__new__` to
    # create the values for the enums. So this looks like it should fail, except
    # __new__ is called like: Item.__new__(Item, *value).
    # Since value is a NamedTuple, it unpacks cleanly and a new Item is made.
    # So this test basically checks that the enum overlay correctly prepares
    # value as an argument to __new__.
    self.Check("""
      import enum
      from typing import NamedTuple
      class Item(NamedTuple):
        x: int
      class M(Item, enum.Enum):
        A = Item(1)
    """)

  def test_mixin_base_type(self):
    # Don't try to use a base class as a base_type if it's actually a mixin.
    self.Check("""
      import enum

      class Token:
        name: str
        value: str
        def __str__(self) -> str:
          return self.value

      # Each member of M is a Token, but Token.__init__ is never called.
      class M(Token, enum.Enum):
        A = "hello"

      def take_token(t: Token) -> str:
        return str(t)

      take_token(M.A)
      assert_type(M.A.value, str)
    """)

  def test_valid_members_functions(self):
    self.Check("""
      import enum
      from typing import Any, Callable
      class M(enum.Enum):
        A = lambda x: x
        B = 1
      assert_type(M.A, Callable[[Any], Any])
      assert_type(M.B, M)
    """)

  def test_valid_members_pytd_functions(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", "def a(x) -> None: ...")
      self.Check(
          """
        import enum
        from typing import Any, Callable
        import foo
        class M(enum.Enum):
          A = foo.a
          B = 1
        assert_type(M.A, Callable[[Any], None])
        assert_type(M.B, M)
      """,
          pythonpath=[d.path],
      )

  def test_valid_members_dundername(self):
    self.Check("""
      import enum
      class M(enum.Enum):
        __A__ = "hello"
        B = "world"
      assert_type(M.__A__, str)
      assert_type(M.B, M)
    """)

  def test_valid_members_dundername_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "foo.pyi",
          """
        enum: module
        class M(enum.Enum):
          __A__: str
          B: str
      """,
      )
      self.Check(
          """
        import foo
        assert_type(foo.M.__A__, str)
        assert_type(foo.M.B, foo.M)
      """,
          pythonpath=[d.path],
      )

  def test_valid_members_class(self):
    # Class are callables, but they aren't descriptors.
    self.Check("""
      import enum
      class Vclass: pass
      class M(enum.Enum):
        V = Vclass
      assert_type(M.V, M)
    """)

  def test_valid_members_class_descriptor(self):
    # Classes that have __get__ are descriptors though.
    # TODO(b/172045608): M.V should be Vclass, not str.
    self.Check("""
      import enum
      class Vclass:
        def __get__(self, *args, **kwargs):
          return "I'm a descriptor"
      class M(enum.Enum):
        V = Vclass
        I = Vclass()
      assert_type(M.V, str)  # Should be Vclass (b/172045608)
      assert_type(M.I, str)
    """)

  def test_not_supported_yet(self):
    self.CheckWithErrors("""
      import enum
      enum.ReprEnum  # not-supported-yet
    """)

  def test_members_with_value_attribute(self):
    with self.DepTree([(
        "foo.py",
        """
      import enum
      from typing import List

      class Attr:
        def __init__(self, values: list[str]):
          self.value = [v for v in values]
        @classmethod
        def make(cls, values: List[str]) -> 'Attr':
          return cls(values)

      class MyEnum(enum.Enum):
        A = Attr(['a'])
        B = Attr.make(['b'])

        @property
        def value_alias(self):
          return self.value
    """,
    )]):
      self.Check("""
        import foo
        assert_type(foo.MyEnum.A, foo.MyEnum)
        assert_type(foo.MyEnum.A.value_alias, foo.Attr)
        assert_type(foo.MyEnum.B, foo.MyEnum)
        assert_type(foo.MyEnum.B.value_alias, foo.Attr)
      """)

  def test_missing(self):
    self.Check("""
      import enum
      class E(enum.Enum):
        X = 42
        @classmethod
        def _missing_(cls, value: object) -> "E":
          return cls.X
      assert_type(E("FOO"), E)
    """)

  def test_missing_pyi(self):
    with self.DepTree([(
        "foo.pyi",
        """
      import enum
      class E(enum.Enum):
        X = 42
        @classmethod
        def _missing_(cls, value: object) -> E: ...
    """,
    )]):
      self.Check("""
        import foo
        assert_type(foo.E("FOO"), foo.E)
      """)


if __name__ == "__main__":
  test_base.main()
