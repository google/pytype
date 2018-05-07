"""Tests for TypeVar."""

from pytype import utils
from pytype.tests import test_base


class Test(test_base.TargetPython27FeatureTest):
  """Tests for TypeVar."""

  def testUseConstraintsFromPyi(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """\
        from typing import AnyStr, TypeVar
        T = TypeVar("T", int, float)
        def f(x: T) -> T: ...
        def g(x: AnyStr) -> AnyStr: ...
      """)
      _, errors = self.InferWithErrors("""\
        import foo
        foo.f("")
        foo.g(0)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (2, "wrong-arg-types", r"Union\[float, int\].*str"),
          (3, "wrong-arg-types", r"Union\[str, unicode\].*int")])

  def testExtraArguments(self):
    # TODO(b/78905523): Make this a target-independent test.
    _, errors = self.InferWithErrors("""\
      from typing import TypeVar
      T = TypeVar("T", extra_arg=42)
      S = TypeVar("S", *__any_object__)
      U = TypeVar("U", **__any_object__)
    """)
    self.assertErrorLogIs(errors, [
        (2, "invalid-typevar", r"extra_arg"),
        (3, "invalid-typevar", r"\*args"),
        (4, "invalid-typevar", r"\*\*kwargs")])

  def testSimplifyArgsAndKwargs(self):
    # TODO(b/78905523): Make this a target-independent test.
    ty = self.Infer("""
      from typing import TypeVar
      constraints = (int, str)
      kwargs = {"covariant": True}
      T = TypeVar("T", *constraints, **kwargs)  # pytype: disable=not-supported-yet
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Tuple, Type, TypeVar
      T = TypeVar("T", int, str)
      constraints = ...  # type: Tuple[Type[int], Type[str]]
      kwargs = ...  # type: Dict[str, bool]
    """)

  def testCallTypeParameterInstance(self):
    # Python 2-specific due to the iteritems call (which is required to trigger
    # use of TypeParameterInstance).
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.callbacks = {"": int}
        def call(self):
          for _, callback in sorted(self.callbacks.iteritems()):
            return callback()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional, Type
      class Foo(object):
        callbacks = ...  # type: Dict[str, Type[int]]
        def call(self) -> Optional[int]
    """)


if __name__ == "__main__":
  test_base.main()
