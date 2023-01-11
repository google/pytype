"""Test functions with complex cfg."""
# Regression test to make sure our large constant optimizations don't affect
# functions with complex control flow (since we use the number of bindings a
# variable has as a proxy for large literals, a function with many internal
# branches can trigger a false positive in its return value).
#
# Test case taken from lib2to3/pgen2/tokenize.py


from pytype.tests import test_base
from pytype.tests import test_utils


class TestComplexFunction(test_base.BaseTest):
  """Test function with complex cfg."""

  def test_function_not_optimized(self):
    # If we do not analyse generate_tokens with full filtering, some of the
    # return branches will be None and the iterator will raise a type error.
    code = test_utils.test_data_file("tokenize.py")
    with self.DepTree([("foo.py", code)]):
      self.Check("""
        import io
        import foo
        stream = io.StringIO("")
        tokens = foo.generate_tokens(stream.readline)
        for tok_type, tok_str, _, _, _ in tokens:
          pass
      """)


if __name__ == "__main__":
  test_base.main()
