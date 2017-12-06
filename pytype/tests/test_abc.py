"""Tests for @abc.abstractmethod in abc_overlay.py."""

from pytype import utils
from pytype.tests import test_base


class AbstractMethodTests(test_base.BaseTest):
  """Tests for @abc.abstractmethod."""

  def test_basic_abstractmethod(self):
    ty, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      import abc

      class Example(object):
        __metaclass__ = abc.ABCMeta

        @abc.abstractmethod
        def foo(self) -> int:
          pass
    """)

    self.assertTypesMatchPytd(ty, """\
      import abc
      from typing import Type

      abc = ...  # type: module

      class Example(object, metaclass=abc.ABCMeta):
        __metaclass__ = ...  # type: Type[abc.ABCMeta]
        @abstractmethod
        def foo(self) -> int: ...
      """)
    self.assertErrorLogIs(errors, [])

  def test_super_abstractmethod(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      import abc

      class Example(object):
        __metaclass__ = abc.ABCMeta

        @abc.abstractmethod
        def foo(self) -> int:
          pass

      class Ex2(Example):
        def foo(self) -> int:
          return super(Ex2, self).foo()
      """)
    self.assertErrorLogIs(errors, [(9, "bad-return-type")])

  def test_super_abstractmethod_in_abstract_class(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc

      class Example(object):
        __metaclass__ = abc.ABCMeta

        @abc.abstractmethod
        def foo(self) -> int:
          pass

      class Ex2(Example):
        @abc.abstractmethod
        def foo(self) -> int:
          return super(Ex2, self).foo()
    """)

  def test_abstract_subclass(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc

      class Example(object):
        __metaclass__ = abc.ABCMeta

      class Ex2(Example):
        @abc.abstractmethod
        def foo(self) -> int:
          pass
    """)

  def test_inherited_abstract_method(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc

      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self) -> int:
          pass

      class Ex2(Example):
        def bar(self):
          return super(Ex2, self).foo()
    """)

  def test_regular_method_in_abstract_class(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        def foo(self) -> int:
          pass  # line 6
        @abc.abstractmethod
        def bar(self): ...
    """)
    self.assertErrorLogIs(errors, [(6, "bad-return-type", r"int.*None")])

  def test_name_error(self):
    _, errors = self.InferWithErrors("""\
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          name_error
    """)
    self.assertErrorLogIs(errors, [(6, "name-error", r"name_error")])

  def test_call_abstract_method(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self) -> int:
          return None
        def bar(self):
          return self.foo()
    """)

  def test_namedtuple_return(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc
      import collections
      X = collections.namedtuple("X", "")
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self) -> X:
          return None
    """)

  def test_no_skip_calls(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self) -> int:
          return None
    """, skip_repeat_calls=False)

  def test_instantiate_abstract_class(self):
    _, errors = self.InferWithErrors("""\
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          pass
      Example()  # line 7
    """)
    self.assertErrorLogIs(errors, [(7, "not-instantiable", r"Example.*foo")])

  def test_instantiate_pyi_abstract_class(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class Example(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def foo(self) -> None: ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.Example()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "not-instantiable",
                                      r"foo\.Example.*foo")])

  def test_stray_abstractmethod(self):
    _, errors = self.InferWithErrors("""\
      import abc
      class Example(object):
        @abc.abstractmethod
        def foo(self):
          pass
    """)
    self.assertErrorLogIs(errors, [(2, "ignored-abstractmethod",
                                    r"foo.*Example")])

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

  def test_multiple_inheritance_implementation_pyi(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class Interface(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def foo(self): ...
        class X(Interface): ...
        class Implementation(Interface):
          def foo(self) -> int: ...
        class Foo(X, Implementation): ...
      """)
      self.Check("""
        import foo
        foo.Foo().foo()
      """, pythonpath=[d.path])

  def test_multiple_inheritance_error(self):
    _, errors = self.InferWithErrors("""\
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
      Foo().foo()  # line 11
    """)
    self.assertErrorLogIs(errors, [(11, "not-instantiable", r"Foo.*foo")])

  def test_multiple_inheritance_error_pyi(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class X(object): ...
        class Interface(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def foo(self): ...
        class Foo(X, Interface): ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.Foo().foo()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "not-instantiable", r"foo\.Foo.*foo")])

  def test_abstract_method_unusual_selfname(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(this) -> int:
          pass
    """)

  def test_abstractmethod_and_property(self):
    self.Check("""
      from __future__ import google_type_annotations
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
        @property
        @abc.abstractmethod
        def foo(self) -> int:
          pass
    """)


if __name__ == "__main__":
  test_base.main()
