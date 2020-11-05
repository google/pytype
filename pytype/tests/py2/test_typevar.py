"""Tests for TypeVar."""

from pytype import file_utils
from pytype.tests import test_base


class Test(test_base.TargetPython27FeatureTest):
  """Tests for TypeVar."""

  def test_use_constraints_from_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import AnyStr, TypeVar
        T = TypeVar("T", int, float)
        def f(x: T) -> T: ...
        def g(x: AnyStr) -> AnyStr: ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f("")  # wrong-arg-types[e1]
        foo.g(0)  # wrong-arg-types[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"Union\[float, int\].*str",
          "e2": r"Union\[str, unicode\].*int"})

  def test_extra_arguments(self):
    # TODO(b/78905523): Make this a target-independent test.
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", extra_arg=42)  # invalid-typevar[e1]
      S = TypeVar("S", *__any_object__)  # invalid-typevar[e2]
      U = TypeVar("U", **__any_object__)  # invalid-typevar[e3]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"extra_arg", "e2": r"\*args", "e3": r"\*\*kwargs"})

  def test_simplify_args_and_kwargs(self):
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

  def test_call_type_parameter_instance(self):
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
        def __init__(self) -> None: ...
        def call(self) -> Optional[int]: ...
    """)


test_base.main(globals(), __name__ == "__main__")
