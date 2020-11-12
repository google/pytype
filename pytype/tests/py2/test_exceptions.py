"""Test exceptions."""

from pytype.tests import test_base


class TestExceptions(test_base.TargetPython27FeatureTest):
  """Exception tests."""

  # The `raise x, y, z` syntax is not valid in python3

  def test_raise_exception_2args(self):
    self.Check("raise ValueError, 'bad'")

  def test_raise_exception_3args(self):
    self.Check("""
      from sys import exc_info
      try:
        raise Exception
      except:
        _, _, tb = exc_info()
      raise ValueError, "message", tb
      """)

  def test_reraise_no_return(self):
    ty = self.Infer("""
      import sys
      def f():
        try:
          raise ValueError()
        except:
          exc_info = sys.exc_info()
          raise exc_info[0], exc_info[1], exc_info[2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn
      sys = ...  # type: module
      def f() -> NoReturn: ...
    """)

  # Infers __init__(self, _) -> NoReturn under target py3
  # b/78654300
  def test_type_self(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, _):  # Add an arg so __init__ isn't optimized away.
          if type(self) is Foo:
            raise ValueError()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __init__(self, _) -> None: ...
    """)


test_base.main(globals(), __name__ == "__main__")
