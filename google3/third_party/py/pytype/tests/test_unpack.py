"""Test unpacking."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestUnpack(test_base.BaseTest):
  """Test unpacking of sequences via *xs."""

  def test_build_with_unpack_indefinite(self):
    ty = self.Infer("""
      from typing import List
      class A: pass
      a: List[A] = []
      b: List[str] = []
      c = [*a, *b, 1]
      d = {*a, *b, 1}
      e = (*a, *b, 1)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Set, Tuple, Union

      class A: ...
      a = ...  # type: List[A]
      b = ...  # type: List[str]
      c = ...  # type: List[Union[A, str, int]]
      d = ...  # type: Set[Union[A, str, int]]
      e = ...  # type: Tuple[Union[A, str, int], ...]
    """)

  def test_empty(self):
    ty, err = self.InferWithErrors("""
      a, *b = []  # bad-unpacking[e]
      c, *d = [1]
      *e, f = [2]
      g, *h, i = [1, 2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      a: Any
      b: List[nothing]
      c: int
      d: List[nothing]
      e: List[nothing]
      f: int
      g: int
      h: List[nothing]
      i: int
    """)
    self.assertErrorSequences(err, {"e": ["0 values", "1 variable"]})

  def test_unpack_indefinite_from_pytd(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        a: Tuple[int, ...]
        b: Tuple[str, ...]
      """)
      ty = self.Infer("""
        import foo
        c = (*foo.a, *foo.b)
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import Tuple, Union
      c: Tuple[Union[int, str], ...]
    """)

  def test_unpack_in_function_args(self):
    # TODO(b/63407497): Enabling --strict-parameter-checks leads to a
    # wrong-arg-types error on line 6.
    self.options.tweak(strict_parameter_checks=False)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        a: Tuple[int, ...]
        b: Tuple[str, ...]
      """)
      errors = self.CheckWithErrors("""
        import foo
        class A: pass
        def f(w: A, x: int, y: str, z: str):
          pass
        c = (*foo.a, *foo.b)
        f(A(), *c, "hello")
        f(A(), *c)
        f(*c, "hello")  # wrong-arg-types[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"w: A.*w: Union.int,.str."})

  def test_unpack_concrete_in_function_args(self):
    self.CheckWithErrors("""
      def f(x: int, y: str):
        pass
      a = (1, 2)
      f(*a)  # wrong-arg-types
      f(1, *("x", "y"))  # wrong-arg-count
    """)

  def test_match_typed_starargs(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        def f(x:int, *args: str): ...
        a: list
        b: Any
      """)
      self.Check("""
        import foo
        foo.f(1, *foo.a)
        foo.f(1, *foo.b)
        foo.f(*foo.a)
      """, pythonpath=[d.path])

  def test_path_join(self):
    self.Check("""
      import os
      xs: list
      os.path.join('x', *xs)
    """)

  def test_overloaded_function(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        @overload
        def f(x:int, *args: str): ...
        @overload
        def f(x:str, *args: str): ...
        a: list
        b: Any
      """)
      self.Check("""
        import foo
        foo.f(1, *foo.a)
        foo.f(1, *foo.b)
        foo.f(*foo.a)
      """, pythonpath=[d.path])

  def test_unpack_kwargs_without_starargs(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Dict, Optional
        def f(x: int, y: str, z: bool = True, a: Optional[object] = None ): ...
        a: Dict[str, Any]
        b: dict
      """)
      self.Check("""
        import foo
        foo.f(1, 'a', **foo.a)
        foo.f(1, 'a', **foo.b)
        def g(x: int, y: str, **kwargs):
          foo.f(x, y, **kwargs)
      """, pythonpath=[d.path])

  def test_set_length_one_nondeterministic_unpacking(self):
    self.Check("""
    (x,) = {'a'}
    """)

  def test_frozenset_length_one_nondeterministic_unpacking(self):
    self.Check("""
    (x,) = frozenset(['a'])
    """)

  def test_set_nondeterministic_unpacking(self):
    self.CheckWithErrors("""
    (x, y) = {'a', 'b'}   # bad-unpacking
    """)

  def test_frozenset_nondeterministic_unpacking(self):
    self.CheckWithErrors("""
    (x, y) = frozenset(['a', 'b'])   # bad-unpacking
    """)

  def test_str(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Optional, Text
        class A: ...
        def f(
            x: Text,
            y: int,
            k: bool = ...,
            l: Optional[Text] = ...,
            m: Optional[A] = ...,
        ) -> None: ...
      """)
      self.Check("""
        import foo
        from typing import Text
        def g(self, x: str, **kwargs) -> None:
          foo.f(x, 1, **kwargs)
      """, pythonpath=[d.path])

  def test_unknown_length_tuple(self):
    self.Check("""
      from typing import Tuple
      def f(*args: str):
        pass
      x: Tuple[str, ...]
      f(*x, 'a', 'b', 'c')
    """)

  def test_dont_unpack_iterable(self):
    # Check that we don't treat x as a splat in the call to f() just because
    # it's an indefinite iterable.
    self.Check("""
      class Foo(list):
        pass

      def f(x: Foo, y: int, z: bool = True):
        pass

      def g(x: Foo, **kwargs):
        f(x, 10, **kwargs)
    """)

  def test_erroneous_splat(self):
    # Don't crash on an unnecessary splat.
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Sequence
        def f(x: Sequence[Any], y: str): ...
        def g(x: Sequence[Any], y: Sequence[str]): ...
      """)
      self.CheckWithErrors("""
        import itertools
        from typing import List
        import foo
        x: list
        y: List[int]
        foo.f(*x, "a")
        foo.f(*x, *y)  # wrong-arg-types
        foo.g(*x, *y)  # wrong-arg-types
        a = itertools.product(*x, *y)
      """, pythonpath=[d.path])

  def test_unpack_namedtuple(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(a, b, c, d, e, f): ...
      """)
      self.Check("""
        import collections
        import foo
        X = collections.namedtuple('X', ('a', 'b', 'c'))
        foo.f(*X(0, 1, 2), 3, 4, 5)

        def g() -> X:
          return X(0, 1, 2)
        p = X(*g())
        q = X(*g())
        f = X(*(x - y for x, y in zip(p, q)))
      """, pythonpath=[d.path])

  def test_posargs_and_namedargs(self):
    self.Check("""
      def f(x, y=1, z=2, a=3):
        pass

      def g(b=None):
        f(*b, y=2, z=3)
    """)

  def test_dont_unpack_into_optional(self):
    self.Check("""
      def f(x: int, y: int, z: str = ...):
        pass

      def g(*args: int):
        f(*args)
    """)

  def test_multiple_tuple_bindings(self):
    ty = self.Infer("""
      from typing import Tuple

      class C:
        def __init__(self, p, q):
          self.p = p
          self.q = q

      x = [('a', 1), ('c', 3j), (2, 3)]
      y = [C(*a).q for a in x]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Tuple, Union
      class C:
        p: Any
        q: Any
        def __init__(self, p, q): ...
      x: List[Tuple[Union[int, str], Union[complex, int]]]
      y: List[Union[complex, int]]
    """)

  def test_type_parameter_instance(self):
    ty = self.Infer("""
      from typing import Dict, Tuple

      class Key:
        pass
      class Value:
        pass

      def foo(x: Dict[Tuple[Key, Value], str]):
        ret = []
        for k, v in sorted(x.items()):
          key, value = k
          ret.append(key)
        return ret
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Tuple

      class Key: ...
      class Value: ...

      def foo(x: Dict[Tuple[Key, Value], str]) -> List[Key]: ...
    """)

  def test_unpack_any_subclass_instance(self):
    # Test for a corner case in b/261564270
    with self.DepTree([("foo.pyi", """
      from typing import Any

      Base: Any
    """)]):
      self.Check("""
        import foo
        class A(foo.Base):
          @classmethod
          def make(cls, hello, world):
            return cls(hello, world)

        a = A.make(1, 2)
        b = A.make(*a)
      """)


if __name__ == "__main__":
  test_base.main()
