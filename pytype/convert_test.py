"""Tests for convert.py."""

from pytype import abstract
from pytype import abstract_utils
from pytype import config
from pytype import errors
from pytype import file_utils
from pytype import load_pytd
from pytype import vm
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.tests import test_base
import six

import unittest


class ConvertTest(test_base.UnitTest):

  def setUp(self):
    super().setUp()
    options = config.Options.create(python_version=self.python_version)
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))

  def _load_ast(self, name, src):
    with file_utils.Tempdir() as d:
      d.create_file(name + ".pyi", src)
      self._vm.loader.pythonpath = [d.path]  # monkeypatch
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
    cls_meta = self._convert_class("a.B", ast).cls
    subcls_meta = self._convert_class("a.C", ast).cls
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
    cls_meta = self._convert_class("a.B", ast).cls
    subcls_meta = self._convert_class("a.C", ast).cls
    self.assertEqual(meta, cls_meta)
    self.assertEqual(meta, subcls_meta)

  def test_generic_with_any_param(self):
    ast = self._load_ast("a", """
      from typing import Dict
      x = ...  # type: Dict[str]
    """)
    val = self._vm.convert.constant_to_value(
        ast.Lookup("a.x").type, {}, self._vm.root_cfg_node)
    self.assertIs(val.formal_type_parameters[abstract_utils.K],
                  self._vm.convert.str_type)
    self.assertIs(val.formal_type_parameters[abstract_utils.V],
                  self._vm.convert.unsolvable)

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
        abstract_utils.AsInstance(x), {}, self._vm.root_cfg_node)
    self.assertIsInstance(cls, abstract.TupleClass)
    six.assertCountEqual(self, cls.formal_type_parameters.items(),
                         [(0, self._vm.convert.str_type),
                          (1, self._vm.convert.int_type),
                          (abstract_utils.T, abstract.Union([
                              cls.formal_type_parameters[0],
                              cls.formal_type_parameters[1],
                          ], self._vm))])
    self.assertIsInstance(instance, abstract.Tuple)
    self.assertListEqual([v.data for v in instance.pyval],
                         [[self._vm.convert.primitive_class_instances[str]],
                          [self._vm.convert.primitive_class_instances[int]]])
    # The order of option elements in Union is random
    six.assertCountEqual(
        self, instance.get_instance_type_parameter(abstract_utils.T).data,
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

  def test_boolean_constants(self):
    true = self._vm.convert.constant_to_value(True, {}, self._vm.root_cfg_node)
    self.assertEqual(true, self._vm.convert.true)
    false = self._vm.convert.constant_to_value(
        False, {}, self._vm.root_cfg_node)
    self.assertEqual(false, self._vm.convert.false)

  def test_callable_with_args(self):
    ast = self._load_ast("a", """
      from typing import Callable
      x = ...  # type: Callable[[int, bool], str]
    """)
    x = ast.Lookup("a.x").type
    cls = self._vm.convert.constant_to_value(x, {}, self._vm.root_cfg_node)
    instance = self._vm.convert.constant_to_value(
        abstract_utils.AsInstance(x), {}, self._vm.root_cfg_node)
    self.assertIsInstance(cls, abstract.CallableClass)
    six.assertCountEqual(
        self,
        cls.formal_type_parameters.items(),
        [(0, self._vm.convert.int_type),
         (1, self._vm.convert.primitive_classes[bool]),
         (abstract_utils.ARGS, abstract.Union(
             [cls.formal_type_parameters[0], cls.formal_type_parameters[1]],
             self._vm)),
         (abstract_utils.RET, self._vm.convert.str_type)])
    self.assertIsInstance(instance, abstract.Instance)
    self.assertEqual(instance.cls, cls)
    six.assertCountEqual(
        self,
        [(name, set(var.data))
         for name, var in instance.instance_type_parameters.items()],
        [(abstract_utils.full_type_name(instance, abstract_utils.ARGS),
          {self._vm.convert.primitive_class_instances[int],
           self._vm.convert.primitive_class_instances[bool]}),
         (abstract_utils.full_type_name(instance, abstract_utils.RET),
          {self._vm.convert.primitive_class_instances[str]})])

  def test_callable_no_args(self):
    ast = self._load_ast("a", """
      from typing import Callable
      x = ... # type: Callable[[], ...]
    """)
    x = ast.Lookup("a.x").type
    cls = self._vm.convert.constant_to_value(x, {}, self._vm.root_cfg_node)
    instance = self._vm.convert.constant_to_value(
        abstract_utils.AsInstance(x), {}, self._vm.root_cfg_node)
    self.assertIsInstance(
        cls.get_formal_type_parameter(abstract_utils.ARGS), abstract.Empty)
    self.assertEqual(abstract_utils.get_atomic_value(
        instance.get_instance_type_parameter(abstract_utils.ARGS)),
                     self._vm.convert.empty)

  def test_plain_callable(self):
    ast = self._load_ast("a", """
      from typing import Callable
      x = ...  # type: Callable[..., int]
    """)
    x = ast.Lookup("a.x").type
    cls = self._vm.convert.constant_to_value(x, {}, self._vm.root_cfg_node)
    instance = self._vm.convert.constant_to_value(
        abstract_utils.AsInstance(x), {}, self._vm.root_cfg_node)
    self.assertIsInstance(cls, abstract.ParameterizedClass)
    six.assertCountEqual(self, cls.formal_type_parameters.items(),
                         [(abstract_utils.ARGS, self._vm.convert.unsolvable),
                          (abstract_utils.RET, self._vm.convert.int_type)])
    self.assertIsInstance(instance, abstract.Instance)
    self.assertEqual(instance.cls, cls.base_cls)
    six.assertCountEqual(
        self,
        [(name, var.data)
         for name, var in instance.instance_type_parameters.items()],
        [(abstract_utils.full_type_name(instance, abstract_utils.ARGS),
          [self._vm.convert.unsolvable]),
         (abstract_utils.full_type_name(instance, abstract_utils.RET),
          [self._vm.convert.primitive_class_instances[int]])])

  def test_function_with_starargs(self):
    ast = self._load_ast("a", """
      def f(*args: int): ...
    """)
    f = self._vm.convert.constant_to_value(
        ast.Lookup("a.f"), {}, self._vm.root_cfg_node)
    sig, = f.signatures
    annot = sig.signature.annotations["args"]
    self.assertEqual(pytd_utils.Print(annot.get_instance_type()),
                     "Tuple[int, ...]")

  def test_function_with_starstarargs(self):
    ast = self._load_ast("a", """
      def f(**kwargs: int): ...
    """)
    f = self._vm.convert.constant_to_value(
        ast.Lookup("a.f"), {}, self._vm.root_cfg_node)
    sig, = f.signatures
    annot = sig.signature.annotations["kwargs"]
    self.assertEqual(pytd_utils.Print(annot.get_instance_type()),
                     "Dict[str, int]")

  def test_mro(self):
    ast = self._load_ast("a", """
      x = ...  # type: dict
    """)
    x = ast.Lookup("a.x").type
    cls = self._vm.convert.constant_to_value(x, {}, self._vm.root_cfg_node)
    self.assertListEqual([v.name for v in cls.mro],
                         ["dict", "Dict", "MutableMapping", "Mapping", "Sized",
                          "Iterable", "Container", "Generic", "Protocol",
                          "object"])

  def test_widen_type(self):
    ast = self._load_ast("a", """
      x = ...  # type: tuple[int, ...]
      y = ...  # type: dict[str, int]
    """)
    x = ast.Lookup("a.x").type
    tup = self._vm.convert.constant_to_value(x, {}, self._vm.root_cfg_node)
    widened_tup = self._vm.convert.widen_type(tup)
    self.assertEqual(pytd_utils.Print(widened_tup.get_instance_type()),
                     "Iterable[int]")
    y = ast.Lookup("a.y").type
    dct = self._vm.convert.constant_to_value(y, {}, self._vm.root_cfg_node)
    widened_dct = self._vm.convert.widen_type(dct)
    self.assertEqual(pytd_utils.Print(widened_dct.get_instance_type()),
                     "Mapping[str, int]")

  def test_abstract_method_round_trip(self):
    sig = pytd.Signature((), None, None, pytd.AnythingType(), (), ())
    f_pytd = pytd.Function(
        name="f", signatures=(sig,), kind=pytd.METHOD,
        flags=pytd.Function.abstract_flag(True))
    f = self._vm.convert.constant_to_value(f_pytd, {}, self._vm.root_cfg_node)
    self.assertTrue(f.is_abstract)
    f_out = f.to_pytd_def(self._vm.root_cfg_node, f.name)
    self.assertTrue(f_out.is_abstract)

  def test_class_abstract_method(self):
    ast = self._load_ast("a", """
      class A(object):
        @abstractmethod
        def f(self) -> int: ...
    """)
    cls = self._vm.convert.constant_to_value(
        ast.Lookup("a.A"), {}, self._vm.root_cfg_node)
    six.assertCountEqual(self, cls.abstract_methods, {"f"})

  def test_class_inherited_abstract_method(self):
    ast = self._load_ast("a", """
      class A(object):
        @abstractmethod
        def f(self) -> int: ...
      class B(A): ...
    """)
    cls = self._vm.convert.constant_to_value(
        ast.Lookup("a.B"), {}, self._vm.root_cfg_node)
    six.assertCountEqual(self, cls.abstract_methods, {"f"})

  def test_class_override_abstract_method(self):
    ast = self._load_ast("a", """
      class A(object):
        @abstractmethod
        def f(self) -> int: ...
      class B(A):
        def f(self) -> bool: ...
    """)
    cls = self._vm.convert.constant_to_value(
        ast.Lookup("a.B"), {}, self._vm.root_cfg_node)
    self.assertFalse(cls.abstract_methods)

  def test_class_override_abstract_method_still_abstract(self):
    ast = self._load_ast("a", """
      class A(object):
        @abstractmethod
        def f(self) -> int: ...
      class B(A):
        @abstractmethod
        def f(self) -> bool: ...
    """)
    cls = self._vm.convert.constant_to_value(
        ast.Lookup("a.B"), {}, self._vm.root_cfg_node)
    six.assertCountEqual(self, cls.abstract_methods, {"f"})

  def test_parameterized_class_abstract_method(self):
    ast = self._load_ast("a", """
      class A(object):
        @abstractmethod
        def f(self) -> int: ...
    """)
    cls = self._vm.convert.constant_to_value(
        ast.Lookup("a.A"), {}, self._vm.root_cfg_node)
    parameterized_cls = abstract.ParameterizedClass(cls, {}, self._vm)
    six.assertCountEqual(self, parameterized_cls.abstract_methods, {"f"})

  def test_classvar(self):
    ast = self._load_ast("a", """
      from typing import ClassVar
      class X:
        v: ClassVar[int]
    """)
    pyval = ast.Lookup("a.X").Lookup("v").type
    v = self._vm.convert.constant_to_value(pyval, {}, self._vm.root_cfg_node)
    self.assertEqual(v, self._vm.convert.int_type)

  def test_classvar_instance(self):
    ast = self._load_ast("a", """
      from typing import ClassVar
      class X:
        v: ClassVar[int]
    """)
    pyval = ast.Lookup("a.X").Lookup("v").type
    v = self._vm.convert.constant_to_value(
        abstract_utils.AsInstance(pyval), {}, self._vm.root_cfg_node)
    self.assertEqual(v, self._vm.convert.primitive_class_instances[int])

  def test_constant_name(self):
    # Test that we create a string name without crashing.
    self.assertIsInstance(self._vm.convert.constant_name(int), str)
    self.assertIsInstance(self._vm.convert.constant_name(None), str)
    self.assertIsInstance(
        self._vm.convert.constant_name((int, (str, super))), str)


if __name__ == "__main__":
  unittest.main()
