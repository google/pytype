"""Tests for classes."""

from pytype import file_utils
from pytype.tests import test_base


class ClassesTest(test_base.TargetPython27FeatureTest):
  """Tests for classes."""

  def test_type_change(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.__class__ = int
      # Setting __class__ makes the type ambiguous to pytype, so it thinks that
      # both str.__mod__(unicode) -> unicode and str.__mod__(Any) -> str can
      # match this operation.
      x = "" % type(A())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        def __init__(self) -> None: ...
      x = ...  # type: Any
    """)

  def test_init_test_class_in_setup(self):
    ty = self.Infer("""
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      unittest = ...  # type: module
      class A(unittest.TestCase):
          x = ...  # type: int
          def fooTest(self) -> int: ...
          def setUp(self) -> None: ...
    """)

  def test_init_inherited_test_class_in_setup(self):
    ty = self.Infer("""
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
      class B(A):
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      unittest = ...  # type: module
      class A(unittest.TestCase):
          x = ...  # type: int
          def setUp(self) -> None: ...
      class B(A):
          x = ...  # type: int
          def fooTest(self) -> int: ...
    """)

  def test_set_metaclass(self):
    ty = self.Infer("""
      class A(type):
        def f(self):
          return 3.14
      class X(object):
        __metaclass__ = A
      v = X.f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type):
        def f(self) -> float: ...
      class X(object, metaclass=A):
        __metaclass__ = ...  # type: Type[A]
      v = ...  # type: float
    """)

  def test_no_metaclass(self):
    # In both of these cases, the metaclass should not actually be set.
    ty = self.Infer("""
      class A(type): pass
      X1 = type("X1", (), {"__metaclass__": A})
      class X2(object):
        __metaclass__ = type
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type): ...
      class X1(object):
        __metaclass__ = ...  # type: Type[A]
      class X2(object):
        __metaclass__ = ...  # type: Type[type]
    """)

  def test_metaclass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class MyMeta(type):
          def register(self, cls: type) -> None: ...
        def mymethod(funcobj: T) -> T: ...
      """)
      ty = self.Infer("""
        import foo
        class X(object):
          __metaclass__ = foo.MyMeta
          @foo.mymethod
          def f(self):
            return 42
        X.register(tuple)
        v = X().f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        foo = ...  # type: module
        class X(object, metaclass=foo.MyMeta):
          __metaclass__ = ...  # type: Type[foo.MyMeta]
          def f(self) -> int: ...
        v = ...  # type: int
      """)

  @test_base.skip("Setting __metaclass__ to a function doesn't work yet.")
  def test_function_as_metaclass(self):
    ty = self.Infer("""
      def MyMeta(name, bases, members):
        return type(name, bases, members)
      class X(object):
        __metaclass__ = MyMeta
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def MyMeta(names, bases, members) -> Any: ...
      class X(object, metaclass=MyMeta):
        def __metaclass__(names, bases, members) -> Any: ...
    """)

  def test_unknown_metaclass(self):
    self.Check("""
      class Foo(object):
        __metaclass__ = __any_object__
        def foo(self):
          self.bar()
        @classmethod
        def bar(cls):
          pass
    """)


test_base.main(globals(), __name__ == "__main__")
