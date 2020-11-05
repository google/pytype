"""Tests for if-splitting."""

from pytype import file_utils
from pytype.tests import test_base


class SplitTest(test_base.TargetIndependentTest):
  """Tests for if-splitting."""

  def test_restrict_none(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else None

        if y:
          # y can't be None here!
          return y
        else:
          return 123
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[int, str]: ...
    """)

  def test_restrict_true(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else True

        if y:
          return 123
        else:
          return y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[int, str]: ...
    """)

  def test_related_variable(self):
    ty = self.Infer("""
      def foo(x):
        # y is Union[str, None]
        # z is Union[float, True]
        if x:
          y = str(x)
          z = 1.23
        else:
          y = None
          z = True

        if y:
          # We only return z when y is true, so z must be a float here.
          return z

        return 123
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[float, int]: ...
    """)

  def test_nested_conditions(self):
    ty = self.Infer("""
      def foo(x1, x2):
        y1 = str(x1) if x1 else 0

        if y1:
          if x2:
            return y1  # The y1 condition is still active here.

        return "abc"
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x1, x2) -> str: ...
    """)

  def test_remove_condition_after_merge(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else None

        if y:
          # y can't be None here.
          z = 123
        # But y can be None here.
        return y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[None, str]: ...
    """)

  def test_unsatisfiable_condition(self):
    # Check both sides of an "if".  If unsatisfiable code is executed then
    # it will result in an error due to unknown_method() and widen the return
    # signature to a Union.
    #
    # If a constant such as 0 or 1 is directly used as the condition of an
    # "if", then the compiler won't even generate bytecode for the branch
    # that isn't taken.  Thus the constant is first assigned to a variable and
    # the variable is used as the condition.  This is enough to fool the
    # compiler but pytype still figures out that one path is dead.
    ty = self.Infer("""
      def f1(x):
        c = 0
        if c:
          unknown_method()
          return 123
        else:
          return "hello"

      def f2(x):
        c = 1
        if c:
          return 123
        else:
          unknown_method()
          return "hello"

      def f3(x):
        c = 0
        if c:
          return 123
        else:
          return "hello"

      def f4(x):
        c = 1
        if c:
          return 123
        else:
          return "hello"
    """)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> str: ...
      def f2(x) -> int: ...
      def f3(x) -> str: ...
      def f4(x) -> int: ...
    """)

  def test_sources_propagated_through_call(self):
    ty = self.Infer("""
      class Foo(object):
        def method(self):
          return 1

      class Bar(object):
        def method(self):
          return "x"

      def foo(x):
        if x:
          obj = Foo()
        else:
          obj = Bar()

        if isinstance(obj, Foo):
          return obj.method()
        return None
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Foo(object):
        def method(self) -> int: ...

      class Bar(object):
        def method(self) -> str: ...

      def foo(x) -> Union[None, int]: ...
    """)

  def test_short_circuit(self):
    # Unlike normal if statement, the and/or short circuit logic does
    # not appear to be optimized away by the compiler.  Therefore these
    # simple tests do in fact execute if-splitting logic.
    ty = self.Infer("""
      def int_t(x): return 1 or x
      def int_f(x): return 0 and x
      def str_t(x): return "s" or x
      def str_f(x): return "" and x
      def bool_t(x): return True or x
      def bool_f(x): return False and x
      def tuple_t(x): return (1, ) or x
      def tuple_f(x): return () and x
      def dict_f(x): return {} and x
      def list_f(x): return [] and x
      def set_f(x): return set() and x
      def frozenset_f(x): return frozenset() and x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Tuple
      def int_t(x) -> int: ...
      def int_f(x) -> int: ...
      def str_t(x) -> str: ...
      def str_f(x) -> str: ...
      def bool_t(x) -> bool: ...
      def bool_f(x) -> bool: ...
      def tuple_t(x) -> Tuple[int]: ...
      def tuple_f(x) -> Tuple[()]: ...
      def dict_f(x) -> Dict[nothing, nothing]: ...
      def list_f(x) -> List[nothing]: ...
      def set_f(x) -> set[nothing]: ...
      def frozenset_f(x) -> frozenset[nothing]: ...
    """)

  def test_dict(self):
    # Dicts start out as empty, which is compatible with False and not
    # compatible with True.  Any operation that possibly adds an item will
    # make the dict ambiguous - compatible with both True and False.
    ty = self.Infer("""
      def f1():
        d = {}
        return 123 if d else "hello"

      def f2(x):
        d = {}
        d[x] = x
        return 123 if d else "hello"
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f1() -> str: ...
      def f2(x) -> Union[int, str]: ...
    """)

  def test_dict_update(self):
    ty = self.Infer("""
      def f1():
        d = {}
        d.update({})
        return 123 if d else "hello"

      def f2():
        d = {}
        d.update({"a": 1})
        return 123 if d else "hello"

    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f1() -> str: ...
      def f2() -> int: ...
    """)

  def test_dict_update_from_kwargs(self):
    ty = self.Infer("""
      def f1():
        d = {}
        d.update()
        return 123 if d else "hello"

      def f2():
        d = {}
        d.update(a=1)
        return 123 if d else "hello"
    """)
    self.assertTypesMatchPytd(ty, """
      def f1() -> str: ...
      def f2() -> int: ...
    """)

  def test_bad_dict_update(self):
    ty = self.Infer("""
      def f1():
        d = {}
        d.update({"a": 1}, {"b": 2})
        return 123 if d else "hello"

      def f2():
        d = {}
        d.update({"a": 1}, {"b": 2}, c=3)
        return 123 if d else "hello"
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f1() -> Union[str, int]: ...
      def f2() -> Union[str, int]: ...
    """)

  def test_isinstance(self):
    ty = self.Infer("""
      # Always returns a bool.
      def sig(x): return isinstance(x, str)
      # Cases where isinstance() can be determined, if-split will
      # narrow the return to a single type.
      def d1(): return "y" if isinstance("s", str) else 0
      def d2(): return "y" if isinstance("s", object) else 0
      def d3(): return "y" if isinstance("s", int) else 0
      def d4(): return "y" if isinstance("s", (float, str)) else 0
      # Cases where isinstance() is ambiguous.
      def a1(x): return "y" if isinstance(x, str) else 0
      def a2(x):
        cls = int if __random__ else str
        return "y" if isinstance("a", cls) else 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def sig(x) -> bool: ...
      def d1() -> str: ...
      def d2() -> str: ...
      def d3() -> int: ...
      def d4() -> str: ...
      def a1(x) -> Union[int, str]: ...
      def a2(x) -> Union[int, str]: ...
    """)

  def test_is_subclass(self):
    ty = self.Infer("""
      # Always return a bool
      def sig(x): return issubclass(x, object)
      # Classes for testing
      class A(object): pass
      class B(A): pass
      class C(object): pass
      # Check the if-splitting based on issubclass
      def d1(): return "y" if issubclass(B, A) else 0
      def d2(): return "y" if issubclass(B, object) else 0
      def d3(): return "y" if issubclass(B, C) else 0
      def d4(): return "y" if issubclass(B, (C, A)) else 0
      def d5(): return "y" if issubclass(B, ((C, str), A, (int, object))) else 0
      def d6(): return "y" if issubclass(B, ((C, str), int, (float, A))) else 0
      # Ambiguous results
      def a1(x): return "y" if issubclass(x, A) else 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def sig(x) -> bool: ...
      def d1() -> str: ...
      def d2() -> str: ...
      def d3() -> int: ...
      def d4() -> str: ...
      def d5() -> str: ...
      def d6() -> str: ...
      def a1(x) -> Union[int, str]: ...

      class A(object):
        pass

      class B(A):
        pass

      class C(object):
        pass
      """)

  def test_hasattr_builtin(self):
    ty = self.Infer("""
      # Always returns a bool.
      def sig(x): return hasattr(x, "upper")
      # Cases where hasattr() can be determined, if-split will
      # narrow the return to a single type.
      def d1(): return "y" if hasattr("s", "upper") else 0
      def d2(): return "y" if hasattr("s", "foo") else 0
      # We should follow the chain of superclasses
      def d3(): return "y" if hasattr("s", "__repr__") else 0
      # Cases where hasattr() is ambiguous.
      def a1(x): return "y" if hasattr(x, "upper") else 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def sig(x) -> bool: ...
      def d1() -> str: ...
      def d2() -> int: ...
      def d3() -> str: ...
      def a1(x) -> Union[int, str]: ...
    """)

  def test_split(self):
    ty = self.Infer("""
      def f2(x):
        if x:
          return x
        else:
          return 3j

      def f1(x):
        y = 1 if x else 0
        if y:
          return f2(y)
        else:
          return None
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Optional, TypeVar, Union
      _T0 = TypeVar("_T0")
      def f2(x: _T0) -> Union[_T0, complex]: ...
      def f1(x) -> Optional[int]: ...
    """)

  def test_dead_if(self):
    ty = self.Infer("""
      def foo(x):
        x = None
        if x is not None:
          x.foo()
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> None: ...
    """)

  def test_unary_not(self):
    ty = self.Infer("""
      def not_t(x):
        x = None
        if not x:
          return 1
        else:
          x.foo()
          return "a"

      def not_f(x):
        x = True
        if not x:
          x.foo()
          return 1
        else:
          return "a"

      def not_ambiguous(x):
        if not x:
          return 1
        else:
          return "a"

    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def not_t(x) -> int: ...
      def not_f(x) -> str: ...
      def not_ambiguous(x) -> Union[int, str]: ...
    """)

  def test_isinstance_object_without_class(self):
    ty = self.Infer("""
      def foo(x):
        return 1 if isinstance(dict, type) else "x"
    """)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> int: ...
    """)

  def test_double_assign(self):
    self.Check("""
      x = 1
      x = None
      if x is not None:
        x.foo()
    """)

  def test_infinite_loop(self):
    self.Check("""
      class A(object):
        def __init__(self):
          self.members = []
        def add(self):
          self.members.append(42)

      class B(object):
        def __init__(self):
          self._map = {}
        def _foo(self):
          self._map[0] = A()
          while True:
            pass
        def add2(self):
          self._map[0].add()

      b = B()
      b._foo()
      b.add2()
    """)

  def test_dict_contains(self):
    """Assert that we can determine whether a dict contains a key."""
    self.Check("""
      d1 = {"x": 42}
      if "x" in d1:
        d1["x"]
      else:
        d1["nonsense"]  # Dead code

      d2 = {}
      if "x" in d2:
        d2["nonsense"]  # Dead code

      d3 = {__any_object__: __any_object__}
      if "x" in d3:
        d3["x"]
      else:
        d3["y"]
    """)

  def test_dict_does_not_contain(self):
    """Assert that we can determine whether a dict does not contain a key."""
    self.Check("""
      d1 = {"x": 42}
      if "x" not in d1:
        d1["nonsense"]  # Dead code
      else:
        d1["x"]

      d2 = {}
      if "x" not in d2:
        pass
      else:
        d2["nonsense"]  # Dead code

      d3 = {__any_object__: __any_object__}
      if "x" not in d3:
        d3["y"]
      else:
        d3["x"]
    """)

  def test_dict_maybe_contains(self):
    """Test that we can handle more complex cases involving dict membership."""
    ty = self.Infer("""
      if __random__:
        x = {"a": 1, "b": 2}
      else:
        x = {"b": 42j}
      if "a" in x:
        v1 = x["b"]
      if "a" not in x:
        v2 = x["b"]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      x = ...  # type: Dict[str, Union[int, complex]]
      v1 = ...  # type: int
      v2 = ...  # type: complex
    """)

  def test_contains_coerce_to_bool(self):
    ty = self.Infer("""
      class A(object):
        def __contains__(self, x):
          return 1
      class B(object):
        def __contains__(self, x):
          return 0
      x1 = "" if "a" in A() else u""
      x2 = 3 if "a" not in A() else 42j
      y1 = 3.14 if "b" in B() else 16j
      y2 = True if "b" not in B() else 4.2
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __contains__(self, x) -> int: ...
      class B(object):
        def __contains__(self, x) -> int: ...
      x1 = ...  # type: str
      x2 = ...  # type: complex
      y1 = ...  # type: complex
      y2 = ...  # type: bool
    """)

  def test_skip_over_midway_if(self):
    ty = self.Infer("""
      def f(r):
        y = "foo"
        if __random__:
          x = True
        else:
          x = False
        if x:
          return y
        else:
          return None
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      def f(r) -> Optional[str]: ...
    """)

  def test_dict_eq(self):
    ty = self.Infer("""
      if __random__:
        x = {"a": 1}
        z = 42
      else:
        x = {"b": 1}
        z = 42j
      y = {"b": 1}
      if x == y:
        v1 = z
      if x != y:
        v2 = z
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      x = ...  # type: Dict[str, int]
      y = ...  # type: Dict[str, int]
      z = ...  # type: Union[int, complex]
      v1 = ...  # type: complex
      v2 = ...  # type: Union[int, complex]
    """)

  def test_tuple_eq(self):
    ty = self.Infer("""
      if __random__:
        x = (1,)
        z = ""
      else:
        x = (1, 2)
        z = 3.14
      y = (1, 2)
      if x == y:
        v1 = z
      if x != y:
        v2 = z
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      x: Tuple[int, ...]
      y: Tuple[int, int]
      z: Union[str, float]
      v1: float
      v2: str
    """)

  def test_primitive_eq(self):
    ty = self.Infer("""
      if __random__:
        x = "a"
        z = 42
      else:
        x = "b"
        z = 3.14
      y = "a"
      if x == y:
        v1 = z
      if x != y:
        v2 = z
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      x = ...  # type: str
      y = ...  # type: str
      z = ...  # type: Union[int, float]
      v1 = ...  # type: int
      v2 = ...  # type: float
    """)

  def test_primitive_not_eq(self):
    self.Check("""
      x = "foo" if __random__ else 42
      if x == "foo":
        x.upper()
    """)

  def test_builtin_full_name_check(self):
    # Don't get confused by a class named int
    self.InferWithErrors("""
      class int():
        pass
      x = "foo" if __random__ else int()
      if x == "foo":
        x.upper()  # attribute-error
    """)

  def test_type_parameter_in_branch(self):
    ty = self.Infer("""
      if __random__:
        x = {"a": 1, "b": 42}
      else:
        x = {"b": 42j}
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Union
      x = ...  # type: Dict[str, Union[int, complex]]
    """)

  def test_none_or_tuple(self):
    # This tests the attribute retrieval code in vm.py:_get_iter
    self.Check("""
      foo = (0, 0)
      if __random__:
        foo = None
      if foo:
        a, b = foo
    """)

  def test_cmp_is_pytd_class(self):
    self.Check("""
      x = bool
      if x is str:
        name_error
      if x is not bool:
        name_error
    """)

  def test_cmp_is_tuple_type(self):
    self.Check("""
      x = (1,)
      y = (1, 2)
      z = None  # type: type[tuple]
      if type(x) is not type(y):
        name_error
      if type(x) is not z:
        name_error
    """)

  def test_cmp_is_function_type(self):
    self.Check("""
      def f(): pass
      def g(x): return x
      if type(f) is not type(g):
        name_error
    """)

  def test_cmp_is_interpreter_class(self):
    self.Check("""
      class X(object): pass
      class Y(object): pass
      if X is Y:
        name_error
      if X is not X:
        name_error
    """)

  def test_cmp_is_class_name_collision(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(object): ...
      """)
      self.Check("""
        import foo
        class X(object): pass
        if foo.X is X:
          name_error
      """, pythonpath=[d.path])

  def test_get_iter(self):
    self.Check("""
      def f():
        z = (1,2) if __random__ else None
        if not z:
          return
          x, y = z
    """)

  def test_list_comprehension(self):
    self.Check("""
      widgets = [None, 'hello']
      wotsits = [x for x in widgets if x]
      for x in wotsits:
        x.upper()
    """)

  def test_primitive(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Value(int):
            pass
        value1 = ...  # type: int
        value2 = ...  # type: Value
      """)
      self.CheckWithErrors("""
        import foo
        if foo.value1 == foo.value2:
          name_error  # name-error
      """, pythonpath=[d.path])

  def test_list_element(self):
    ty = self.Infer("""
      def f():
        x = None if __random__ else 42
        return [x] if x else [42]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f() -> List[int]: ...
    """)

  def test_keep_constant(self):
    self.Check("""
      use_option = False
      if use_option:
        name_error
    """)

  def test_function_and_class_truthiness(self):
    self.Check("""
      def f(x):
        return {} if x else []
      def g():
        return f(lambda: True).values()
      def h():
        return f(object).values()
    """)

  def test_object_truthiness(self):
    ty = self.Infer("""
      x = object() and True
    """)
    self.assertTypesMatchPytd(ty, """
      x: bool
    """)

  def test_override_len(self):
    ty = self.Infer("""
      class A:
        def __len__(self):
          return 42

      x = A() and True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A:
        def __len__(self) -> int: ...
      x: Union[A, bool]
    """)


test_base.main(globals(), __name__ == "__main__")
