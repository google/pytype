"""Tests for if-splitting."""

from pytype.tests import test_base


class SplitTest(test_base.TargetPython3BasicTest):
  """Tests for if-splitting."""

  def testHasAttr(self):
    ty = self.Infer("""

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
    """)
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

  def testUnion(self):
    self.Check("""

      from typing import Union
      def f(data: str):
        pass
      def as_my_string(data: Union[str, int]):
        if isinstance(data, str):
          f(data)
    """)

  def testUnion2(self):
    self.Check("""

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

  def testLoadAttr(self):
    self.Check("""


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

      from typing import Optional
      def f(x: Optional[str]) -> str:
        if x is None:
          x = ''
        return x
      """)

  def testConditionsAreOrdered(self):
    """Assert that multiple conditions on a path work."""
    self.Check("""

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

      from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is not None:
          x = None
        return x
      """)

  def testGuardingIsNotElse(self):
    """Assert that conditions are remembered for else if."""
    self.Check("""

      from typing import Optional
      def f(x: Optional[str]) -> int:
        if x is None:
          x = 1
        else:
          x = 1
        return x
      """)

  def testSimpleOr(self):
    self.Check("""

      def f(self, x: str = None) -> str:
        return x or "foo"
    """)

  def testOr(self):
    self.Check("""

      from typing import Optional
      def f(foo: Optional[int] = None) -> int:
        if foo is None:
          return 1
        return foo
      def g(foo: Optional[int] = None) -> int:
        return foo or 1
      def h(foo: Optional[int] = None) -> int:
        foo = foo or 1
        return foo
      def j(foo: Optional[int] = None) -> int:
        if foo is None:
          foo = 1
        return foo
    """)

  def testHiddenConflict(self):
    self.Check("""

      import typing
      def f(obj: typing.Union[int, dict, list, float, str, complex]):
        if isinstance(obj, int):
          return
        if isinstance(obj, dict):
          obj.values
    """)

  def testIsInstanceList(self):
    self.Check("""

      from typing import List
      def f(x: List[float]):
        if not isinstance(x, list):
          return float(x)
    """)

  def testLongSignature(self):
    self.Check("""


      class Foo(object):

        def __init__(self, x1: str = None, x2: str = None, x3: str = None,
                     x4: str = None, x5: str = None, x6: str = None,
                     x7: str = None, x8: str = None, x9: str = None,
                     credentials: str = None):
          if not credentials:
            credentials = ""
          self.credentials = credentials.upper()
    """)

  def testCreateList(self):
    self.Check("""

      from typing import List, Optional
      def _CreateList(opt: Optional[str]) -> List[str]:
        if opt is not None:
          return [opt]
        return ["foo"]
    """)

  def testCreateTuple(self):
    self.Check("""

      from typing import Optional, Tuple
      def _CreateTuple(opt: Optional[str]) -> Tuple[str]:
        if opt is not None:
          return (opt,)
        return ("foo",)
    """)


class SplitTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for if-splitting in Python 3."""

  def testIsInstanceMultiple(self):
    ty = self.Infer("""
      from typing import Union
      def UpperIfString(value: Union[bytes, str, int]):
        if isinstance(value, (bytes, str)):
          return value.upper()
      def ReturnIfNumeric(value: Union[str, int]):
        if isinstance(value, (int, (float, complex))):
          return value
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      def UpperIfString(value: Union[bytes, int, str]) -> Optional[Union[bytes, str]]
      def ReturnIfNumeric(value: Union[str, int]) -> Optional[int]
    """)

  def testIsInstanceAliased(self):
    # Like the previous test, but with isinstance aliased to myisinstance.
    ty = self.Infer("""
      from typing import Union
      myisinstance = isinstance
      def UpperIfString(value: Union[bytes, str, int]):
        if myisinstance(value, (bytes, str)):
          return value.upper()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Optional, Tuple, Union
      def myisinstance(object, class_or_type_or_tuple: Union[Tuple[Union[Tuple[type, ...], type], ...], type]) -> bool: ...
      def UpperIfString(value: Union[bytes, int, str]) -> Optional[Union[bytes, str]]
    """)

  def testShadowNone(self):
    self.Check("""
      from typing import Optional, Union
      def f(x: Optional[Union[str, bytes]]):
        if x is None:
          x = ''
        return x.upper()
    """)


test_base.main(globals(), __name__ == "__main__")
