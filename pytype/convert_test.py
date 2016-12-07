"""Tests for convert.py."""


from pytype import abstract
from pytype import config
from pytype import errors
from pytype import utils
from pytype import vm

import unittest


class ConvertTest(unittest.TestCase):

  def setUp(self):
    self._vm = vm.VirtualMachine(errors.ErrorLog(), config.Options([""]))

  def _load_ast(self, name, src):
    with utils.Tempdir() as d:
      d.create_file(name + ".pyi", src)
      self._vm.options.tweak(pythonpath=[d.path])
      return self._vm.loader.import_name(name)

  def _convert_class(self, name, ast):
    return self._vm.convert.convert_constant_to_value(
        name, ast.Lookup(name), {}, self._vm.root_cfg_node)

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
      x = ...  # type: Dict[str]
    """)
    val = self._vm.convert.convert_constant_to_value(
        "x", ast.Lookup("a.x").type, {}, self._vm.root_cfg_node)
    self.assertIs(val.type_parameters["K"],
                  abstract.get_atomic_value(self._vm.convert.str_type))
    self.assertIs(val.type_parameters["V"], self._vm.convert.unsolvable)


if __name__ == "__main__":
  unittest.main()
