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


if __name__ == "__main__":
  test_inference.main()
