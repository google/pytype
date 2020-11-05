"""Test comparison operators."""


from pytype.tests import test_base


class InTest(test_base.TargetIndependentTest):
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
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)
    self.assertErrorRegexes(errors, {"e": r"'in'.*object"})

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x in y
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() in []
      def g():
        # The result of __contains__ is coerced to a bool.
        return 3 in Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
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


class NotInTest(test_base.TargetIndependentTest):
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
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)
    self.assertErrorRegexes(errors, {"e": r"'in'.*object"})

  # "not in" maps to the inverse of __contains__
  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() not in []
      def g():
        # The result of __contains__ is coerced to a bool.
        return 3 not in Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
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


class IsTest(test_base.TargetIndependentTest):
  """Test for "x is y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)


class IsNotTest(test_base.TargetIndependentTest):
  """Test for "x is not y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is not y
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_class_new(self):
    # The assert should not block inference of the return type, since cls could
    # be a subclass of Foo
    ty = self.Infer("""
      class Foo(object):
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
      class Foo(object):
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


class LtTest(test_base.TargetIndependentTest):
  """Test for "x < y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x < y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __lt__(self, x):
          return 3j
      def f():
        return Foo() < 3
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  @test_base.skip("Needs full emulation of Objects/object.c:try_rich_compare")
  def test_reverse(self):
    ty = self.Infer("""
      class Foo(object):
        def __lt__(self, x):
          return 3j
        def __gt__(self, x):
          raise x
      class Bar(Foo):
        def __gt__(self, x):
          return (3,)
      def f1():
        return Foo() < 3
      def f2():
        return Foo() < Foo()
      def f3():
        return Foo() < Bar()
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f1"), self.complex)
    self.assertOnlyHasReturnType(ty.Lookup("f2"), self.complex)
    self.assertOnlyHasReturnType(ty.Lookup("f3"), self.tuple)


class LeTest(test_base.TargetIndependentTest):
  """Test for "x <= y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x <= y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __le__(self, x):
          return 3j
      def f():
        return Foo() <= 3
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class GtTest(test_base.TargetIndependentTest):
  """Test for "x > y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x > y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __gt__(self, x):
          return 3j
      def f():
        return Foo() > 3
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class GeTest(test_base.TargetIndependentTest):
  """Test for "x >= y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x >= y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __ge__(self, x):
          return 3j
      def f():
        return Foo() >= 3
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class EqTest(test_base.TargetIndependentTest):
  """Test for "x == y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x == y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __eq__(self, x):
          return 3j
      def f():
        return Foo() == 3
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def test_class(self):
    ty = self.Infer("""
      def f(x, y):
        return x.__class__ == y.__class__
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_primitive_against_unknown(self):
    self.assertNoCrash(self.Check, """
      v = None  # type: int
      v == __any_object__
    """)


class NeTest(test_base.TargetIndependentTest):
  """Test for "x != y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x != y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __ne__(self, x):
          return 3j
      def f():
        return Foo() != 3
    """, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class InstanceUnequalityTest(test_base.TargetIndependentTest):

  def test_iterator_contains(self):
    self.Check("""
      1 in iter((1, 2))
      1 not in iter((1, 2))
    """)


test_base.main(globals(), __name__ == "__main__")
