"""Tests for convert.py."""


from pytype import abstract
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype import utils
from pytype import vm

import unittest


class ConvertTest(unittest.TestCase):

  def setUp(self):
    options = config.Options([""])
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, options))

  def _load_ast(self, name, src):
    with utils.Tempdir() as d:
      d.create_file(name + ".pyi", src)
      self._vm.options.tweak(pythonpath=[d.path])
      return self._vm.loader.import_name(name)

  def _convert_class(self, name, ast):
    return self._vm.convert.constant_to_value(
        ast.Lookup(name), {}, self._vm.root_cfg_node)

  def test_convert_metaclass(self):
    ast = self._load_ast("a", """
      class A(type): ...
      class B(metaclass=A): ...
      class C(B): ...
    """)
    meta = self._convert_class("a.A", ast)
    cls_meta, = self._convert_class("a.B", ast).cls.data
    subcls_meta, = self._convert_class("a.C", ast).cls.data
    self.assertEqual(meta, cls_meta)
    self.assertEqual(meta, subcls_meta)

  def test_convert_no_metaclass(self):
    ast = self._load_ast("a", """
      class A(object): ...
    """)
    cls = self._convert_class("a.A", ast)
    self.assertIsNone(cls.cls)

  def test_convert_metaclass_with_generic(self):
    ast = self._load_ast("a", """
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class A(type): ...
      class B(Generic[T], metaclass=A): ...
      class C(B[int]): ...
    """)
    meta = self._convert_class("a.A", ast)
    cls_meta, = self._convert_class("a.B", ast).cls.data
    subcls_meta, = self._convert_class("a.C", ast).cls.data
    self.assertEqual(meta, cls_meta)
    self.assertEqual(meta, subcls_meta)

  def test_generic_with_any_param(self):
    ast = self._load_ast("a", """
      from typing import Dict
      x = ...  # type: Dict[str]
    """)
    val = self._vm.convert.constant_to_value(
        ast.Lookup("a.x").type, {}, self._vm.root_cfg_node)
    self.assertIs(val.type_parameters[abstract.K],
                  abstract.get_atomic_value(self._vm.convert.str_type))
    self.assertIs(val.type_parameters[abstract.V], self._vm.convert.unsolvable)

  def test_convert_long(self):
    val = self._vm.convert.constant_to_value(2**64, {}, self._vm.root_cfg_node)
    self.assertIs(val, self._vm.convert.primitive_class_instances[int])

  def test_heterogeneous_tuple(self):
    ast = self._load_ast("a", """
      from typing import Tuple
      x = ...  # type: Tuple[str, int]
    """)
    x = ast.Lookup("a.x").type
    cls = self._vm.convert.constant_to_value(x, {}, self._vm.root_cfg_node)
    instance = self._vm.convert.constant_to_value(
        abstract.AsInstance(x), {}, self._vm.root_cfg_node)
    self.assertIsInstance(cls, abstract.TupleClass)
    self.assertListEqual(sorted(cls.type_parameters.items()),
                         [(0, self._vm.convert.str_type.data[0]),
                          (1, self._vm.convert.int_type.data[0]),
                          (abstract.T, abstract.Union([
                              cls.type_parameters[0],
                              cls.type_parameters[1],
                          ], self._vm))])
    self.assertIsInstance(instance, abstract.Tuple)
    self.assertListEqual([v.data for v in instance.pyval],
                         [[self._vm.convert.primitive_class_instances[str]],
                          [self._vm.convert.primitive_class_instances[int]]])
    self.assertListEqual(instance.type_parameters[abstract.T].data,
                         [self._vm.convert.primitive_class_instances[str],
                          self._vm.convert.primitive_class_instances[int]])

  def test_build_bool(self):
    any_bool = self._vm.convert.build_bool(self._vm.root_cfg_node, None)
    t_bool = self._vm.convert.build_bool(self._vm.root_cfg_node, True)
    f_bool = self._vm.convert.build_bool(self._vm.root_cfg_node, False)
    self.assertEqual(any_bool.data,
                     [self._vm.convert.primitive_class_instances[bool]])
    self.assertEqual(t_bool.data, [self._vm.convert.true])
    self.assertEqual(f_bool.data, [self._vm.convert.false])


if __name__ == "__main__":
  unittest.main()
