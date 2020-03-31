"""Tests for @abc.abstractmethod in abc_overlay.py."""

from pytype.tests import test_base


class AbstractMethodTests(test_base.TargetPython27FeatureTest):
  """Tests for @abc.abstractmethod."""

  def test_name_error(self):
    self.InferWithErrors("""
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          name_error  # name-error
    """)

  def test_instantiate_abstract_class(self):
    _, errors = self.InferWithErrors("""
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          pass
      Example()  # not-instantiable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Example.*foo"})

  def test_multiple_inheritance_implementation(self):
    self.Check("""
      import abc
      class Interface(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          pass
      class X(Interface):
        pass
      class Implementation(Interface):
        def foo(self):
          print 42
      class Foo(X, Implementation):
        pass
      Foo().foo()
    """)

  def test_multiple_inheritance_error(self):
    _, errors = self.InferWithErrors("""
      import abc
      class X(object):
        pass
      class Interface(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          pass
      class Foo(X, Interface):
        pass
      Foo().foo()  # not-instantiable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Foo.*foo"})

  def test_multiple_inheritance_builtins(self):
    self.Check("""
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
      class Bar1(Foo, tuple):
        pass
      class Bar2(Foo, str):
        pass
      class Bar3(Foo, unicode):
        pass
      class Bar4(Foo, bytearray):
        pass
      class Bar5(Foo, dict):
        pass
      class Bar6(Foo, list):
        pass
      class Bar7(Foo, set):
        pass
      class Bar8(Foo, frozenset):
        pass
      class Bar9(Foo, buffer):
        pass
      class BarA(Foo, xrange):
        pass
      Bar1()
      Bar2()
      Bar3()
      Bar4()
      Bar5()
      Bar6()
      Bar7()
      Bar8()
      Bar9("")
      BarA(0)
    """)

  def test_unannotated_noreturn(self):
    ty = self.Infer("""
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          raise NotImplementedError()
        def bar(self):
          return self.foo()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type
      abc = ...  # type: module
      class Foo(object, metaclass=abc.ABCMeta):
        __metaclass__ = ...  # type: Type[abc.ABCMeta]
        @abc.abstractmethod
        def foo(self) -> Any: ...
        def bar(self) -> Any: ...
    """)

  def test_none_attribute(self):
    self.Check("""
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          pass
        def bar(self):
          return self.foo().upper()
    """)


test_base.main(globals(), __name__ == "__main__")
