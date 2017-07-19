"""Tests for @abc.abstractmethod in abc_overlay.py."""

from pytype.tests import test_inference


class AbstractMethodTests(test_inference.InferenceTest):
  """Tests for @abc.abstractmethod."""

  def test_basic_abstractmethod(self):
    ty, errors = self.InferAndCheck("""\
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
    _, errors = self.InferAndCheck("""\
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
    self.assertNoErrors("""
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
    self.assertNoErrors("""
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
    self.assertNoErrors("""
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
    _, errors = self.InferAndCheck("""\
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
    _, errors = self.InferAndCheck("""\
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self):
          name_error
    """)
    self.assertErrorLogIs(errors, [(6, "name-error", r"name_error")])

  def test_call_abstract_method(self):
    self.assertNoErrors("""
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
    self.assertNoErrors("""
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
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      import abc
      class Example(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def foo(self) -> int:
          return None
    """, skip_repeat_calls=False)


if __name__ == "__main__":
  test_inference.main()
