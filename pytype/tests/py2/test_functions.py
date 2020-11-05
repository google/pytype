"""Test functions."""

from pytype.tests import test_base


class TestFunctions(test_base.TargetPython27FeatureTest):
  """Test functions."""

  def test_tuple_args_smoke(self):
    unused_ty = self.Infer("""
      def foo((x, y), z):
        pass
    """)
    # Smoke test only. pytd doesn't support automatic tuple unpacking in args.

  def test_matching_functions(self):
    ty = self.Infer("""
      def f():
        return 3

      class Foo(object):
        def match_method(self):
          return map(self.method, [])
        def match_function(self):
          return map(f, [])
        def match_pytd_function(self):
          return map(map, [])
        def match_bound_pytd_function(self):
          return map({}.keys, [])
        def method(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f() -> int: ...
      class Foo(object):
        def match_method(self) -> List[nothing, ...]: ...
        def match_function(self) -> List[nothing, ...]: ...
        def match_pytd_function(self) -> List[nothing, ...]: ...
        def match_bound_pytd_function(self) -> List[nothing, ...]: ...
        def method(self) -> NoneType: ...
    """)


test_base.main(globals(), __name__ == "__main__")
