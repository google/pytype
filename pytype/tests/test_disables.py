"""Tests for disabling errors."""

from pytype.tests import test_base
from pytype.tests import test_utils


class DisableTest(test_base.BaseTest):
  """Test error disabling."""

  def test_invalid_directive(self):
    _, errors = self.InferWithErrors("""
      x = 1  # pytype: this is not a valid pytype directive.  # invalid-directive
    """)
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def test_invalid_disable_error_name(self):
    _, errors = self.InferWithErrors("""
      x = 1  # pytype: disable=not-an-error.  # invalid-directive[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Invalid error name.*not-an-error"})
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def test_disable_error(self):
    self.InferWithErrors("""
      x = a  # name-error
      x = b  # pytype: disable=name-error
      x = c  # name-error
    """)

  def test_open_ended_directive(self):
    """Test that disables in the middle of the file can't be left open-ended."""
    _, errors = self.InferWithErrors("""
      '''This is a docstring.
      def f(x):
        pass
      class A:
        pass
      The above definitions should be ignored.
      '''
      # pytype: disable=attribute-error  # ok (before first class/function def)
      CONSTANT = 42
      # pytype: disable=not-callable  # ok (before first class/function def)
      def f(x):
        # type: ignore  # late-directive[e1]
        pass
      def g(): pass
      x = y  # pytype: disable=name-error  # ok (single line)
      # pytype: disable=attribute-error  # ok (re-enabled)
      # pytype: disable=wrong-arg-types  # late-directive[e2]
      # pytype: enable=attribute-error
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Type checking", "e2": r"wrong-arg-types"})
    # late-directive is a warning
    self.assertFalse(errors.has_error())

  def test_skip_file(self):
    self.Check("""
      # pytype: skip-file
      name_error
    """)

  def test_implicit_return(self):
    """Test that the return is attached to the last line of the function."""
    # In python 3.10+ the bytecode line number for the RETURN None is at the
    # enclosing control flow statement that falls through to the end. We adjust
    # it before reporting the error. In 3.9- it is already set to the last line
    # of the function.
    self.Check("""
      class A:
        def f(self) -> str:
          if __random__:
            if __random__:
              return "a"  # pytype: disable=bad-return-type

      def g() -> str:
        pass  # pytype: disable=bad-return-type

      def h() -> str:
        return ([1,
                 2,
                 3])  # pytype: disable=bad-return-type
    """)

  def test_implicit_return_empty_function(self):
    # Check that we find the start of a function correctly and not the end of
    # the previous one.
    self.Check("""
      def f():
        pass

      def j() -> str:
        '''docstring'''  # pytype: disable=bad-return-type
    """)

  @test_utils.skipBeforePy((3, 8), "RETURN_VALUE opcode lineno changed in 3.8")
  def test_implicit_return_not_at_end(self):
    self.Check("""
      import logging
      def f() -> str:
        try:
          return ''
        except KeyError:
          logging.exception(  # pytype: disable=bad-return-type
              'oops')
    """)

  def test_implicit_return_annotated_nested_function(self):
    self.Check("""
      import logging
      def f():
        def g() -> str:
          try:
            return ''
          except:
            logging.exception('oops')  # pytype: disable=bad-return-type
        return g
    """)

  def test_implicit_return_annotated_outer_function(self):
    self.Check("""
      def f() -> str:
        def g():
          pass
        pass  # pytype: disable=bad-return-type
    """)

  def test_silence_variable_mismatch(self):
    self.Check("""
      x = [
          0,
      ]  # type: None  # pytype: disable=annotation-type-mismatch
    """)

  def test_disable_location(self):
    self.Check("""
      import re
      re.sub(
        '', object(), '')  # pytype: disable=wrong-arg-types
    """)

  def test_skip_file_with_comment(self):
    self.Check("""
      # pytype: skip-file  # extra comment here
      import nonsense
    """)

  def test_missing_parameter_disable(self):
    self.Check("""
      class Foo:
        def __iter__(self, x, y):
          pass
      def f(x):
        pass
      f(
        x=[x for x in Foo],  # pytype: disable=missing-parameter
      )
    """)

  def test_silence_parameter_mismatch(self):
    self.Check("""
      def f(
        x: int = 0.0,
        y: str = '',
        **kwargs,
      ):  # pytype: disable=annotation-type-mismatch
        pass
    """)

  @test_utils.skipFromPy((3, 8), "MAKE_FUNCTION opcode lineno changes in 3.8")
  def test_do_not_silence_parameter_mismatch_pre38(self):
    self.CheckWithErrors("""
      def f(
        x: int = 0.0,
        y: str = '',  # annotation-type-mismatch
        **kwargs,
      ):
        pass  # pytype: disable=annotation-type-mismatch
    """)

  @test_utils.skipBeforePy((3, 8), "MAKE_FUNCTION opcode lineno changes in 3.8")
  def test_do_not_silence_parameter_mismatch(self):
    self.CheckWithErrors("""
      def f(  # annotation-type-mismatch
        x: int = 0.0,
        y: str = '',
        **kwargs,
      ):
        pass  # pytype: disable=annotation-type-mismatch
    """)

  def test_container_disable(self):
    self.Check("""
      x: list[int] = []
      x.append(
          ''
      )  # pytype: disable=container-type-mismatch
    """)

  def test_multiple_directives(self):
    """We should support multiple directives on one line."""
    self.Check("""
      a = list() # type: list[int, str]  # pytype: disable=invalid-annotation
      b = list() # pytype: disable=invalid-annotation  # type: list[int, str]
      def foo(x): pass
      c = foo(a, b.i) # pytype: disable=attribute-error  # pytype: disable=wrong-arg-count
    """)

  def test_bare_annotation(self):
    self.Check("""
      from typing import AnyStr
      def f():
        x: AnyStr  # pytype: disable=invalid-annotation
    """)


class AttributeErrorDisableTest(test_base.BaseTest):
  """Test attribute-error disabling."""

  def test_disable(self):
    self.Check("""
      x = [None]
      y = ''.join(z.oops
                  for z in x)  # pytype: disable=attribute-error
    """)

  def test_method_disable(self):
    self.Check("""
      x = [None]
      y = ''.join(z.oops()
                  for z in x)  # pytype: disable=attribute-error
    """)

  def test_iter_disable(self):
    self.Check("""
      x = [y for y in None
          ]  # pytype: disable=attribute-error
    """)

  def test_unpack_disable(self):
    self.Check("""
      x, y, z = (
        None)  # pytype: disable=attribute-error
    """)

  def test_contextmanager_disable(self):
    self.Check("""
      def f():
        return None
      with f(
          ):  # pytype: disable=attribute-error
        pass
    """)

  def test_regular_disable(self):
    self.Check("""
      class Foo:
        pass
      def f(a):
        pass
      f(
          Foo.nonexistent)  # pytype: disable=attribute-error
    """)


if __name__ == "__main__":
  test_base.main()
