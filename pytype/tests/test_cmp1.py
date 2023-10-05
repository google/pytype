"""Test comparison operators."""

from pytype.tests import test_base


class InTest(test_base.BaseTest):
  """Test for "x in y". Also test overloading of this operator."""

  def test_concrete(self):
    ty, errors = self.InferWithErrors("""
      def f(x, y):
        return x in y  # unsupported-operands[e]
      f(1, [1])
      f(1, [2])
      f("x", "x")
      f("y", "x")
      f("y", (1,))
      f("y", object())
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")
    self.assertErrorRegexes(errors, {"e": r"'in'.*object"})

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x in y
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo:
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() in []
      def g():
        # The result of __contains__ is coerced to a bool.
        return 3 in Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __contains__(self, x) -> complex: ...
      def f() -> bool: ...
      def g() -> bool: ...
    """)

  def test_none(self):
    _, errors = self.InferWithErrors("""
      x = None
      if "" in x:  # unsupported-operands[e1]
        del x[""]  # unsupported-operands[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"'in'.*None", "e2": r"item deletion.*None"})


class NotInTest(test_base.BaseTest):
  """Test for "x not in y". Also test overloading of this operator."""

  def test_concrete(self):
    ty, errors = self.InferWithErrors("""
      def f(x, y):
        return x not in y  # unsupported-operands[e]
      f(1, [1])
      f(1, [2])
      f("x", "x")
      f("y", "x")
      f("y", (1,))
      f("y", object())
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")
    self.assertErrorRegexes(errors, {"e": r"'in'.*object"})

  # "not in" maps to the inverse of __contains__
  def test_overloaded(self):
    ty = self.Infer("""
      class Foo:
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() not in []
      def g():
        # The result of __contains__ is coerced to a bool.
        return 3 not in Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __contains__(self, x) -> complex: ...
      def f() -> bool: ...
      def g() -> bool: ...
    """)

  def test_none(self):
    _, errors = self.InferWithErrors("""
      x = None
      if "" not in x:  # unsupported-operands[e1]
        x[""] = 42  # unsupported-operands[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"'in'.*None", "e2": r"item assignment.*None"})


class IsTest(test_base.BaseTest):
  """Test for "x is y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
      f(1, 2)
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")


class IsNotTest(test_base.BaseTest):
  """Test for "x is not y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is not y
      f(1, 2)
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """)
    self.assertTypesMatchPytd(ty, "def f(x, y) -> bool: ...")

  def test_class_new(self):
    # The assert should not block inference of the return type, since cls could
    # be a subclass of Foo
    ty = self.Infer("""
      class Foo:
        def __new__(cls, *args, **kwargs):
          assert(cls is not Foo)
          return object.__new__(cls)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      _TFoo = TypeVar('_TFoo', bound=Foo)
      class Foo:
        def __new__(cls: Type[_TFoo], *args, **kwargs) -> _TFoo: ...
    """)

  def test_class_factory(self):
    # The assert should not block inference of the return type, since cls could
    # be a subclass of Foo
    ty = self.Infer("""
      class Foo:
        @classmethod
        def factory(cls, *args, **kwargs):
          assert(cls is not Foo)
          return object.__new__(cls)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      _TFoo = TypeVar('_TFoo', bound=Foo)
      class Foo:
        @classmethod
        def factory(cls: Type[_TFoo], *args, **kwargs) -> _TFoo: ...
    """)


class CmpTest(test_base.BaseTest):
  """Test for comparisons. Also test overloading."""

  OPS = ["<", "<=", ">", ">="]

  def _test_concrete(self, op):
    ty, errors = self.InferWithErrors(f"""
      def f(x, y):
        return x {op} y  # unsupported-operands[e]
      f(1, 2)
      f(1, "a")  # <- error raised from here but in line 2
      f(object(), "x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f(x: int, y: int) -> bool: ...
      @overload
      def f(x: object, y: str) -> bool: ...
    """)
    self.assertErrorRegexes(errors, {"e": "Types.*int.*str"})
    self.assertErrorRegexes(errors, {"e": "Called from.*line 4"})

  def test_concrete(self):
    for op in self.OPS:
      self._test_concrete(op)

  def test_literal(self):
    for op in self.OPS:
      errors = self.CheckWithErrors(f"""
        '1' {op} 2 # unsupported-operands[e]
      """)
      self.assertErrorRegexes(errors, {"e": "Types.*str.*int"})

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo:
        def __lt__(self, x):
          return 3j
      def f():
        return Foo() < 3
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __lt__(self, x) -> complex: ...
      def f() -> complex: ...
    """)


class EqTest(test_base.BaseTest):
  """Test for "x == y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x == y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f(x: int, y: int) -> bool: ...
      @overload
      def f(x: int, y: str) -> bool: ...
      @overload
      def f(x: object, y: str) -> bool: ...
    """)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo:
        def __eq__(self, x):
          return 3j
      def f():
        return Foo() == 3
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __eq__(self, x) -> complex: ...
      def f() -> complex: ...
    """)

  def test_class(self):
    ty = self.Infer("""
      def f(x, y):
        return x.__class__ == y.__class__
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f(x: int, y: int) -> bool: ...
      @overload
      def f(x: int, y: str) -> bool: ...
      @overload
      def f(x: object, y: str) -> bool: ...
    """)

  def test_primitive_against_unknown(self):
    self.assertNoCrash(self.Check, """
      v = None  # type: int
      v == __any_object__
    """)


class NeTest(test_base.BaseTest):
  """Test for "x != y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x != y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f(x: int, y: int) -> bool: ...
      @overload
      def f(x: int, y: str) -> bool: ...
      @overload
      def f(x: object, y: str) -> bool: ...
    """)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo:
        def __ne__(self, x):
          return 3j
      def f():
        return Foo() != 3
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __ne__(self, x) -> complex: ...
      def f() -> complex: ...
    """)


class InstanceUnequalityTest(test_base.BaseTest):

  def test_iterator_contains(self):
    self.Check("""
      1 in iter((1, 2))
      1 not in iter((1, 2))
    """)


if __name__ == "__main__":
  test_base.main()
