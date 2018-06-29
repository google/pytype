"""Utility class and function for tests."""

import collections

from pytype import compat
from pytype import state as frame_state
from pytype.pyc import loadmarshal


FakeCode = collections.namedtuple("FakeCode", "co_filename co_name")


class FakeOpcode(object):
  """Util class for generating fake Opcode for testing."""

  def __init__(self, filename, line, methodname):
    self.code = FakeCode(filename, methodname)
    self.line = line

  def to_stack(self):
    return [frame_state.SimpleFrame(self)]


def fake_stack(length):
  return [frame_state.SimpleFrame(FakeOpcode("foo.py", i, "function%d" % i))
          for i in range(length)]


class OperatorsTestMixin(object):
  """Mixin providing utilities for operators tests."""

  def check_expr(self, expr, assignments, expected_return):
    """Check the expression."""
    # Note that testing "1+2" as opposed to "x=1; y=2; x+y" doesn't really test
    # anything because the peephole optimizer converts "1+2" to "3" and __add__
    # isn't called. So, need to defeat the optimizer by replacing the constants
    # by variables, which will result in calling __add__ et al.

    # Join the assignments with ";" to avoid figuring out the exact indentation:
    assignments = "; ".join(assignments)
    src = """
      def f():
        {assignments}
        return {expr}
      f()
    """.format(expr=expr, assignments=assignments)
    ty = self.Infer(src, deep=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), expected_return)

  def check_binary(self, function_name, op):
    """Check the binary operator."""
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self, unused_x):
          return 3j
      class Bar(object):
        pass
      def f():
        return Foo() {op} Bar()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def check_unary(self, function_name, op, ret=None):
    """Check the unary operator."""
    ty = self.Infer("""
      class Foo(object):
        def {function_name}(self):
          return 3j
      def f():
        return {op} Foo()
      f()
    """.format(function_name=function_name, op=op),
                    deep=False,
                    show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), ret or self.complex)

  def check_reverse(self, function_name, op):
    """Check the reverse operator."""
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      class Bar(Foo):
        def __r{function_name}__(self, x):
          return "foo"
      def f():
        return Foo() {op} 1  # use Foo.__{function_name}__
      def g():
        return 1 {op} Bar()  # use Bar.__r{function_name}__
      def h():
        return Foo() {op} Bar()  # use Bar.__r{function_name}__
      def i():
        return Foo() {op} Foo()  # use Foo.__{function_name}__
      f(); g(); h(); i()
    """.format(op=op, function_name=function_name),
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)
    self.assertHasReturnType(ty.Lookup("g"), self.str)
    self.assertHasReturnType(ty.Lookup("h"), self.str)
    self.assertHasReturnType(ty.Lookup("i"), self.complex)

  def check_inplace(self, function_name, op):
    """Check the inplace operator."""
    ty = self.Infer("""
      class Foo(object):
        def __{function_name}__(self, x):
          return 3j
      def f():
        x = Foo()
        x {op} None
        return x
      f()
    """.format(op=op, function_name=function_name),
                    deep=False,
                    show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.complex)


# TODO(sivachandra): Remove this class in favor of the class OperatorsTestMixin.
# It is not a drop-in-replacement currently, but there is no reason why it
# cannot be made one.
class InplaceTestMixin(object):
  """Mixin providing a method to check in-place operators."""

  def _check_inplace(self, op, assignments, expected_return):
    """Check the inplace operator."""
    assignments = "; ".join(assignments)
    src = """
      def f(x, y):
        {assignments}
        x {op}= y
        return x
      a = f(1, 2)
    """.format(assignments=assignments, op=op)
    ty = self.Infer(src, deep=False)
    self.assertTypeEquals(ty.Lookup("a").type, expected_return)


class TestCollectionsMixin(object):
  """Mixin providing utils for tests on the collections module."""

  def _testCollectionsObject(self, obj, good_arg, bad_arg, error):  # pylint: disable=invalid-name
    result = self.CheckWithErrors("""\
      import collections
      def f(x: collections.{obj}): ...
      f({good_arg})
      f({bad_arg})  # line 5
    """.format(obj=obj, good_arg=good_arg, bad_arg=bad_arg))
    self.assertErrorLogIs(result, [(4, "wrong-arg-types", error)])


class MakeCodeMixin(object):
  """Mixin providing a method to make a code object from bytecode."""

  def make_code(self, int_array, name="testcode"):
    """Utility method for creating CodeType objects."""
    return loadmarshal.CodeType(
        argcount=0, kwonlyargcount=0, nlocals=2, stacksize=2, flags=0,
        consts=[None, 1, 2], names=[], varnames=["x", "y"], filename="",
        name=name, firstlineno=1, lnotab=[], freevars=[], cellvars=[],
        code=compat.int_array_to_bytes(int_array),
        python_version=self.python_version)
