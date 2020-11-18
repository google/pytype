"""Tests for abstract.py."""

from pytype import abstract
from pytype import abstract_utils
from pytype import config
from pytype import errors
from pytype import function
from pytype import load_pytd
from pytype import special_builtins
from pytype import state as frame_state
from pytype import vm
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.typegraph import cfg
import six

import unittest


class AbstractTestBase(test_base.UnitTest):

  def setUp(self):
    super().setUp()
    options = config.Options.create(python_version=self.python_version)
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))
    self._program = self._vm.program
    self._node = self._vm.root_cfg_node.ConnectNew("test_node")

  def new_var(self, *values):
    """Create a Variable bound to the given values."""
    var = self._program.NewVariable()
    for value in values:
      var.AddBinding(value, source_set=(), where=self._node)
    return var

  def new_dict(self, **kwargs):
    """Create a Dict from keywords mapping names to Variable objects."""
    d = abstract.Dict(self._vm)
    for name, var in kwargs.items():
      d.set_str_item(self._node, name, var)
    return d


class IsInstanceTest(AbstractTestBase):

  def setUp(self):
    super().setUp()
    self._is_instance = special_builtins.IsInstance.make(self._vm)
    # Easier access to some primitive instances.
    self._bool = self._vm.convert.primitive_class_instances[bool]
    self._int = self._vm.convert.primitive_class_instances[int]
    self._str = self._vm.convert.primitive_class_instances[str]
    # Values that represent primitive classes.
    self._obj_class = self._vm.convert.primitive_classes[object]
    self._int_class = self._vm.convert.primitive_classes[int]
    self._str_class = self._vm.convert.primitive_classes[str]

  def assert_call(self, expected, left, right):
    """Check that call() returned the desired results.

    Args:
      expected: A dict from values to source sets, where a source set is
          represented by the sorted binding names separated by spaces, for
          example "left:0 right:1" would indicate binding #0 of variable
          "left" and binding #1 of variable "right".
      left: A Variable to use as the first arg to call().
      right: A Variable to use as the second arg to call().
    """
    name_map = {left: "left", right: "right"}
    node, result = self._is_instance.call(
        self._node, None, function.Args(
            (left, right), self.new_dict(), None, None))
    self.assertIn(node, self._node.outgoing)
    result_map = {}
    # Turning source sets into canonical string representations of the binding
    # names makes it much easier to debug failures.
    for b in result.bindings:
      terms = set()
      for o in b.origins:
        self.assertEqual(node, o.where)
        for sources in o.source_sets:
          terms.add(" ".join(sorted(
              "%s:%d" % (name_map[b.variable], b.variable.bindings.index(b))
              for b in sources)))
      result_map[b.data] = terms
    self.assertEqual(expected, result_map)

  def test_call_single_bindings(self):
    right = self.new_var(self._str_class)
    left = self.new_var(self._str)
    self.assert_call(
        {self._vm.convert.true: {"left:0 right:0"}},
        left, right)
    left = self.new_var(self._int)
    self.assert_call(
        {self._vm.convert.false: {"left:0 right:0"}},
        left, right)
    left = self.new_var(abstract.Unknown(self._vm))
    self.assert_call(
        {self._bool: {"left:0 right:0"}},
        left, right)

  def test_call_multiple_bindings(self):
    left = self.new_var(self._int, self._str)
    right = self.new_var(self._int_class, self._str_class)
    self.assert_call(
        {
            self._vm.convert.true: {"left:0 right:0", "left:1 right:1"},
            self._vm.convert.false: {"left:0 right:1", "left:1 right:0"},
        }, left, right)

  def test_call_wrong_argcount(self):
    self._vm.push_frame(frame_state.SimpleFrame())
    node, result = self._is_instance.call(
        self._node, None, function.Args((), self.new_dict(), None, None))
    self.assertEqual(self._node, node)
    self.assertIsInstance(abstract_utils.get_atomic_value(result),
                          abstract.Unsolvable)
    six.assertRegex(self, str(self._vm.errorlog), "missing-parameter")

  def test_call_wrong_keywords(self):
    self._vm.push_frame(frame_state.SimpleFrame())
    x = self.new_var(abstract.Unknown(self._vm))
    node, result = self._is_instance.call(
        self._node, None, function.Args(
            (x, x), self.new_dict(foo=x), None, None))
    self.assertEqual(self._node, node)
    self.assertIsInstance(abstract_utils.get_atomic_value(result),
                          abstract.Unsolvable)
    six.assertRegex(self, str(self._vm.errorlog),
                    r"foo.*isinstance.*\[wrong-keyword-args\]")

  def test_is_instance(self):
    def check(expected, left, right):
      self.assertEqual(expected, self._is_instance._is_instance(left, right))

    # Unknown and Unsolvable are ambiguous.
    check(None, abstract.Unknown(self._vm), self._obj_class)
    check(None, abstract.Unsolvable(self._vm), self._obj_class)

    # If the object's class has multiple bindings, result is ambiguous.
    obj = abstract.SimpleAbstractValue("foo", self._vm)
    check(None, obj, self._obj_class)
    obj.set_class(self._node, self.new_var(
        self._str_class, self._int_class))
    check(None, obj, self._str_class)

    # If the class_spec is not a class, result is ambiguous.
    check(None, self._str, self._str)

    # Result is True/False depending on if the class is in the object's mro.
    check(True, self._str, self._obj_class)
    check(True, self._str, self._str_class)
    check(False, self._str, self._int_class)

  def test_flatten(self):
    def maybe_var(v):
      return v if isinstance(v, cfg.Variable) else self.new_var(v)

    def new_tuple(*args):
      pyval = tuple(maybe_var(a) for a in args)
      return self._vm.convert.tuple_to_value(pyval)

    def check(expected_ambiguous, expected_classes, value):
      classes = []
      ambiguous = special_builtins._flatten(value, classes)
      self.assertEqual(expected_ambiguous, ambiguous)
      self.assertEqual(expected_classes, classes)

    unknown = abstract.Unknown(self._vm)

    # Simple values.
    check(False, [self._str_class], self._str_class)
    check(True, [], self._str)
    check(True, [], unknown)

    # (str, int)
    check(False, [self._str_class, self._int_class],
          new_tuple(self._str_class, self._int_class))
    # (str, ?, int)
    check(True, [self._str_class, self._int_class],
          new_tuple(self._str_class, unknown, self._int_class))
    # (str, (int, object))
    check(False, [self._str_class, self._int_class, self._obj_class],
          new_tuple(
              self._str_class,
              new_tuple(self._int_class, self._obj_class)))
    # (str, (?, object))
    check(True, [self._str_class, self._obj_class],
          new_tuple(
              self._str_class,
              new_tuple(unknown, self._obj_class)))
    # A variable with multiple bindings is ambiguous.
    # (str, int | object)
    check(True, [self._str_class],
          new_tuple(self._str_class,
                    self.new_var(self._int_class, self._obj_class)))


class PyTDTest(AbstractTestBase):
  """Tests for abstract -> pytd type conversions."""

  def test_metaclass(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    meta = abstract.InterpreterClass("M", [], {}, None, self._vm)
    meta.official_name = "M"
    cls.cls = meta
    pytd_cls = cls.to_pytd_def(self._vm.root_cfg_node, "X")
    self.assertEqual(pytd_cls.metaclass, pytd.NamedType("M"))

  def test_inherited_metaclass(self):
    parent = abstract.InterpreterClass("X", [], {}, None, self._vm)
    parent.official_name = "X"
    meta = abstract.InterpreterClass("M", [], {}, None, self._vm)
    meta.official_name = "M"
    parent.cls = meta
    child = abstract.InterpreterClass(
        "Y", [parent.to_variable(self._vm.root_cfg_node)], {}, None, self._vm)
    self.assertIs(child.cls, parent.cls)
    pytd_cls = child.to_pytd_def(self._vm.root_cfg_node, "Y")
    self.assertIs(pytd_cls.metaclass, None)

  def test_metaclass_union(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    meta1 = abstract.InterpreterClass("M1", [], {}, None, self._vm)
    meta2 = abstract.InterpreterClass("M2", [], {}, None, self._vm)
    meta1.official_name = "M1"
    meta2.official_name = "M2"
    cls.cls = abstract.Union([meta1, meta2], self._vm)
    pytd_cls = cls.to_pytd_def(self._vm.root_cfg_node, "X")
    self.assertEqual(pytd_cls.metaclass, pytd.UnionType(
        (pytd.NamedType("M1"), pytd.NamedType("M2"))))

  def test_to_type_with_view1(self):
    # to_type(<instance of List[int or unsolvable]>, view={T: int})
    instance = abstract.List([], self._vm)
    instance.merge_instance_type_parameter(
        self._vm.root_cfg_node, abstract_utils.T, self._vm.program.NewVariable(
            [self._vm.convert.unsolvable], [], self._vm.root_cfg_node))
    param_binding = instance.get_instance_type_parameter(
        abstract_utils.T).AddBinding(
            self._vm.convert.primitive_class_instances[int], [],
            self._vm.root_cfg_node)
    view = {
        instance.get_instance_type_parameter(abstract_utils.T): param_binding}
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view=view)
    self.assertEqual("__builtin__.list", pytd_type.base_type.name)
    self.assertSetEqual({"__builtin__.int"},
                        {t.name for t in pytd_type.parameters})

  def test_to_type_with_view2(self):
    # to_type(<tuple (int or str,)>, view={0: str})
    param1 = self._vm.convert.primitive_class_instances[int]
    param2 = self._vm.convert.primitive_class_instances[str]
    param_var = param1.to_variable(self._vm.root_cfg_node)
    str_binding = param_var.AddBinding(param2, [], self._vm.root_cfg_node)
    instance = abstract.Tuple((param_var,), self._vm)
    view = {param_var: str_binding}
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view=view)
    self.assertEqual(pytd_type.parameters[0],
                     pytd.NamedType("__builtin__.str"))

  def test_to_type_with_view_and_empty_param(self):
    instance = abstract.List([], self._vm)
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view={})
    self.assertEqual("__builtin__.list", pytd_type.base_type.name)
    self.assertSequenceEqual((pytd.NothingType(),), pytd_type.parameters)

  def test_typing_container(self):
    cls = self._vm.convert.list_type
    container = abstract.AnnotationContainer("List", self._vm, cls)
    expected = pytd.GenericType(pytd.NamedType("__builtin__.list"),
                                (pytd.AnythingType(),))
    actual = container.get_instance_type(self._vm.root_cfg_node)
    self.assertEqual(expected, actual)


# TODO(rechen): Test InterpreterFunction.
class FunctionTest(AbstractTestBase):

  def _make_pytd_function(self, params, name="f"):
    pytd_params = []
    for i, p in enumerate(params):
      p_type = pytd.ClassType(p.name)
      p_type.cls = p
      pytd_params.append(
          pytd.Parameter(function.argname(i), p_type, False, False, None))
    pytd_sig = pytd.Signature(
        tuple(pytd_params), None, None, pytd.AnythingType(), (), ())
    sig = function.PyTDSignature(name, pytd_sig, self._vm)
    return abstract.PyTDFunction(name, (sig,), pytd.METHOD, self._vm)

  def _call_pytd_function(self, f, args):
    b = f.to_binding(self._vm.root_cfg_node)
    return f.call(self._vm.root_cfg_node, b, function.Args(posargs=args))

  def test_call_with_empty_arg(self):
    self.assertRaises(AssertionError, self._call_pytd_function,
                      self._make_pytd_function(params=()),
                      (self._vm.program.NewVariable(),))

  def test_call_with_bad_arg(self):
    f = self._make_pytd_function(
        (self._vm.lookup_builtin("__builtin__.str"),))
    arg = self._vm.convert.primitive_class_instances[int].to_variable(
        self._vm.root_cfg_node)
    self.assertRaises(
        function.WrongArgTypes, self._call_pytd_function, f, (arg,))

  def test_simple_call(self):
    f = self._make_pytd_function(
        (self._vm.lookup_builtin("__builtin__.str"),))
    arg = self._vm.convert.primitive_class_instances[str].to_variable(
        self._vm.root_cfg_node)
    node, ret = self._call_pytd_function(f, (arg,))
    self.assertIs(node, self._vm.root_cfg_node)
    retval, = ret.bindings
    self.assertIs(retval.data, self._vm.convert.unsolvable)

  def test_call_with_multiple_arg_bindings(self):
    f = self._make_pytd_function(
        (self._vm.lookup_builtin("__builtin__.str"),))
    arg = self._vm.program.NewVariable()
    arg.AddBinding(self._vm.convert.primitive_class_instances[str], [],
                   self._vm.root_cfg_node)
    arg.AddBinding(self._vm.convert.primitive_class_instances[int], [],
                   self._vm.root_cfg_node)
    node, ret = self._call_pytd_function(f, (arg,))
    self.assertIs(node, self._vm.root_cfg_node)
    retval, = ret.bindings
    self.assertIs(retval.data, self._vm.convert.unsolvable)

  def test_call_with_skipped_combination(self):
    f = self._make_pytd_function(
        (self._vm.lookup_builtin("__builtin__.str"),))
    node = self._vm.root_cfg_node.ConnectNew()
    arg = self._vm.convert.primitive_class_instances[str].to_variable(node)
    node, ret = self._call_pytd_function(f, (arg,))
    self.assertIs(node, self._vm.root_cfg_node)
    self.assertFalse(ret.bindings)

  def test_signature_from_pytd(self):
    # def f(self: Any, *args: Any)
    self_param = pytd.Parameter("self", pytd.AnythingType(), False, False, None)
    args_param = pytd.Parameter("args", pytd.AnythingType(), False, True, None)
    sig = function.Signature.from_pytd(
        self._vm, "f", pytd.Signature(
            (self_param,), args_param, None, pytd.AnythingType(), (), ()))
    self.assertEqual(repr(sig), "def f(self: Any, *args: Any) -> Any")
    self.assertEqual(sig.name, "f")
    self.assertSequenceEqual(sig.param_names, ("self",))
    self.assertEqual(sig.varargs_name, "args")
    self.assertFalse(sig.kwonly_params)
    self.assertIs(sig.kwargs_name, None)
    self.assertSetEqual(set(sig.annotations), {"self", "args", "return"})
    self.assertTrue(sig.has_return_annotation)
    self.assertTrue(sig.has_param_annotations)

  def test_signature_from_callable(self):
    # Callable[[int, str], Any]
    params = {0: self._vm.convert.int_type, 1: self._vm.convert.str_type}
    params[abstract_utils.ARGS] = abstract.Union(
        (params[0], params[1]), self._vm)
    params[abstract_utils.RET] = self._vm.convert.unsolvable
    callable_val = abstract.CallableClass(
        self._vm.convert.function_type, params, self._vm)
    sig = function.Signature.from_callable(callable_val)
    self.assertEqual(repr(sig), "def <callable>(_0: int, _1: str) -> Any")
    self.assertEqual(sig.name, "<callable>")
    self.assertSequenceEqual(sig.param_names, ("_0", "_1"))
    self.assertIs(sig.varargs_name, None)
    self.assertFalse(sig.kwonly_params)
    self.assertIs(sig.kwargs_name, None)
    six.assertCountEqual(self, sig.annotations.keys(), sig.param_names)
    self.assertFalse(sig.has_return_annotation)
    self.assertTrue(sig.has_param_annotations)

  def test_signature_annotations(self):
    # def f(self: Any, *args: Any)
    self_param = pytd.Parameter("self", pytd.AnythingType(), False, False, None)
    # Imitate the parser's conversion of '*args: Any' to '*args: Tuple[Any]'.
    tup = pytd.ClassType("__builtin__.tuple")
    tup.cls = self._vm.convert.tuple_type.pytd_cls
    any_tuple = pytd.GenericType(tup, (pytd.AnythingType(),))
    args_param = pytd.Parameter("args", any_tuple, False, True, None)
    sig = function.Signature.from_pytd(
        self._vm, "f", pytd.Signature(
            (self_param,), args_param, None, pytd.AnythingType(), (), ()))
    self.assertEqual(repr(sig),
                     "def f(self: Any, *args: Tuple[Any, ...]) -> Any")
    self.assertIs(sig.annotations["self"], self._vm.convert.unsolvable)
    args_type = sig.annotations["args"]
    self.assertIsInstance(args_type, abstract.ParameterizedClass)
    self.assertIs(args_type.base_cls, self._vm.convert.tuple_type)
    self.assertListEqual(list(args_type.formal_type_parameters.items()),
                         [(abstract_utils.T, self._vm.convert.unsolvable)])
    self.assertIs(sig.drop_first_parameter().annotations["args"], args_type)

  def test_signature_annotations_existence(self):
    # def f(v: "X") -> "Y"
    sig = function.Signature(
        name="f",
        param_names=("v",),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={},
    )
    self.assertFalse(sig.has_param_annotations)
    self.assertFalse(sig.has_return_annotation)
    sig.set_annotation("v", self._vm.convert.unsolvable)
    self.assertTrue(sig.has_param_annotations)
    self.assertFalse(sig.has_return_annotation)
    sig.set_annotation("return", self._vm.convert.unsolvable)
    self.assertTrue(sig.has_param_annotations)
    self.assertTrue(sig.has_return_annotation)

  def test_signature_posarg_only_param_count(self):
    # def f(x): ...
    sig = function.Signature(
        name="f",
        param_names=("x",),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={},
    )
    self.assertEqual(repr(sig), "def f(x) -> Any")
    self.assertEqual(sig.mandatory_param_count(), 1)
    self.assertEqual(sig.maximum_param_count(), 1)

  def test_signature_posarg_and_kwarg_param_count(self):
    # def f(x, y=None): ...
    sig = function.Signature(
        name="f",
        param_names=("x", "y",),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={"y": self._vm.convert.none_type.to_variable(self._node)},
        annotations={},
    )
    self.assertEqual(repr(sig), "def f(x, y = None) -> Any")
    self.assertEqual(sig.mandatory_param_count(), 1)
    self.assertEqual(sig.maximum_param_count(), 2)

  def test_signature_varargs_param_count(self):
    # def f(*args): ...
    sig = function.Signature(
        name="f",
        param_names=(),
        varargs_name="args",
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={},
    )
    self.assertEqual(repr(sig), "def f(*args) -> Any")
    self.assertEqual(sig.mandatory_param_count(), 0)
    self.assertIsNone(sig.maximum_param_count())

  def test_signature_kwargs_param_count(self):
    # def f(**kwargs): ...
    sig = function.Signature(
        name="f",
        param_names=(),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name="kwargs",
        defaults={},
        annotations={},
    )
    self.assertEqual(repr(sig), "def f(**kwargs) -> Any")
    self.assertEqual(sig.mandatory_param_count(), 0)
    self.assertIsNone(sig.maximum_param_count())

  def test_signature_kwonly_param_count(self):
    # def f(*, y=None): ...
    sig = function.Signature(
        name="f",
        param_names=(),
        varargs_name=None,
        kwonly_params=("y",),
        kwargs_name=None,
        defaults={"y": self._vm.convert.none_type.to_variable(self._node)},
        annotations={},
    )
    self.assertEqual(repr(sig), "def f(*, y = None) -> Any")
    self.assertEqual(sig.mandatory_param_count(), 0)
    self.assertEqual(sig.maximum_param_count(), 1)

  def test_signature_has_param(self):
    # def f(x, *args, y, **kwargs): ...
    sig = function.Signature(
        name="f",
        param_names=("x",),
        varargs_name="args",
        kwonly_params={"y"},
        kwargs_name="kwargs",
        defaults={},
        annotations={},
    )
    self.assertEqual(repr(sig), "def f(x, *args, y, **kwargs) -> Any")
    for param in ("x", "args", "y", "kwargs"):
      self.assertTrue(sig.has_param(param))
    self.assertFalse(sig.has_param("rumpelstiltskin"))

  def test_signature_insert_varargs_and_kwargs(self):
    # def f(x, *args, y, **kwargs): ...
    sig = function.Signature(
        name="f",
        param_names=("x",),
        varargs_name="args",
        kwonly_params={"y"},
        kwargs_name="kwargs",
        defaults={},
        annotations={},
    )
    # f(1, 2, y=3, z=4)
    int_inst = self._vm.convert.primitive_class_instances[int]
    int_binding = int_inst.to_binding(self._node)
    arg_dict = {
        "x": int_binding, "_1": int_binding, "y": int_binding, "z": int_binding}
    sig = sig.insert_varargs_and_kwargs(arg_dict)
    self.assertEqual(sig.name, "f")
    self.assertSequenceEqual(sig.param_names, ("x", "_1", "z"))
    self.assertEqual(sig.varargs_name, "args")
    self.assertSetEqual(sig.kwonly_params, {"y"})
    self.assertEqual(sig.kwargs_name, "kwargs")
    self.assertFalse(sig.annotations)

  def test_signature_del_param_annotation(self):
    # def f(x) -> int: ...
    sig = function.Signature(
        name="f",
        param_names=("x",),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={"x": self._vm.convert.unsolvable,
                     "return": self._vm.convert.unsolvable},
    )
    sig.del_annotation("x")
    six.assertCountEqual(self, sig.annotations.keys(), {"return"})
    self.assertFalse(sig.has_param_annotations)
    self.assertTrue(sig.has_return_annotation)

  def test_signature_del_return_annotation(self):
    # def f(x) -> int: ...
    sig = function.Signature(
        name="f",
        param_names=("x",),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={"x": self._vm.convert.unsolvable,
                     "return": self._vm.convert.unsolvable},
    )
    sig.del_annotation("return")
    six.assertCountEqual(self, sig.annotations.keys(), {"x"})
    self.assertTrue(sig.has_param_annotations)
    self.assertFalse(sig.has_return_annotation)

  def test_signature_del_nonexistent_annotation(self):
    # def f(): ...
    sig = function.Signature(
        name="f",
        param_names=(),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={},
        annotations={},
    )
    self.assertRaises(KeyError, sig.del_annotation, "rumpelstiltskin")

  def test_constructor_args(self):
    f = abstract.PyTDFunction.make("open", self._vm, "__builtin__")
    self.assertEqual(f.full_name, "__builtin__.open")
    six.assertCountEqual(
        self,
        {sig.pytd_sig for sig in f.signatures},
        self._vm.lookup_builtin("__builtin__.open").signatures)
    self.assertIs(f.kind, pytd.METHOD)
    self.assertIs(f.vm, self._vm)

  def test_constructor_args_pyval(self):
    sig = pytd.Signature((), None, None, pytd.AnythingType(), (), ())
    pyval = pytd.Function("blah", (sig,), pytd.STATICMETHOD, 0)
    f = abstract.PyTDFunction.make("open", self._vm, "__builtin__", pyval=pyval)
    self.assertEqual(f.full_name, "__builtin__.open")
    f_sig, = f.signatures
    self.assertIs(f_sig.pytd_sig, sig)
    self.assertIs(f.kind, pytd.STATICMETHOD)
    self.assertIs(f.vm, self._vm)

  def test_get_constructor_args(self):
    f = abstract.PyTDFunction.make(
        "TypeVar", self._vm, "typing", pyval_name="_typevar_new")
    self.assertEqual(f.full_name, "typing.TypeVar")
    six.assertCountEqual(
        self,
        {sig.pytd_sig for sig in f.signatures},
        self._vm.loader.import_name("typing").Lookup(
            "typing._typevar_new").signatures)
    self.assertIs(f.kind, pytd.METHOD)
    self.assertIs(f.vm, self._vm)

  def test_bound_function_repr(self):
    f = self._make_pytd_function(params=())
    callself = self._vm.program.NewVariable(
        [abstract.AtomicAbstractValue(name, self._vm)
         for name in ("test1", "test2")], [], self._vm.root_cfg_node)
    bound = abstract.BoundFunction(callself, f)
    six.assertCountEqual(self, bound.repr_names(), ["test1.f", "test2.f"])
    six.assertRegex(self, repr(bound), r"test(1|2)\.f")

  def test_bound_function_callself_repr(self):
    f = self._make_pytd_function(params=())
    callself = self._vm.program.NewVariable(
        [abstract.AtomicAbstractValue("test", self._vm)],
        [], self._vm.root_cfg_node)
    bound = abstract.BoundFunction(callself, f)
    callself_repr = lambda v: v.name + "foo"
    six.assertCountEqual(self, bound.repr_names(callself_repr), ["testfoo.f"])

  def test_bound_function_nested_repr(self):
    f = self._make_pytd_function(params=())
    callself1 = self._vm.program.NewVariable(
        [abstract.AtomicAbstractValue("test1", self._vm)],
        [], self._vm.root_cfg_node)
    bound1 = abstract.BoundFunction(callself1, f)
    callself2 = self._vm.program.NewVariable(
        [abstract.AtomicAbstractValue("test2", self._vm)],
        [], self._vm.root_cfg_node)
    bound2 = abstract.BoundFunction(callself2, bound1)
    # `bound2` is BoundFunction(test2, BoundFunction(test1, f))
    six.assertCountEqual(self, bound2.repr_names(), ["test2.f"])

  def test_bound_function_repr_no_callself(self):
    f = self._make_pytd_function(params=())
    callself = self._vm.program.NewVariable()
    bound = abstract.BoundFunction(callself, f)
    six.assertCountEqual(self, bound.repr_names(), ["<class>.f"])

  def test_bound_function_repr_replace_parent(self):
    f = self._make_pytd_function(params=(), name="foo.f")
    callself = self._vm.program.NewVariable(
        [abstract.AtomicAbstractValue("test", self._vm)],
        [], self._vm.root_cfg_node)
    bound = abstract.BoundFunction(callself, f)
    six.assertCountEqual(self, bound.repr_names(), ["test.f"])


class AbstractMethodsTest(AbstractTestBase):

  def test_abstract_method(self):
    func = abstract.Function("f", self._vm).to_variable(self._vm.root_cfg_node)
    func.data[0].is_abstract = True
    cls = abstract.InterpreterClass("X", [], {"f": func}, None, self._vm)
    six.assertCountEqual(self, cls.abstract_methods, {"f"})

  def test_inherited_abstract_method(self):
    sized_pytd = self._vm.loader.typing.Lookup("typing.Sized")
    sized = self._vm.convert.constant_to_value(
        sized_pytd, {}, self._vm.root_cfg_node)
    cls = abstract.InterpreterClass(
        "X", [sized.to_variable(self._vm.root_cfg_node)], {}, None, self._vm)
    six.assertCountEqual(self, cls.abstract_methods, {"__len__"})

  def test_overridden_abstract_method(self):
    sized_pytd = self._vm.loader.typing.Lookup("typing.Sized")
    sized = self._vm.convert.constant_to_value(
        sized_pytd, {}, self._vm.root_cfg_node)
    bases = [sized.to_variable(self._vm.root_cfg_node)]
    members = {"__len__": self._vm.new_unsolvable(self._vm.root_cfg_node)}
    cls = abstract.InterpreterClass("X", bases, members, None, self._vm)
    self.assertFalse(cls.abstract_methods)

  def test_overridden_abstract_method_still_abstract(self):
    sized_pytd = self._vm.loader.typing.Lookup("typing.Sized")
    sized = self._vm.convert.constant_to_value(
        sized_pytd, {}, self._vm.root_cfg_node)
    bases = [sized.to_variable(self._vm.root_cfg_node)]
    func = abstract.Function("__len__", self._vm)
    func.is_abstract = True
    members = {"__len__": func.to_variable(self._vm.root_cfg_node)}
    cls = abstract.InterpreterClass("X", bases, members, None, self._vm)
    six.assertCountEqual(self, cls.abstract_methods, {"__len__"})


class SimpleFunctionTest(AbstractTestBase):

  def _make_func(self, name="_", param_names=None, varargs_name=None,
                 kwonly_params=(), kwargs_name=None, defaults=(),
                 annotations=None):
    return abstract.SimpleFunction(name, param_names or (), varargs_name,
                                   kwonly_params, kwargs_name, defaults,
                                   annotations or {}, self._vm)

  def _simple_sig(self, param_types, ret_type=None):
    annots = {("_%d" % i): t for i, t in enumerate(param_types)}
    params = tuple(annots.keys())
    if ret_type:
      annots["return"] = ret_type
    return self._make_func(param_names=params, annotations=annots)

  def test_simple_call(self):
    f = self._simple_sig([self._vm.convert.str_type],
                         ret_type=self._vm.convert.int_type)
    args = function.Args(
        (self._vm.convert.build_string(self._vm.root_cfg_node, "hello"),))
    node, ret = f.call(self._vm.root_cfg_node, f, args)
    self.assertIs(node, self._vm.root_cfg_node)
    ret_val, = ret.data
    self.assertEqual(ret_val.cls, self._vm.convert.int_type)

  def test_call_with_bad_arg(self):
    f = self._make_func(param_names=("test",),
                        annotations={"test": self._vm.convert.str_type})
    args = function.Args((self._vm.convert.build_int(self._vm.root_cfg_node),))
    self.assertRaises(function.WrongArgTypes, f.call,
                      self._vm.root_cfg_node, f, args)

  def test_call_with_no_args(self):
    f = self._simple_sig([self._vm.convert.str_type, self._vm.convert.int_type])
    args = function.Args(())
    self.assertRaises(function.MissingParameter, f.call,
                      self._vm.root_cfg_node, f, args)

  def test_call_with_multiple_arg_bindings(self):
    f = self._simple_sig([self._vm.convert.str_type])
    arg = self._vm.program.NewVariable()
    arg.AddBinding(self._vm.convert.primitive_class_instances[str], [],
                   self._vm.root_cfg_node)
    arg.AddBinding(self._vm.convert.primitive_class_instances[int], [],
                   self._vm.root_cfg_node)
    args = function.Args((arg,))
    node, ret = f.call(self._vm.root_cfg_node, f, args)
    self.assertIs(node, self._vm.root_cfg_node)
    self.assertIs(ret.data[0], self._vm.convert.none)

  def test_call_with_varargs(self):
    f = self._make_func(
        varargs_name="arg",
        annotations={"arg": self._vm.convert.str_type,
                     "return": self._vm.convert.str_type}
    )
    starargs = abstract.Tuple(
        (self._vm.convert.build_string(self._vm.root_cfg_node, ""),),
        self._vm).to_variable(self._vm.root_cfg_node)
    args = function.Args(posargs=(), starargs=starargs)
    node, ret = f.call(self._vm.root_cfg_node, f, args)
    self.assertIs(node, self._vm.root_cfg_node)
    self.assertIs(ret.data[0].cls, self._vm.convert.str_type)

  def test_call_with_bad_varargs(self):
    f = self._make_func(
        varargs_name="arg",
        annotations={"arg": self._vm.convert.str_type})
    starargs = abstract.Tuple(
        (self._vm.convert.build_string(self._vm.root_cfg_node, ""),
         self._vm.convert.build_int(self._vm.root_cfg_node)),
        self._vm
    ).to_variable(self._vm.root_cfg_node)
    args = function.Args(posargs=(), starargs=starargs)
    self.assertRaises(function.WrongArgTypes, f.call,
                      self._vm.root_cfg_node, f, args)

  def test_call_with_multiple_varargs_bindings(self):
    f = self._make_func(
        varargs_name="arg",
        annotations={"arg": self._vm.convert.str_type})
    arg = self._vm.program.NewVariable()
    arg.AddBinding(self._vm.convert.primitive_class_instances[str], [],
                   self._vm.root_cfg_node)
    arg.AddBinding(self._vm.convert.primitive_class_instances[int], [],
                   self._vm.root_cfg_node)
    starargs = abstract.Tuple((arg,), self._vm)
    starargs = starargs.to_variable(self._vm.root_cfg_node)
    args = function.Args(posargs=(), starargs=starargs)
    f.call(self._vm.root_cfg_node, f, args)

  def test_call_with_kwargs(self):
    f = self._make_func(
        kwargs_name="kwarg",
        annotations={"kwarg": self._vm.convert.str_type})
    kwargs = abstract.Dict(self._vm)
    kwargs.update(
        self._vm.root_cfg_node,
        {
            "_1": self._vm.convert.build_string(self._vm.root_cfg_node, "1"),
            "_2": self._vm.convert.build_string(self._vm.root_cfg_node, "2")
        })
    kwargs = kwargs.to_variable(self._vm.root_cfg_node)
    args = function.Args(
        posargs=(),
        namedargs=abstract.Dict(self._vm),
        starstarargs=kwargs
    )
    f.call(self._vm.root_cfg_node, f, args)

  def test_call_with_bad_kwargs(self):
    f = self._make_func(
        kwargs_name="kwarg",
        annotations={"kwarg": self._vm.convert.str_type})
    kwargs = abstract.Dict(self._vm)
    kwargs.update(self._vm.root_cfg_node,
                  {"_1": self._vm.convert.build_int(self._vm.root_cfg_node)})
    kwargs = kwargs.to_variable(self._vm.root_cfg_node)
    args = function.Args(
        posargs=(),
        namedargs=abstract.Dict(self._vm),
        starstarargs=kwargs
    )
    self.assertRaises(function.WrongArgTypes, f.call,
                      self._vm.root_cfg_node, f, args)

  def test_call_with_kwonly_args(self):
    f = self._make_func(
        param_names=("test",),
        kwonly_params=("a", "b"),
        annotations={
            "test": self._vm.convert.str_type,
            "a": self._vm.convert.str_type,
            "b": self._vm.convert.str_type
        }
    )
    kwargs = abstract.Dict(self._vm)
    kwargs.update(
        self._vm.root_cfg_node,
        {
            "a": self._vm.convert.build_string(self._vm.root_cfg_node, "2"),
            "b": self._vm.convert.build_string(self._vm.root_cfg_node, "3")
        }
    )
    kwargs = kwargs.to_variable(self._vm.root_cfg_node)
    args = function.Args(
        posargs=(self._vm.convert.build_string(self._vm.root_cfg_node, "1"),),
        namedargs=abstract.Dict(self._vm),
        starstarargs=kwargs
    )
    f.call(self._vm.root_cfg_node, f, args)
    kwargs = abstract.Dict(self._vm)
    kwargs.update(
        self._vm.root_cfg_node,
        {"b": self._vm.convert.build_string(self._vm.root_cfg_node, "3")}
    )
    kwargs = kwargs.to_variable(self._vm.root_cfg_node)
    args = function.Args(
        posargs=(self._vm.convert.build_string(self._vm.root_cfg_node, "1"),
                 self._vm.convert.build_int(self._vm.root_cfg_node)),
        namedargs=abstract.Dict(self._vm),
        starstarargs=kwargs
    )
    self.assertRaises(function.MissingParameter, f.call,
                      self._vm.root_cfg_node, f, args)

  def test_call_with_all_args(self):
    f = self._make_func(
        param_names=("a", "b", "c"),
        varargs_name="arg",
        kwargs_name="kwarg",
        defaults=(self._vm.convert.build_int(self._vm.root_cfg_node),),
        annotations={
            "a": self._vm.convert.str_type,
            "b": self._vm.convert.int_type,
            "c": self._vm.convert.int_type,
            "arg": self._vm.convert.primitive_classes[float],
            "kwarg": self._vm.convert.primitive_classes[bool]
        }
    )
    posargs = (self._vm.convert.build_string(self._vm.root_cfg_node, "1"),
               self._vm.convert.build_int(self._vm.root_cfg_node))
    float_inst = self._vm.convert.primitive_class_instances[float]
    stararg = abstract.Tuple((float_inst.to_variable(self._vm.root_cfg_node),),
                             self._vm).to_variable(self._vm.root_cfg_node)
    namedargs = abstract.Dict(self._vm)
    kwarg = abstract.Dict(self._vm)
    kwarg.update(self._vm.root_cfg_node,
                 {"x": self._vm.convert.build_bool(self._vm.root_cfg_node),
                  "y": self._vm.convert.build_bool(self._vm.root_cfg_node)})
    kwarg = kwarg.to_variable(self._vm.root_cfg_node)
    args = function.Args(posargs, namedargs, stararg, kwarg)
    f.call(self._vm.root_cfg_node, f, args)

  def test_call_with_defaults(self):
    f = self._make_func(
        param_names=("a", "b", "c"),
        defaults=(self._vm.convert.build_int(self._vm.root_cfg_node),),
        annotations={
            "a": self._vm.convert.int_type,
            "b": self._vm.convert.int_type,
            "c": self._vm.convert.int_type
        }
    )
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node))
    )
    f.call(self._vm.root_cfg_node, f, args)
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node))
    )
    f.call(self._vm.root_cfg_node, f, args)
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),))
    self.assertRaises(
        function.MissingParameter, f.call, self._vm.root_cfg_node, f, args)

  def test_call_with_bad_default(self):
    f = self._make_func(
        param_names=("a", "b"),
        defaults=(self._vm.convert.build_string(self._vm.root_cfg_node, ""),),
        annotations={
            "a": self._vm.convert.int_type,
            "b": self._vm.convert.str_type
        }
    )
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node))
    )
    self.assertRaises(
        function.WrongArgTypes, f.call, self._vm.root_cfg_node, f, args)

  def test_call_with_duplicate_keyword(self):
    f = self._simple_sig([self._vm.convert.int_type]*2)
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node)),
        namedargs={"_1": self._vm.convert.build_int(self._vm.root_cfg_node)}
    )
    self.assertRaises(
        function.DuplicateKeyword, f.call, self._vm.root_cfg_node, f, args)

  def test_call_with_wrong_arg_count(self):
    f = self._simple_sig([self._vm.convert.int_type])
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node))
    )
    self.assertRaises(
        function.WrongArgCount, f.call, self._vm.root_cfg_node, f, args)

  def test_change_defaults(self):
    f = self._make_func(
        param_names=("a", "b", "c"),
        defaults=(self._vm.convert.build_int(self._vm.root_cfg_node),)
    )
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),
                 self._vm.convert.build_int(self._vm.root_cfg_node))
    )
    f.call(self._vm.root_cfg_node, f, args)
    new_defaults = abstract.Tuple(
        (self._vm.convert.build_int(self._vm.root_cfg_node),
         self._vm.convert.build_int(self._vm.root_cfg_node)),
        self._vm).to_variable(self._vm.root_cfg_node)
    f.set_function_defaults(self._vm.root_cfg_node, new_defaults)
    f.call(self._vm.root_cfg_node, f, args)
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),)
    )
    f.call(self._vm.root_cfg_node, f, args)

  def test_call_with_type_parameter(self):
    ret_cls = abstract.ParameterizedClass(
        self._vm.convert.list_type,
        {abstract_utils.T: abstract.TypeParameter(abstract_utils.T, self._vm)},
        self._vm
    )
    f = self._make_func(
        param_names=("test",),
        annotations={
            "test": abstract.TypeParameter(abstract_utils.T, self._vm),
            "return": ret_cls
        }
    )
    args = function.Args(
        posargs=(self._vm.convert.build_int(self._vm.root_cfg_node),))
    _, ret = f.call(self._vm.root_cfg_node, f, args)
    # ret is an Instance(ParameterizedClass(list, {abstract_utils.T: int}))
    # but we really only care about T.
    self.assertIs(ret.data[0].cls.formal_type_parameters[abstract_utils.T],
                  self._vm.convert.int_type)

  def test_signature_func_output_basic(self):
    node = self._vm.root_cfg_node
    f = self._make_func(name="basic", param_names=("a", "b"))
    fp = self._vm.convert.pytd_convert.value_to_pytd_def(node, f, f.name)
    self.assertEqual(pytd_utils.Print(fp), "def basic(a, b) -> None: ...")

  def test_signature_func_output_annotations(self):
    node = self._vm.root_cfg_node
    f = self._make_func(
        name="annots",
        param_names=("a", "b"),
        annotations={
            "a": self._vm.convert.int_type,
            "b": self._vm.convert.str_type,
            "return": self._vm.convert.int_type
        }
    )
    fp = self._vm.convert.pytd_convert.value_to_pytd_def(node, f, f.name)
    self.assertEqual(pytd_utils.Print(fp),
                     "def annots(a: int, b: str) -> int: ...")

  def test_signature_func_output(self):
    node = self._vm.root_cfg_node
    dict_type = abstract.ParameterizedClass(
        self._vm.convert.dict_type,
        {abstract_utils.K: self._vm.convert.str_type,
         abstract_utils.V: self._vm.convert.int_type},
        self._vm)
    f = self._make_func(
        name="test",
        param_names=("a", "b"),
        varargs_name="c",
        kwonly_params=("d", "e"),
        kwargs_name="f",
        defaults={
            "b": self._vm.convert.build_int(node),
            "d": self._vm.convert.build_int(node)
        },
        annotations={
            "a": self._vm.convert.str_type,
            "b": self._vm.convert.int_type,
            "c": self._vm.convert.str_type,
            "d": dict_type,
            "e": self._vm.convert.int_type,
            "f": self._vm.convert.str_type,
            "return": self._vm.convert.str_type
        }
    )
    fp = self._vm.convert.pytd_convert.value_to_pytd_def(node, f, f.name)
    f_str = ("def test(a: str, b: int = ..., *c: str, d: Dict[str, int] = ...,"
             " e: int, **f: str) -> str: ...")
    self.assertEqual(pytd_utils.Print(fp), f_str)


class AbstractTest(AbstractTestBase):

  def test_interpreter_class_official_name(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    cls.update_official_name("Z")
    self.assertEqual(cls.official_name, "Z")
    cls.update_official_name("A")  # takes effect because A < Z
    self.assertEqual(cls.official_name, "A")
    cls.update_official_name("Z")  # no effect
    self.assertEqual(cls.official_name, "A")
    cls.update_official_name("X")  # takes effect because X == cls.name
    self.assertEqual(cls.official_name, "X")
    cls.update_official_name("A")  # no effect
    self.assertEqual(cls.official_name, "X")

  def test_type_parameter_official_name(self):
    param = abstract.TypeParameter("T", self._vm)
    self._vm.frame = frame_state.SimpleFrame()  # for error logging
    param.update_official_name("T")
    self.assertFalse(self._vm.errorlog.has_error())
    param.update_official_name("Q")
    self.assertTrue(self._vm.errorlog.has_error())

  def test_type_parameter_equality(self):
    param1 = abstract.TypeParameter("S", self._vm)
    param2 = abstract.TypeParameter("T", self._vm)
    cls = abstract.InterpreterClass("S", [], {}, None, self._vm)
    self.assertEqual(param1, param1)
    self.assertNotEqual(param1, param2)
    self.assertNotEqual(param1, cls)

  def test_union_equality(self):
    union1 = abstract.Union((self._vm.convert.unsolvable,), self._vm)
    union2 = abstract.Union((self._vm.convert.none,), self._vm)
    cls = abstract.InterpreterClass("Union", [], {}, None, self._vm)
    self.assertEqual(union1, union1)
    self.assertNotEqual(union1, union2)
    self.assertNotEqual(union1, cls)

  def test_instantiate_type_parameter_type(self):
    params = {
        abstract_utils.T: abstract.TypeParameter(abstract_utils.T, self._vm)}
    cls = abstract.ParameterizedClass(
        self._vm.convert.type_type, params, self._vm)
    self.assertListEqual(cls.instantiate(self._node).data,
                         [self._vm.convert.unsolvable])

  def test_super_type(self):
    supercls = special_builtins.Super(self._vm)
    self.assertEqual(supercls.get_class(), self._vm.convert.type_type)

  def test_instantiate_interpreter_class(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    # When there is no current frame, create a new instance every time.
    v1 = abstract_utils.get_atomic_value(cls.instantiate(self._node))
    v2 = abstract_utils.get_atomic_value(cls.instantiate(self._node))
    self.assertIsNot(v1, v2)
    # Create one instance per opcode.
    fake_opcode = object()
    self._vm.push_frame(frame_state.SimpleFrame(fake_opcode))
    v3 = abstract_utils.get_atomic_value(cls.instantiate(self._node))
    v4 = abstract_utils.get_atomic_value(cls.instantiate(self._node))
    self.assertIsNot(v1, v3)
    self.assertIsNot(v2, v3)
    self.assertIs(v3, v4)

  def test_set_module_on_module(self):
    # A module's 'module' attribute should always remain None, and no one
    # should attempt to set it to something besides the module's name or None.
    ast = pytd_utils.CreateModule("some_mod")
    mod = abstract.Module(self._vm, ast.name, {}, ast)
    mod.module = ast.name
    self.assertIsNone(mod.module)
    self.assertEqual(ast.name, mod.full_name)
    mod.module = None
    self.assertIsNone(mod.module)
    self.assertEqual(ast.name, mod.full_name)
    def set_module():
      mod.module = "other_mod"
    self.assertRaises(AssertionError, set_module)

  def test_call_type_parameter_instance(self):
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    instance.merge_instance_type_parameter(
        self._vm.root_cfg_node, abstract_utils.T,
        self._vm.convert.int_type.to_variable(self._vm.root_cfg_node))
    t = abstract.TypeParameter(abstract_utils.T, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    node, ret = t_instance.call(self._node, t_instance.to_binding(self._node),
                                function.Args(posargs=()))
    self.assertIs(node, self._node)
    retval, = ret.data
    self.assertEqual(retval.cls, self._vm.convert.int_type)

  def test_call_empty_type_parameter_instance(self):
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    t = abstract.TypeParameter(abstract_utils.T, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    node, ret = t_instance.call(self._node, t_instance.to_binding(self._node),
                                function.Args(posargs=()))
    self.assertIs(node, self._node)
    retval, = ret.data
    self.assertIs(retval, self._vm.convert.empty)

  def test_call_type_parameter_instance_with_wrong_args(self):
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    instance.merge_instance_type_parameter(
        self._vm.root_cfg_node, abstract_utils.T,
        self._vm.convert.int_type.to_variable(self._vm.root_cfg_node))
    t = abstract.TypeParameter(abstract_utils.T, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    posargs = (self._vm.new_unsolvable(self._node),) * 3
    node, ret = t_instance.call(self._node, t_instance.to_binding(self._node),
                                function.Args(posargs=posargs))
    self.assertIs(node, self._node)
    self.assertTrue(ret.bindings)
    error, = self._vm.errorlog
    self.assertEqual(error.name, "wrong-arg-count")

  def test_instantiate_tuple_class_for_sub(self):
    type_param = abstract.TypeParameter(abstract_utils.K, self._vm)
    cls = abstract.TupleClass(
        self._vm.convert.tuple_type,
        {0: type_param, abstract_utils.T: type_param}, self._vm)
    # Instantiate the tuple class.
    subst_value = cls.instantiate(
        self._vm.root_cfg_node, abstract_utils.DUMMY_CONTAINER)
    # Recover the class from the instance.
    subbed_cls = self._vm.annotations_util.sub_one_annotation(
        self._vm.root_cfg_node, type_param, [{abstract_utils.K: subst_value}])
    self.assertEqual(cls, subbed_cls)

  def test_singleton(self):
    self.assertIs(abstract.Unsolvable(self._vm), abstract.Unsolvable(self._vm))

  def test_singleton_subclass(self):
    self.assertIs(abstract.Empty(self._vm), abstract.Empty(self._vm))
    self.assertIsNot(abstract.Deleted(self._vm), abstract.Empty(self._vm))


if __name__ == "__main__":
  unittest.main()
