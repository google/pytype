"""Tests for attrs library in attr_overlay.py."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestAttrib(test_utils.TestAttrMixin,
                 test_base.TargetIndependentTest):
  """Tests for attr.ib."""

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
        def __init__(self, x, y: int, z: str) -> None: ...
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
        def __init__(self, x: A) -> None: ...
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
        def __init__(self, x: List[int]) -> None: ...
    """)

  def test_union_types(self):
    ty = self.Infer("""
      from typing import Union
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=Union[str, int])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      attr: module
      class Foo(object):
        x: Union[str, int]
        def __init__(self, x: Union[str, int]) -> None: ...
    """)

  def test_comment_annotations(self):
    ty = self.Infer("""
      from typing import Union
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: Union[str, int]
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      attr: module
      class Foo(object):
        x: Union[str, int]
        y: str
        def __init__(self, x: Union[str, int], y: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: 'Foo'
        y = attr.ib() # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
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
        def __init__(self, x: int, y: str) -> None: ...
    """)

  def test_type_clash(self):
    _, errors = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=str) # type: int
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation")])

  def test_name_mangling(self):
    # NOTE: Python itself mangles names starting with two underscores.
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        _x = attr.ib(type=int)
        __y = attr.ib(type=int)
        ___z = attr.ib(type=int)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        _x: int
        _Foo__y: int
        _Foo___z: int
        def __init__(self, x: int, Foo__y: int, Foo___z: int) -> None: ...
    """)

  def test_defaults(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=42)
        y = attr.ib(type=int, default=6)
        z = attr.ib(type=str, default=28)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: int
        y: int
        z: str
        def __init__(self, x: int = ..., y: int = ..., z: str = ...) -> None: ...
    """)

  def test_defaults_with_typecomment(self):
    # Typecomments should override the type of default
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=42) # type: int
        y = attr.ib(default=42) # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, x: int = ..., y: str = ...) -> None: ...
    """)


class TestAttrs(test_utils.TestAttrMixin,
                test_base.TargetIndependentTest):
  """Tests for attr.s."""

  def test_basic(self):
    ty = self.Infer("""
      import attr
      @attr.s()
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
        def __init__(self, x, y: int, z: str) -> None: ...
    """)

  def test_no_init(self):
    ty = self.Infer("""
      import attr
      @attr.s(init=False)
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
    """)

  def test_bad_kwarg(self):
    _, err = self.InferWithErrors("""
      import attr
      class A:
        pass
      @attr.s(init=A())
      class Foo:
        pass
    """)
    self.assertErrorLogIs(err, [(5, "not-supported-yet")])


test_base.main(globals(), __name__ == "__main__")
