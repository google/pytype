"""Tests for attrs library in attr_overlay.py."""

from pytype import file_utils
from pytype.tests import test_base


ATTR_PYI = """
from typing import Optional, Type, TypeVar
T = TypeVar('T')
def s(cls: Type[T]) -> Type[T]: ...
def ib(type: T = Nonei, **kwargs) -> T: ...
"""


class TestAttrib(test_base.TargetIndependentTest):
  """Tests for attr.ib."""

  def Infer(self, code):
    with file_utils.Tempdir() as d:
      d.create_file("attr.pyi", ATTR_PYI)
      return super(TestAttrib, self).Infer(code, pythonpath=[d.path])

  def InferWithErrors(self, code):
    with file_utils.Tempdir() as d:
      d.create_file("attr.pyi", ATTR_PYI)
      return super(TestAttrib, self).InferWithErrors(code, pythonpath=[d.path])

  def test_basic(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib()
        y = attr.ib(type=int)
        z = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: Any
        y: int
        z: str
        def __init__(self, x, y, z) -> None: ...
    """)

  def test_interpreter_class(self):
    ty = self.Infer("""
      import attr
      class A(object): pass
      @attr.s
      class Foo(object):
        x = attr.ib(type=A)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class A(object): ...
      class Foo(object):
        x: A
        def __init__(self, x) -> None: ...
    """)

  def test_typing(self):
    ty = self.Infer("""
      from typing import List
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=List[int])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      attr: module
      class Foo(object):
        x: List[int]
        def __init__(self, x) -> None: ...
    """)

  def test_comment_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: int
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, x, y) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: int
        y = attr.ib(type=str)
        z = 1 # class var, should not be in __init__
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        z: int
        def __init__(self, x, y) -> None: ...
    """)

  def test_type_clash(self):
    _, errors = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=str) # type: int
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation")])


test_base.main(globals(), __name__ == "__main__")
