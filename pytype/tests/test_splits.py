"""Tests for if-splitting."""

from pytype import utils
from pytype.tests import test_base


class SplitTest(test_base.BaseTest):
  """Tests for if-splitting."""

  def testRestrictNone(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else None

        if y:
          # y can't be None here!
          return y
        else:
          return 123
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[int, str]: ...
    """)

  def testRestrictTrue(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else True

        if y:
          return 123
        else:
          return y
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[int, str]: ...
    """)

  def testRelatedVariable(self):
    ty = self.Infer("""
      def foo(x):
        # y is str or None
        # z is float or True
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[float, int]: ...
    """)

  def testNestedConditions(self):
    ty = self.Infer("""
      def foo(x1, x2):
        y1 = str(x1) if x1 else 0

        if y1:
          if x2:
            return y1  # The y1 condition is still active here.

        return "abc"
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x1, x2) -> str: ...
    """)

  def testRemoveConditionAfterMerge(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else None

        if y:
          # y can't be None here.
          z = 123
        # But y can be None here.
        return y
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def foo(x) -> Union[None, str]: ...
    """)

  def testUnsatisfiableCondition(self):
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> str: ...
      def f2(x) -> int: ...
      def f3(x) -> str: ...
      def f4(x) -> int: ...
    """)

  def testSourcesPropagatedThroughCall(self):
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
    """, deep=True)
    # TODO(dbaum): This test could be more focused if assertTypesMatchPytd
    # accepted some sort of filter that would be applied to both pytd trees
    # before matching.
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Foo(object):
        def method(self) -> int: ...

      class Bar(object):
        def method(self) -> str: ...

      def foo(x) -> Union[None, int]: ...
    """)

  def testShortCircuit(self):
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Tuple
      def int_t(x) -> int: ...
      def int_f(x) -> int: ...
      def str_t(x) -> str: ...
      def str_f(x) -> str: ...
      def bool_t(x) -> bool: ...
      def bool_f(x) -> bool: ...
      def tuple_t(x) -> Tuple[int]: ...
      def tuple_f(x) -> Tuple[nothing, ...]: ...
      def dict_f(x) -> Dict[nothing, nothing]: ...
      def list_f(x) -> List[nothing]: ...
      def set_f(x) -> set[nothing]: ...
      def frozenset_f(x) -> frozenset[nothing]: ...
    """)

  def testDict(self):
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f1() -> str: ...
      def f2(x) -> Union[int, str]: ...
    """)

  def testDictUpdate(self):
    ty = self.Infer("""
      def f1():
        d = {}
        d.update({})
        return 123 if d else "hello"

      def f2():
        d = {}
        d.update({"a": 1})
        return 123 if d else "hello"

    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f1() -> str: ...
      def f2() -> int: ...
    """)

  def testDictUpdateFromKwargs(self):
    ty = self.Infer("""
      def f1():
        d = {}
        d.update()
        return 123 if d else "hello"

      def f2():
        d = {}
        d.update(a=1)
        return 123 if d else "hello"
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f1() -> str: ...
      def f2() -> int: ...
    """)

  def testBadDictUpdate(self):
    ty = self.Infer("""
      def f1():
        d = {}
        d.update({"a": 1}, {"b": 2})
        return 123 if d else "hello"

      def f2():
        d = {}
        d.update({"a": 1}, {"b": 2}, c=3)
        return 123 if d else "hello"
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f1() -> str or int
      def f2() -> str or int
    """)

  def testIsInstance(self):
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
    """, deep=True)
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

  def testIsInstanceMultiple(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import Union
      def UpperIfString(value: Union[unicode, str, int]):
        if isinstance(value, (unicode, str)):
          return value.upper()
      def ReturnIfNumeric(value: Union[str, int]):
        if isinstance(value, (int, (float, complex))):
          return value
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      def UpperIfString(value: Union[int, unicode]) -> Optional[Union[str, unicode]]
      def ReturnIfNumeric(value: Union[str, int]) -> Optional[int]
    """)

  def testIsInstanceAliased(self):
    # Like the previous test, but with isinstance aliased to myisinstance.
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import Union
      myisinstance = isinstance
      def UpperIfString(value: Union[unicode, str, int]):
        if myisinstance(value, (unicode, str)):
          return value.upper()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Optional, Tuple, Union
      def myisinstance(object, class_or_type_or_tuple: Union[Tuple[Union[Tuple[type, ...], type], ...], type]) -> bool: ...
      def UpperIfString(value: Union[int, unicode]) -> Optional[Union[str, unicode]]
    """)

  def testIsSubclass(self):
    ty = self.Infer("""\
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """\
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

  def testHasAttrBuiltin(self):
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def sig(x) -> bool: ...
      def d1() -> str: ...
      def d2() -> int: ...
      def d3() -> str: ...
      def a1(x) -> Union[int, str]: ...
    """)

  def testHasAttr(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      class Foo():
        def bar(self):
          pass
      class Baz(Foo):
        def quux(self):
          pass
      def d1(x: Foo): return "y" if hasattr(x, "bar") else 0
      def d2(x: Foo): return "y" if hasattr(x, "unknown") else 0
      def d3(x: Baz): return "y" if hasattr(x, "quux") else 0
      def d4(x: Baz): return "y" if hasattr(x, "bar") else 0
      def a1(x): return "y" if hasattr(x, "bar") else 0
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Baz(Foo):
        def quux(self) -> None: ...
      class Foo:
        def bar(self) -> None: ...
      def d1(x: Foo) -> str: ...
      def d2(x: Foo) -> int: ...
      def d3(x: Baz) -> str: ...
      def d4(x: Baz) -> str: ...
      def a1(x) -> Union[int, str]: ...
    """)

  def testSplit(self):
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Optional, TypeVar, Union
      _T0 = TypeVar("_T0")
      def f2(x: _T0) -> Union[_T0, complex]: ...
      def f1(x) -> Optional[int]
    """)

  def testDeadIf(self):
    ty = self.Infer("""
      def foo(x):
        x = None
        if x is not None:
          x.foo()
        return x
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> None: ...
    """)

  def testUnaryNot(self):
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

    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def not_t(x) -> int: ...
      def not_f(x) -> str: ...
      def not_ambiguous(x) -> Union[int, str]: ...
    """)

  def testIsInstanceObjectWithoutClass(self):
    ty = self.Infer("""
      def foo(x):
        return 1 if isinstance(dict, type) else "x"
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> int: ...
    """)

  def testDoubleAssign(self):
    self.Check("""
      x = 1
      x = None
      if x is not None:
        x.foo()
    """)

  def testUnion(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Union
      def f(data: str):
        pass
      def as_my_string(data: Union[str, int]):
        if isinstance(data, str):
          f(data)
    """)

  def testUnion2(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Union
      class MyString(object):
        def __init__(self, arg: str):
          self.arg = arg
      def as_my_string(data: Union[str, MyString]) -> MyString:
        if isinstance(data, str):
          result = MyString(data)
        else:
          # data has type MyString
          result = data
        return result
    """)

  def testInfiniteLoop(self):
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

  def testLoadAttr(self):
    self.Check("""
      from __future__ import google_type_annotations

      class A(object):
        def __init__(self):
          self.initialized = False
          self.data = None
        def f1(self, x: int):
          self.initialized = True
          self.data = x
        def f2(self) -> int:
          if self.initialized:
            return self.data
          else:
            return 0
    """)

  def testGuardingIs(self):
    """Assert that conditions are remembered for is."""
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is None:
          x = ''
        return x
      """)

  def testConditionsAreOrdered(self):
    """Assert that multiple conditions on a path work."""
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[NoneType]) -> int:
        if x is not None:
          x = None
        if x is None:
          x = 1
        return x
      """)

  def testGuardingIsNot(self):
    """Assert that conditions are remembered for is not."""
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is not None:
          x = None
        return x
      """)

  def testGuardingIsNotElse(self):
    """Assert that conditions are remembered for else if."""
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> int:
        if x is None:
          x = 1
        else:
          x = 1
        return x
      """)

  def testDictContains(self):
    """Assert that we can determine whether a dict contains a key."""
    self.Check("""
      d1 = {"x": 42}
      if "x" in d1:
        print d1["x"]
      else:
        print d1["nonsense"]  # Dead code

      d2 = {}
      if "x" in d2:
        print d2["nonsense"]  # Dead code

      d3 = {__any_object__: __any_object__}
      if "x" in d3:
        print d3["x"]
      else:
        print d3["y"]
    """)

  def testDictDoesNotContain(self):
    """Assert that we can determine whether a dict does not contain a key."""
    self.Check("""
      d1 = {"x": 42}
      if "x" not in d1:
        print d1["nonsense"]  # Dead code
      else:
        print d1["x"]

      d2 = {}
      if "x" not in d2:
        pass
      else:
        print d2["nonsense"]  # Dead code

      d3 = {__any_object__: __any_object__}
      if "x" not in d3:
        print d3["y"]
      else:
        print d3["x"]
    """)

  def testDictMaybeContains(self):
    """Test that we can handle more complex cases involving dict membership."""
    ty = self.Infer("""\
      if __random__:
        x = {"a": 1, "b": 2}
      else:
        x = {"b": 42j}
      if "a" in x:
        v1 = x["b"]
      if "a" not in x:
        v2 = x["b"]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      x = ...  # type: Dict[str, int or complex]
      v1 = ...  # type: int
      v2 = ...  # type: complex
    """)

  def testContainsCoerceToBool(self):
    ty = self.Infer("""\
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __contains__(self, x) -> int
      class B(object):
        def __contains__(self, x) -> int
      x1 = ...  # type: str
      x2 = ...  # type: complex
      y1 = ...  # type: complex
      y2 = ...  # type: bool
    """)

  def testSkipOverMidwayIf(self):
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      def f(r) -> Optional[str]
    """)

  def testSimpleOr(self):
    self.Check("""
      from __future__ import google_type_annotations
      def f(self, x:str=None) -> str:
        return x or "foo"
    """)

  def testOr(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(foo: Optional[int]=None) -> int:
        if foo is None:
          return 1
        return foo
      def g(foo: Optional[int]=None) -> int:
        return foo or 1
      def h(foo: Optional[int]=None) -> int:
        foo = foo or 1
        return foo
      def j(foo: Optional[int]=None) -> int:
        if foo is None:
          foo = 1
        return foo
    """)

  def testDictEq(self):
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      x = ...  # type: Dict[str, int]
      y = ...  # type: Dict[str, int]
      z = ...  # type: int or complex
      v1 = ...  # type: complex
      v2 = ...  # type: int or complex
    """)

  def testTupleEq(self):
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      x = ...  # type: Tuple[int, ...]
      y = ...  # type: Tuple[int, int]
      z = ...  # type: str or float
      v1 = ...  # type: float
      v2 = ...  # type: str or float
    """)

  def testPrimitiveEq(self):
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
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: str
      y = ...  # type: str
      z = ...  # type: int or float
      v1 = ...  # type: int
      v2 = ...  # type: float
    """)

  def testPrimitiveNotEq(self):
    self.Check("""
      x = "foo" if __random__ else 42
      if x == "foo":
        x.upper()
    """)

  def testBuiltinFullNameCheck(self):
    # Don't get confused by a class named int
    _, errorlog = self.InferAndCheck("""
      class int():
        pass
      x = "foo" if __random__ else int()
      if x == "foo":
        x.upper()
    """)
    self.assertNotEqual(len(errorlog), 0)

  def testTypeParameterInBranch(self):
    ty = self.Infer("""
      if __random__:
        x = {"a": 1, "b": 42}
      else:
        x = {"b": 42j}
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      x = ...  # type: Dict[str, int or complex]
    """)

  def testNoneOrTuple(self):
    # This tests the attribute retrieval code in vm.py:_get_iter
    self.Check("""\
      foo = (0, 0)
      if __random__:
        foo = None
      if foo:
        a, b = foo
    """)

  def testCmpIsPyTDClass(self):
    self.Check("""
      x = bool
      if x is str:
        name_error
      if x is not bool:
        name_error
    """)

  def testCmpIsTupleType(self):
    self.Check("""
      x = (1,)
      y = (1, 2)
      z = None  # type: type[tuple]
      if type(x) is not type(y):
        name_error
      if type(x) is not z:
        name_error
    """)

  def testCmpIsFunctionType(self):
    self.Check("""
      def f(): pass
      def g(x): return x
      if type(f) is not type(g):
        name_error
    """)

  def testCmpIsInterpreterClass(self):
    self.Check("""
      class X(object): pass
      class Y(object): pass
      if X is Y:
        name_error
      if X is not X:
        name_error
    """)

  def testCmpIsClassNameCollision(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X(object): ...
      """)
      self.Check("""
        import foo
        class X(object): pass
        if foo.X is X:
          name_error
      """, pythonpath=[d.path])

  def testGetIter(self):
    self.Check("""
      def f():
        z = (1,2) if __random__ else None
        if not z:
          return
          x, y = z
    """)

  def testHiddenConflict(self):
    self.Check("""
      from __future__ import google_type_annotations
      import typing
      def f(obj: typing.Union[int, dict, list, float, str, complex]):
        if isinstance(obj, int):
          return
        if isinstance(obj, dict):
          obj.itervalues
    """)


if __name__ == "__main__":
  test_base.main()
