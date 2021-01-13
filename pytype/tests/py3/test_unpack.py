"""Test unpacking."""

from pytype import file_utils
from pytype.tests import test_base


class TestUnpack(test_base.TargetPython3FeatureTest):
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

  def test_unpack_indefinite_from_pytd(self):
    with file_utils.Tempdir() as d:
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
      from typing import Tuple, Union
      foo: module
      c: Tuple[Union[int, str], ...]
    """)

  def test_unpack_in_function_args(self):
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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

  def test_str(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Optional, Text
        class A: ...
        def f(
            x: Text,
            y: int,
            k: bool = ...,
            l: Optional[Text] = ...,
            m: Optional[A] = ...,
        ) -> None
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
    with file_utils.Tempdir() as d:
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
    with file_utils.Tempdir() as d:
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


test_base.main(globals(), __name__ == "__main__")
