import textwrap

from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.rewrite import vm as vm_lib
from pytype.rewrite.abstract import abstract
from pytype.rewrite.tests import test_utils

import unittest


def _make(src: str) -> abstract.BaseValue:
  vm = vm_lib.VirtualMachine.from_source(textwrap.dedent(src))
  vm._run_module()
  return list(vm._module_frame.final_locals.values())[-1]


class OutputTestBase(test_utils.ContextfulTestBase):

  def assertPytdEqual(self, pytd_node, expected_str):
    actual_str = pytd_utils.Print(pytd_node).strip()
    expected_str = textwrap.dedent(expected_str).strip()
    self.assertMultiLineEqual(actual_str, expected_str)


class ClassToPytdDefTest(OutputTestBase):

  def test_constant(self):
    cls = _make("""
      class C:
        X = 0
    """)
    pytd_cls = self.ctx.pytd_converter.to_pytd_def(cls)
    self.assertPytdEqual(pytd_cls, """
      class C:
          X: ClassVar[int]
    """)

  def test_method(self):
    cls = _make("""
      class C:
        def f(self):
          return 0
    """)
    pytd_cls = self.ctx.pytd_converter.to_pytd_def(cls)
    self.assertPytdEqual(pytd_cls, """
      class C:
          def f(self) -> int: ...
    """)

  def test_nested_class(self):
    cls = _make("""
      class C:
        class D:
          pass
    """)
    pytd_cls = self.ctx.pytd_converter.to_pytd_def(cls)
    self.assertPytdEqual(pytd_cls, """
      class C:
          class D: ...
    """)

  def test_instance_attribute(self):
    cls = _make("""
      class C:
        def __init__(self):
          self.x = 42
    """)
    pytd_cls = self.ctx.pytd_converter.to_pytd_def(cls)
    self.assertPytdEqual(pytd_cls, """
      class C:
          x: int
          def __init__(self) -> None: ...
    """)


class FunctionToPytdDefTest(OutputTestBase):

  def test_basic(self):
    func = _make("""
      def f(x, /, y, *args, z, **kwargs):
        return 42
    """)
    pytd_func = self.ctx.pytd_converter.to_pytd_def(func)
    self.assertPytdEqual(pytd_func, """
      def f(x, /, y, *args, z, **kwargs) -> int: ...
    """)

  # TODO(b/241479600): Once the MAKE_FUNCTION opcode is fully supported, add
  # annotations and defaults in the code rather than directly manipulating the
  # signature objects.
  # pytype: disable=attribute-error
  def test_param_annotation(self):
    func = _make("""
      def f(x):
        pass
    """)
    func.signatures[0].annotations['x'] = (
        abstract.SimpleClass(self.ctx, 'C', {}))
    pytd_func = self.ctx.pytd_converter.to_pytd_def(func)
    self.assertPytdEqual(pytd_func, 'def f(x: C) -> None: ...')

  def test_return_annotation(self):
    func = _make("""
      def f():
        pass
    """)
    func.signatures[0].annotations['return'] = (
        abstract.SimpleClass(self.ctx, 'C', {}))
    pytd_func = self.ctx.pytd_converter.to_pytd_def(func)
    self.assertPytdEqual(pytd_func, 'def f() -> C: ...')

  def test_default(self):
    func = _make("""
      def f(x):
        pass
    """)
    func.signatures[0].defaults['x'] = abstract.PythonConstant(self.ctx, 0)
    pytd_func = self.ctx.pytd_converter.to_pytd_def(func)
    self.assertPytdEqual(pytd_func, 'def f(x = ...) -> None: ...')
  # pytype: enable=attribute-error


class ToPytdTypeTest(OutputTestBase):

  def test_any(self):
    self.assertEqual(self.ctx.pytd_converter.to_pytd_type(self.ctx.ANY),
                     pytd.AnythingType())

  def test_constant(self):
    t = self.ctx.pytd_converter.to_pytd_type(
        abstract.PythonConstant(self.ctx, 0))
    self.assertPytdEqual(t, 'int')

  def test_class(self):
    t = self.ctx.pytd_converter.to_pytd_type(
        abstract.SimpleClass(self.ctx, 'C', {}))
    self.assertPytdEqual(t, 'Type[C]')

  def test_mutable_instance(self):
    instance = abstract.MutableInstance(
        self.ctx, abstract.SimpleClass(self.ctx, 'C', {}))
    self.assertPytdEqual(self.ctx.pytd_converter.to_pytd_type(instance), 'C')

  def test_frozen_instance(self):
    instance = abstract.MutableInstance(
        self.ctx, abstract.SimpleClass(self.ctx, 'C', {})).freeze()
    self.assertPytdEqual(self.ctx.pytd_converter.to_pytd_type(instance), 'C')

  def test_precise_callable(self):
    func = _make("""
      def f(x):
        pass
    """)
    self.assertPytdEqual(self.ctx.pytd_converter.to_pytd_type(func),
                         'Callable[[Any], None]')

  def test_any_args_callable(self):
    func = _make("""
      def f(*args):
        return 42
    """)
    self.assertPytdEqual(self.ctx.pytd_converter.to_pytd_type(func),
                         'Callable[..., int]')

  def test_union(self):
    union = abstract.Union(self.ctx, (abstract.PythonConstant(self.ctx, 0),
                                      abstract.PythonConstant(self.ctx, None)))
    self.assertPytdEqual(self.ctx.pytd_converter.to_pytd_type(union),
                         'Optional[int]')


class ToPytdInstanceTypeTest(OutputTestBase):

  def test_any(self):
    self.assertEqual(
        self.ctx.pytd_converter.to_pytd_type_of_instance(self.ctx.ANY),
        pytd.AnythingType())

  def test_class(self):
    cls = abstract.SimpleClass(self.ctx, 'C', {})
    self.assertPytdEqual(
        self.ctx.pytd_converter.to_pytd_type_of_instance(cls), 'C')

  def test_union(self):
    union = abstract.Union(self.ctx, (abstract.SimpleClass(self.ctx, 'C', {}),
                                      abstract.SimpleClass(self.ctx, 'D', {})))
    self.assertPytdEqual(
        self.ctx.pytd_converter.to_pytd_type_of_instance(union), 'Union[C, D]')


if __name__ == '__main__':
  unittest.main()
