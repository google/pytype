"""Tests for recursive types."""

from pytype.tests import test_base


class UsageTest(test_base.BaseTest):
  """Tests usage of recursive types in source code."""

  def test_parameter(self):
    self.Check("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      def f(x: Foo):
        pass
    """)

  def test_comment(self):
    self.Check("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      x = 'hello'  # type: Foo
    """)

  def test_alias(self):
    self.Check("""
      from typing import Any, Iterable, Union
      X = Union[Any, Iterable['X']]
      Y = Union[Any, X]
    """)

  def test_generic_alias(self):
    src = """
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      Tree = Union[T, List['Tree{inner_parameter}']]
      def f(x: Tree[int]): ...
    """
    for inner_parameter in ("", "[T]"):
      with self.subTest(inner_parameter=inner_parameter):
        self.Check(src.format(inner_parameter=inner_parameter))

  def test_generic_alias_rename_type_params(self):
    self.CheckWithErrors("""
      from typing import List, Set, TypeVar, Union
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = Union[T1, Set[T2], List['X[T2, T1]']]
      Y = X[int, str]
      ok1: Y = 0
      ok2: Y = {''}
      ok3: Y = ['']
      ok4: Y = [{0}]
      bad1: Y = ''  # annotation-type-mismatch
      bad2: Y = {0}  # annotation-type-mismatch
      bad3: Y = [0]  # annotation-type-mismatch
      bad4: Y = [{''}]  # annotation-type-mismatch
    """)


class MatchTest(test_base.BaseTest):
  """Tests abstract matching of recursive types."""

  def test_type(self):
    errors = self.CheckWithErrors("""
      from typing import List
      X = List['X']
      x = []
      x.append(x)
      ok: X = x
      bad1: X = [0]  # annotation-type-mismatch[e]
      bad2: X = [[0]]  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "List[X]", "Assignment", "List[int]"]})

  def test_value(self):
    errors = self.CheckWithErrors("""
      from typing import Any, List
      X = List['X']
      x: X = None
      ok1: List[Any] = x
      ok2: List[X] = x
      bad: List[int] = x  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "List[int]", "Assignment", "List[X]"]})

  def test_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set
      X1 = List['X1']
      X2 = List['X2']
      Bad = Set['Bad']
      x: X1 = None
      ok1: X1 = x
      ok2: X2 = x  # ok because X1 and X2 are structurally equivalent
      bad: Bad = x  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Set[Bad]", "Assignment", "List[X1]"]})

  def test_union_as_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Union
      X = Union[str, List['X']]
      ok1: X = ''
      ok2: X = ['']
      ok3: X = [['']]
      bad1: X = 0  # annotation-type-mismatch[e]
      bad2: X = [0]  # annotation-type-mismatch
      bad3: X = [[0]]  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Union[List[X], str]", "Assignment", "int"],
    })

  def test_union_as_value(self):
    errors = self.CheckWithErrors("""
      from typing import Any, List, Union
      X = Union[str, List['X']]
      x: X = None
      ok: Union[str, List[Any]] = x
      bad1: Union[int, List[Any]] = x  # annotation-type-mismatch[e]
      bad2: Union[str, List[int]] = x  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Union[int, list]",
              "Assignment", "Union[List[X], str]"]})

  def test_union_as_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set, Union
      X1 = Union[str, List['X1']]
      X2 = Union[str, List['X2']]
      X3 = Union[int, Union[List['X3'], str]]
      Bad1 = Union[str, Set['Bad1']]
      Bad2 = Union[int, List['Bad2']]
      Bad3 = Union[int, Union[List['Bad3'], int]]
      x: X1 = None
      ok1: X1 = x
      ok2: X2 = x  # ok because X1 and X2 are structurally equivalent
      ok3: X3 = x  # ok because (the equivalent of) X1 is contained in X3
      bad1: Bad1 = x  # annotation-type-mismatch[e]
      bad2: Bad2 = x  # annotation-type-mismatch  # annotation-type-mismatch
      bad3: Bad3 = x  # annotation-type-mismatch  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Union[Set[Bad1], str]",
              "Assignment", "List[X1]",
              "In assignment", "Union[List[X1], str]"],
    })

  def test_contained_union(self):
    self.CheckWithErrors("""
      from typing import List, Union
      X = List[Union[str, List['X']]]
      Y = List[Union[int, List['Y']]]
      x: X = None
      ok: X = x
      bad: Y = x  # annotation-type-mismatch
    """)

  def test_union_no_base_case(self):
    self.CheckWithErrors("""
      from typing import Any, List, Set, Union
      X = Union[List['X'], Set['X']]
      x1: X = None
      x2 = []
      x2.append(x2)
      x3 = set()
      x3.add(x3)
      ok1: X = x1
      ok2: X = x2
      ok3: X = x3
      bad1: X = {0}  # annotation-type-mismatch
      bad2: Set[Any] = x1  # annotation-type-mismatch
    """)

  def test_heterogeneous_namedtuple(self):
    self.CheckWithErrors("""
      from typing import NamedTuple, Tuple, TypeVar, Union

      class Ok(NamedTuple):
        x: int
        y: str

      class No(NamedTuple):
        x: float
        y: str

      T = TypeVar('T')
      X = Union[tuple['X[T]', ...], T]

      x1: X[Union[int, str]] = Ok(x=0, y='1')
      x2: X[Union[int, str]] = No(x=0.0, y='1')  # annotation-type-mismatch
    """)


class InferenceTest(test_base.BaseTest):
  """Tests inference of recursive types."""

  def test_basic(self):
    ty = self.Infer("""
      from typing import List
      Foo = List['Foo']
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      Foo = List[Foo]
    """)

  def test_mutual_recursion(self):
    ty = self.Infer("""
      from typing import List
      X = List['Y']
      Y = List['X']
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      X = List[Y]
      Y = List[List[Y]]
    """)

  def test_parameterization(self):
    ty = self.Infer("""
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = List['Y[int]']
      Y = Union[T, List['Y']]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = List[_Y_LBAR_int_RBAR]
      Y = Union[T, List[Y]]
      _Y_LBAR_int_RBAR = Union[int, List[_Y_LBAR_int_RBAR]]
    """)

  def test_parameterization_with_inner_parameter(self):
    ty = self.Infer("""
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = Union[T, List['X[T]']]
      Y = List[X[int]]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = Union[T, List[_X_LBAR_T_RBAR]]
      Y = List[Union[int, List[_X_LBAR_T_RBAR_LBAR_int_RBAR]]]
      _X_LBAR_T_RBAR = Union[T, List[_X_LBAR_T_RBAR]]
      _X_LBAR_T_RBAR_LBAR_int_RBAR = Union[int, List[
          _X_LBAR_T_RBAR_LBAR_int_RBAR]]
    """)

  def test_branching(self):
    ty = self.Infer("""
      from typing import Mapping, TypeVar, Union

      K = TypeVar('K')
      V = TypeVar('V')

      StructureKV = Union[Mapping[K, 'StructureKV[K, V]'], V]

      try:
        Structure = StructureKV[str, V]
      except TypeError:
        Structure = Union[Mapping[str, 'Structure[V]'], V]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Mapping, TypeVar, Union

      K = TypeVar('K')
      V = TypeVar('V')

      StructureKV = Union[Mapping[K, _StructureKV_LBAR_K_COMMA_V_RBAR], V]

      # The two Mapping values are redundant, but pytype isn't smart enough to
      # deduplicate them.
      Structure = Union[
          Mapping[str, Union[
              _StructureKV_LBAR_K_COMMA_V_RBAR_LBAR_str_COMMA_V_RBAR,
              _Structure_LBAR_V_RBAR]],
          V,
      ]

      _StructureKV_LBAR_K_COMMA_V_RBAR = Union[Mapping[
          K, _StructureKV_LBAR_K_COMMA_V_RBAR], V]
      _StructureKV_LBAR_K_COMMA_V_RBAR_LBAR_str_COMMA_V_RBAR = Union[Mapping[
          str, _StructureKV_LBAR_K_COMMA_V_RBAR_LBAR_str_COMMA_V_RBAR], V]
      _Structure_LBAR_V_RBAR = Union[Mapping[str, _Structure_LBAR_V_RBAR], V]
    """)


class PyiTest(test_base.BaseTest):
  """Tests recursive types defined in pyi files."""

  pickle = False

  def DepTree(self, deps):
    return super().DepTree([d + ({"pickle": self.pickle},) for d in deps])

  def test_basic(self):
    with self.DepTree([("foo.py", """
      from typing import List
      X = List['X']
    """)]):
      self.CheckWithErrors("""
        import foo
        from typing import Any, Set, List
        x: foo.X = None
        ok1: foo.X = x
        ok2: List[Any] = x
        bad1: List[str] = x  # annotation-type-mismatch
        bad2: Set[Any] = x  # annotation-type-mismatch
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing import List, Union
      X = Union[int, List['X']]
    """)]):
      ty = self.Infer("""
        import foo
        X = foo.X
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import List, Union
      X = Union[int, List[foo.X]]
    """)

  def test_reingest_and_use(self):
    with self.DepTree([("foo.py", """
      from typing import List, Union
      X = Union[int, List['X']]
    """)]):
      self.CheckWithErrors("""
        import foo
        from typing import Any, List, Set, Union
        X = foo.X
        x_local: X = None
        x_imported: foo.X = None
        ok1: X = x_local
        ok2: Union[int, List[Any]] = x_local
        ok3: foo.X = x_local
        ok4: X = x_imported
        bad1: Union[int, List[int]] = x_local  # annotation-type-mismatch
        bad2: Union[int, Set[Any]] = x_local  # annotation-type-mismatch
      """)

  def test_reingest_n_times(self):
    deps = [("foo1.py", """
      from typing import List
      X = List['X']
    """)]
    for i in range(3):
      deps.append((f"foo{i+2}.py", f"""
        import foo{i+1}
        X = foo{i+1}.X
      """))
    with self.DepTree(deps):
      self.CheckWithErrors("""
        import foo2
        import foo4
        from typing import Any, List, Set
        X = foo4.X
        # Test local X
        x_local: X = None
        ok1: X = x_local
        bad1: Set[Any] = x_local  # annotation-type-mismatch
        # Test imported foo4.X
        x_foo4: foo4.X = None
        ok2: foo4.X = x_foo4
        bad2: Set[Any] = x_foo4  # annotation-type-mismatch
        # Test interactions
        x_foo2: foo2.X = None
        ok3: foo2.X = x_local
        ok4: foo2.X = x_foo4
        ok5: foo4.X = x_local
        ok6: foo4.X = x_foo2
        ok7: X = x_foo2
        ok8: X = x_foo4
      """)

  def test_mutually_recursive(self):
    with self.DepTree([("foo.py", """
      from typing import List
      X = List['Y']
      Y = List[X]
    """)]):
      self.CheckWithErrors("""
        import foo
        from typing import Any, List
        x: foo.X = None
        ok: List[List[Any]] = x
        bad: List[List[int]] = x  # annotation-type-mismatch
      """)

  def test_parameterization(self):
    foo_src = """
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = Union[T, List['X{inner_parameter}']]
      Y = X[int]
    """
    for inner_parameter in ("", "[T]"):
      with self.subTest(inner_parameter=inner_parameter):
        with self.DepTree([
            ("foo.py", foo_src.format(inner_parameter=inner_parameter))]):
          errors = self.CheckWithErrors("""
            import foo
            ok1: foo.X[str] = ['']
            ok2: foo.Y = [0]
            bad1: foo.X[str] = [0]  # annotation-type-mismatch
            bad2: foo.Y = ['']  # annotation-type-mismatch[e]
          """)
          self.assertErrorSequences(errors, {
              "e": ["Annotation: Union[List[foo.X[int]], int]",
                    "Assignment: List[str]"]})

  def test_parameterize_and_forward(self):
    with self.DepTree([("foo.py", """
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = Union[T, List['X[T]']]
    """), ("bar.py", """
      import foo
      Y = foo.X[str]
    """)]):
      self.Check("""
        import bar
        assert_type(bar.Y, "Type[Union[List[bar.foo.X[T][str]], str]]")
      """)

  def test_dataclass(self):
    with self.DepTree([("foo.py", """
      import dataclasses
      from typing import Dict, List, Optional, Union
      X = Union[List[str], 'X']
      Y = Dict[str, X]
      @dataclasses.dataclass
      class Foo:
        y: Optional[Y] = None
    """)]):
      self.Check("""
        import foo
        def f(x: foo.Foo):
          pass
      """)

  def test_import_multiple_aliases(self):
    with self.DepTree([("foo.py", """
      from typing import List, Union, TypeVar
      T = TypeVar('T')
      X = Union[T, List['X[T]']]
    """), ("bar.py", """
      import foo
      BarX = foo.X
    """), ("baz.py", """
      import foo
      BazX = foo.X
    """)]):
      self.Check("""
        import bar
        import baz
        # Reference BarX, then BazX, then BarX again to test that we've fixed an
        # odd bug where importing an alias in a different namespace changed the
        # scopes of cached TypeVars.
        def f1(x: bar.BarX[str]): ...
        def f2(x: baz.BazX[str]): ...
        def f3(x: bar.BarX[str]): ...
      """)

  def test_formal_alias(self):
    with self.DepTree([("foo.py", """
      from typing import List, Union, TypeVar
      T = TypeVar('T')
      X = Union[T, List['X[T]']]
    """)]):
      self.Check("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        def f(x: foo.X[T], y: T):
          pass
      """)

  def test_use_branched_alias(self):
    with self.DepTree([("foo.py", """
      from typing import Mapping, Sequence, TypeVar, Union
      K = TypeVar('K')
      V = TypeVar('V')
      StructureKV = Union[
          Sequence['StructureKV[K, V]'],
          Mapping[K, 'StructureKV[K, V]'],
          V,
      ]
      try:
        Structure = StructureKV[int, V]
      except TypeError:
        Structure = Union[
            Sequence['Structure[V]'], Mapping[int, 'Structure[V]'], V]
    """)]):
      self.Check("""
        import foo
        from typing import Any
        X = foo.Structure[Any]
        def f(x: X):
          y = x[0]
          return y[1]
      """)


class PickleTest(PyiTest):
  """Test recursive types defined in pickled pyi files."""

  pickle = True


if __name__ == "__main__":
  test_base.main()
