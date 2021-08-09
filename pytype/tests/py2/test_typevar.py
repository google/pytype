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

  def test_call_type_parameter_instance(self):
    # Python 2-specific due to the iteritems call (which is required to trigger
    # use of TypeParameterInstance).
    ty = self.Infer("""
      class Foo:
        def __init__(self):
          self.callbacks = {"": int}
        def call(self):
          for _, callback in sorted(self.callbacks.iteritems()):
            return callback()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional, Type
      class Foo:
        callbacks = ...  # type: Dict[str, Type[int]]
        def __init__(self) -> None: ...
        def call(self) -> Optional[int]: ...
    """)


test_base.main(globals(), __name__ == "__main__")
