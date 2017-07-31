"""Tests for abstract.py."""


from pytype import abstract
from pytype import annotations_util
from pytype import config
from pytype import errors
from pytype import exceptions
from pytype import function
from pytype import load_pytd
from pytype import special_builtins
from pytype import state as frame_state
from pytype import vm
from pytype.pytd import cfg
from pytype.pytd import pytd

import unittest


class AbstractTestBase(unittest.TestCase):

  def setUp(self):
    options = config.Options.create()
    self._vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, options))
    self._program = cfg.Program()
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


class InstanceTest(AbstractTestBase):

  # TODO(dbaum): Is it worth adding a test for frozenset()?  There isn't
  # an easy way to create one directly from the vm, it is already covered
  # in test_splits.py, and there aren't any new code paths.  Perhaps it isn't
  # worth the effort.

  def test_compatible_with_non_container(self):
    # Compatible with either True or False.
    i = abstract.Instance(self._vm.convert.object_type, self._vm)
    self.assertIs(True, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))

  def test_compatible_with_list(self):
    i = abstract.List([], self._vm)
    # Empty list is not compatible with True.
    self.assertIs(False, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))
    # Once a type parameter is set, list is compatible with True and False.
    i.merge_type_parameter(
        self._node, abstract.T,
        self._vm.convert.object_type.to_variable(self._vm.root_cfg_node))
    self.assertIs(True, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))

  def test_compatible_with_set(self):
    i = abstract.Instance(self._vm.convert.set_type, self._vm)
    i.init_type_parameters(abstract.T)
    # Empty list is not compatible with True.
    self.assertIs(False, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))
    # Once a type parameter is set, list is compatible with True and False.
    i.merge_type_parameter(
        self._node, abstract.T,
        self._vm.convert.object_type.to_variable(self._vm.root_cfg_node))
    self.assertIs(True, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))

  def test_compatible_with_none(self):
    # This test is specifically for abstract.Instance, so we don't use
    # self._vm.convert.none, which is an AbstractOrConcreteValue.
    i = abstract.Instance(self._vm.convert.none_type, self._vm)
    self.assertIs(False, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))


class TupleTest(AbstractTestBase):

  def setUp(self):
    super(TupleTest, self).setUp()
    self._var = self._program.NewVariable()
    self._var.AddBinding(abstract.Unknown(self._vm), [], self._node)

  def test_compatible_with__not_empty(self):
    t = abstract.Tuple((self._var,), self._vm)
    self.assertIs(True, t.compatible_with(True))
    self.assertIs(False, t.compatible_with(False))

  def test_compatible_with__empty(self):
    t = abstract.Tuple((), self._vm)
    self.assertIs(False, t.compatible_with(True))
    self.assertIs(True, t.compatible_with(False))

  def test_getitem__concrete_index(self):
    t = abstract.Tuple((self._var,), self._vm)
    index = self._vm.convert.constant_to_var(0)
    node, var = t.cls.data[0].getitem_slot(self._node, index)
    self.assertIs(node, self._node)
    self.assertIs(abstract.get_atomic_value(var),
                  abstract.get_atomic_value(self._var))

  def test_getitem__abstract_index(self):
    t = abstract.Tuple((self._var,), self._vm)
    index = self._vm.convert.build_int(self._node)
    node, var = t.cls.data[0].getitem_slot(self._node, index)
    self.assertIs(node, self._node)
    self.assertIs(abstract.get_atomic_value(var),
                  abstract.get_atomic_value(self._var))


class DictTest(AbstractTestBase):

  def setUp(self):
    super(DictTest, self).setUp()
    self._d = abstract.Dict(self._vm)
    self._var = self._program.NewVariable()
    self._var.AddBinding(abstract.Unknown(self._vm), [], self._node)

  def test_compatible_with__when_empty(self):
    self.assertIs(False, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_setitem(self):
    # Once a slot is added, dict is ambiguous.
    self._d.setitem_slot(self._node, self._var, self._var)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_set_str_item(self):
    self._d.set_str_item(self._node, "key", self._var)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(False, self._d.compatible_with(False))

  def test_compatible_with__after_unknown_update(self):
    # Updating an empty dict with an unknown value makes the former ambiguous.
    self._d.update(self._node, abstract.Unknown(self._vm))
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_empty_update(self):
    empty_dict = abstract.Dict(self._vm)
    self._d.update(self._node, empty_dict)
    self.assertIs(False, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_unambiguous_update(self):
    unambiguous_dict = abstract.Dict(self._vm)
    unambiguous_dict.set_str_item(
        self._node, "a", self._vm.convert.create_new_unsolvable(self._node))
    self._d.update(self._node, unambiguous_dict)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(False, self._d.compatible_with(False))

  def test_compatible_with__after_ambiguous_update(self):
    ambiguous_dict = abstract.Dict(self._vm)
    ambiguous_dict.merge_type_parameter(
        self._node, abstract.K,
        self._vm.convert.create_new_unsolvable(self._node))
    ambiguous_dict.could_contain_anything = True
    self._d.update(self._node, ambiguous_dict)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_concrete_update(self):
    self._d.update(self._node, {})
    self.assertIs(False, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))
    self._d.update(
        self._node, {"a": self._vm.convert.create_new_unsolvable(self._node)})
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(False, self._d.compatible_with(False))


class IsInstanceTest(AbstractTestBase):

  def setUp(self):
    super(IsInstanceTest, self).setUp()
    self._is_instance = special_builtins.IsInstance(self._vm)
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
        self._node, None, abstract.FunctionArgs((left, right), self.new_dict(),
                                                None, None))
    self.assertIn(node, self._node.outgoing)
    result_map = {}
    # Turning source sets into canonical string representations of the binding
    # names makes it much easier to debug failures.
    for b in result.bindings:
      terms = set()
      for o in b.origins:
        self.assertEquals(node, o.where)
        for sources in o.source_sets:
          terms.add(" ".join(sorted(
              "%s:%d" % (name_map[b.variable], b.variable.bindings.index(b))
              for b in sources)))
      result_map[b.data] = terms
    self.assertEquals(expected, result_map)

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
        self._node, None, abstract.FunctionArgs((), self.new_dict(),
                                                None, None))
    self.assertEquals(self._node, node)
    self.assertIsInstance(abstract.get_atomic_value(result),
                          abstract.Unsolvable)
    self.assertRegexpMatches(str(self._vm.errorlog), "missing-parameter")

  def test_call_wrong_keywords(self):
    self._vm.push_frame(frame_state.SimpleFrame())
    x = self.new_var(abstract.Unknown(self._vm))
    node, result = self._is_instance.call(
        self._node, None, abstract.FunctionArgs((x, x), self.new_dict(foo=x),
                                                None, None))
    self.assertEquals(self._node, node)
    self.assertIsInstance(abstract.get_atomic_value(result),
                          abstract.Unsolvable)
    self.assertRegexpMatches(
        str(self._vm.errorlog),
        r"foo.*isinstance.*\[wrong-keyword-args\]")

  def test_is_instance(self):
    def check(expected, left, right):
      self.assertEquals(expected, self._is_instance._is_instance(left, right))

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
      self.assertEquals(expected_ambiguous, ambiguous)
      self.assertEquals(expected_classes, classes)

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

  def testMetaclass(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    meta = abstract.InterpreterClass("M", [], {}, None, self._vm)
    meta.official_name = "M"
    cls.cls = meta.to_variable(self._vm.root_cfg_node)
    pytd_cls = cls.to_pytd_def(self._vm.root_cfg_node, "X")
    self.assertEquals(pytd_cls.metaclass, pytd.NamedType("M"))

  def testInheritedMetaclass(self):
    parent = abstract.InterpreterClass("X", [], {}, None, self._vm)
    meta = abstract.InterpreterClass("M", [], {}, None, self._vm)
    meta.official_name = "M"
    parent.cls = meta.to_variable(self._vm.root_cfg_node)
    child = abstract.InterpreterClass(
        "Y", [parent.to_variable(self._vm.root_cfg_node)], {}, None, self._vm)
    self.assertIs(child.cls, parent.cls)
    pytd_cls = child.to_pytd_def(self._vm.root_cfg_node, "Y")
    self.assertIs(pytd_cls.metaclass, None)

  def testMetaclassUnion(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    meta1 = abstract.InterpreterClass("M1", [], {}, None, self._vm)
    meta2 = abstract.InterpreterClass("M2", [], {}, None, self._vm)
    meta1.official_name = "M1"
    meta2.official_name = "M2"
    cls.cls = abstract.Union(
        [meta1, meta2], self._vm).to_variable(self._vm.root_cfg_node)
    pytd_cls = cls.to_pytd_def(self._vm.root_cfg_node, "X")
    self.assertEquals(pytd_cls.metaclass, pytd.UnionType(
        (pytd.NamedType("M1"), pytd.NamedType("M2"))))

  def testToTypeWithView1(self):
    # to_type(<instance of List[int or unsolvable]>, view={T: int})
    instance = abstract.List([], self._vm)
    instance.merge_type_parameter(
        self._vm.root_cfg_node, abstract.T, self._vm.program.NewVariable(
            [self._vm.convert.unsolvable], [], self._vm.root_cfg_node))
    param_binding = instance.type_parameters[abstract.T].AddBinding(
        self._vm.convert.primitive_class_instances[int], [],
        self._vm.root_cfg_node)
    view = {instance.cls: instance.cls.bindings[0],
            instance.type_parameters[abstract.T]: param_binding,
            param_binding.data.cls: param_binding.data.cls.bindings[0]}
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view=view)
    self.assertEquals("__builtin__.list", pytd_type.base_type.name)
    self.assertSetEqual({"__builtin__.int"},
                        {t.name for t in pytd_type.parameters})

  def testToTypeWithView2(self):
    # to_type(<instance of <str or unsolvable>>, view={__class__: str})
    instance = abstract.Instance(self._vm.convert.unsolvable, self._vm)
    cls_binding = instance.cls.AddBinding(
        self._vm.convert.str_type, [], self._vm.root_cfg_node)
    view = {instance.cls: cls_binding}
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view=view)
    self.assertEquals("__builtin__.str", pytd_type.name)

  def testToTypeWithView3(self):
    # to_type(<tuple (int or str,)>, view={0: str})
    param1 = self._vm.convert.primitive_class_instances[int]
    param2 = self._vm.convert.primitive_class_instances[str]
    param_var = param1.to_variable(self._vm.root_cfg_node)
    str_binding = param_var.AddBinding(param2, [], self._vm.root_cfg_node)
    instance = abstract.Tuple((param_var,), self._vm)
    view = {param_var: str_binding, instance.cls: instance.cls.bindings[0],
            str_binding.data.cls: str_binding.data.cls.bindings[0]}
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view=view)
    self.assertEquals(pytd_type.parameters[0],
                      pytd.NamedType("__builtin__.str"))

  def testToTypeWithViewAndEmptyParam(self):
    instance = abstract.List([], self._vm)
    view = {instance.cls: instance.cls.bindings[0]}
    pytd_type = instance.to_type(self._vm.root_cfg_node, seen=None, view=view)
    self.assertEquals("__builtin__.list", pytd_type.base_type.name)
    self.assertSequenceEqual((pytd.NothingType(),), pytd_type.parameters)

  def testTypingContainer(self):
    cls = self._vm.convert.list_type
    container = abstract.AnnotationContainer("List", self._vm, cls)
    expected = pytd.GenericType(pytd.NamedType("__builtin__.list"),
                                (pytd.AnythingType(),))
    actual = container.get_instance_type(self._vm.root_cfg_node)
    self.assertEquals(expected, actual)


# TODO(rechen): Test InterpreterFunction.
class FunctionTest(AbstractTestBase):

  def _make_pytd_function(self, params):
    pytd_params = []
    for i, p in enumerate(params):
      p_type = pytd.ClassType(p.name)
      p_type.cls = p
      pytd_params.append(
          pytd.Parameter(function.argname(i), p_type, False, False, None))
    pytd_sig = pytd.Signature(
        tuple(pytd_params), None, None, pytd.AnythingType(), (), ())
    sig = abstract.PyTDSignature("f", pytd_sig, self._vm)
    return abstract.PyTDFunction("f", (sig,), pytd.METHOD, self._vm)

  def _call_pytd_function(self, f, args):
    b = f.to_variable(self._vm.root_cfg_node).bindings[0]
    return f.call(
        self._vm.root_cfg_node, b, abstract.FunctionArgs(posargs=args))

  def test_call_with_empty_arg(self):
    self.assertRaises(exceptions.ByteCodeTypeError, self._call_pytd_function,
                      self._make_pytd_function(params=()),
                      (self._vm.program.NewVariable(),))

  def test_call_with_bad_arg(self):
    f = self._make_pytd_function(
        (self._vm.lookup_builtin("__builtin__.str"),))
    arg = self._vm.convert.primitive_class_instances[int].to_variable(
        self._vm.root_cfg_node)
    self.assertRaises(
        abstract.WrongArgTypes, self._call_pytd_function, f, (arg,))

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
    self.assertEquals(sig.name, "f")
    self.assertSequenceEqual(sig.param_names, ("self",))
    self.assertEquals(sig.varargs_name, "args")
    self.assertEmpty(sig.kwonly_params)
    self.assertIs(sig.kwargs_name, None)
    self.assertSetEqual(set(sig.annotations), {"self", "args", "return"})
    self.assertEmpty(sig.late_annotations)
    self.assertTrue(sig.has_return_annotation)
    self.assertTrue(sig.has_param_annotations)

  def test_signature_from_callable(self):
    # Callable[[int, str], Any]
    params = {0: self._vm.convert.int_type, 1: self._vm.convert.str_type}
    params[abstract.ARGS] = abstract.Union((params[0], params[1]), self._vm)
    params[abstract.RET] = self._vm.convert.unsolvable
    callable_val = abstract.Callable(
        self._vm.convert.function_type, params, self._vm)
    sig = function.Signature.from_callable(callable_val)
    self.assertEquals(sig.name, callable_val.name)
    self.assertSequenceEqual(sig.param_names, ("_0", "_1"))
    self.assertIs(sig.varargs_name, None)
    self.assertEmpty(sig.kwonly_params)
    self.assertIs(sig.kwargs_name, None)
    self.assertItemsEqual(sig.annotations, sig.param_names)
    self.assertEmpty(sig.late_annotations)
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
    self.assertIs(sig.annotations["self"], self._vm.convert.unsolvable)
    args_type = sig.annotations["args"]
    self.assertIsInstance(args_type, abstract.ParameterizedClass)
    self.assertIs(args_type.base_cls, self._vm.convert.tuple_type)
    self.assertListEqual(args_type.type_parameters.items(),
                         [(abstract.T, self._vm.convert.unsolvable)])
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
        late_annotations={
            "v": annotations_util.LateAnnotation("X", "v", None),
            "return": annotations_util.LateAnnotation("Y", "return", None)
        }
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
        late_annotations={},
    )
    self.assertEquals(sig.mandatory_param_count(), 1)
    self.assertEquals(sig.maximum_param_count(), 1)

  def test_signature_posarg_and_kwarg_param_count(self):
    # def f(x, y=None): ...
    sig = function.Signature(
        name="f",
        param_names=("x", "y",),
        varargs_name=None,
        kwonly_params=(),
        kwargs_name=None,
        defaults={"y": self._vm.convert.unsolvable.to_variable(self._node)},
        annotations={},
        late_annotations={},
    )
    self.assertEquals(sig.mandatory_param_count(), 1)
    self.assertEquals(sig.maximum_param_count(), 2)

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
        late_annotations={},
    )
    self.assertEquals(sig.mandatory_param_count(), 0)
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
        late_annotations={},
    )
    self.assertEquals(sig.mandatory_param_count(), 0)
    self.assertIsNone(sig.maximum_param_count())

  def test_signature_kwonly_param_count(self):
    # def f(*, y=None): ...
    sig = function.Signature(
        name="f",
        param_names=(),
        varargs_name=None,
        kwonly_params=("y",),
        kwargs_name=None,
        defaults={"y": self._vm.convert.unsolvable.to_variable(self._node)},
        annotations={},
        late_annotations={},
    )
    self.assertEquals(sig.mandatory_param_count(), 0)
    self.assertEquals(sig.maximum_param_count(), 1)

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
        late_annotations={},
    )
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
        late_annotations={},
    )
    # f(1, 2, y=3, z=4)
    int_inst = self._vm.convert.primitive_class_instances[int]
    int_binding = int_inst.to_variable(self._node).bindings[0]
    arg_dict = {
        "x": int_binding, "_1": int_binding, "y": int_binding, "z": int_binding}
    sig = sig.insert_varargs_and_kwargs(arg_dict)
    self.assertEquals(sig.name, "f")
    self.assertSequenceEqual(sig.param_names, ("x", "_1", "z"))
    self.assertEquals(sig.varargs_name, "args")
    self.assertSetEqual(sig.kwonly_params, {"y"})
    self.assertEquals(sig.kwargs_name, "kwargs")
    self.assertFalse(sig.annotations)
    self.assertFalse(sig.late_annotations)


class AbstractMethodsTest(AbstractTestBase):

  def testAbstractMethod(self):
    func = abstract.Function("f", self._vm).to_variable(self._vm.root_cfg_node)
    func.data[0].is_abstract = True
    cls = abstract.InterpreterClass("X", [], {"f": func}, None, self._vm)
    self.assertListEqual(cls.abstract_methods, ["f"])

  def testInheritedAbstractMethod(self):
    sized_pytd = self._vm.loader.typing.Lookup("typing.Sized")
    sized = self._vm.convert.constant_to_value(
        sized_pytd, {}, self._vm.root_cfg_node)
    cls = abstract.InterpreterClass(
        "X", [sized.to_variable(self._vm.root_cfg_node)], {}, None, self._vm)
    self.assertListEqual(cls.abstract_methods, ["__len__"])

  def testOverriddenAbstractMethod(self):
    sized_pytd = self._vm.loader.typing.Lookup("typing.Sized")
    sized = self._vm.convert.constant_to_value(
        sized_pytd, {}, self._vm.root_cfg_node)
    bases = [sized.to_variable(self._vm.root_cfg_node)]
    members = {"__len__":
               self._vm.convert.create_new_unsolvable(self._vm.root_cfg_node)}
    cls = abstract.InterpreterClass("X", bases, members, None, self._vm)
    self.assertFalse(cls.abstract_methods)

  def testOverriddenAbstractMethodStillAbstract(self):
    sized_pytd = self._vm.loader.typing.Lookup("typing.Sized")
    sized = self._vm.convert.constant_to_value(
        sized_pytd, {}, self._vm.root_cfg_node)
    bases = [sized.to_variable(self._vm.root_cfg_node)]
    func = abstract.Function("__len__", self._vm)
    func.is_abstract = True
    members = {"__len__": func.to_variable(self._vm.root_cfg_node)}
    cls = abstract.InterpreterClass("X", bases, members, None, self._vm)
    self.assertListEqual(cls.abstract_methods, ["__len__"])


class AbstractTest(AbstractTestBase):

  def testInterpreterClassOfficialName(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    cls.update_official_name("Z")
    self.assertEquals(cls.official_name, "Z")
    cls.update_official_name("A")  # takes effect because A < Z
    self.assertEquals(cls.official_name, "A")
    cls.update_official_name("Z")  # no effect
    self.assertEquals(cls.official_name, "A")
    cls.update_official_name("X")  # takes effect because X == cls.name
    self.assertEquals(cls.official_name, "X")
    cls.update_official_name("A")  # no effect
    self.assertEquals(cls.official_name, "X")

  def testTypeParameterOfficialName(self):
    param = abstract.TypeParameter("T", self._vm)
    self._vm.frame = frame_state.SimpleFrame()  # for error logging
    param.update_official_name("T")
    self.assertFalse(self._vm.errorlog.has_error())
    param.update_official_name("Q")
    self.assertTrue(self._vm.errorlog.has_error())

  def testTypeParameterEquality(self):
    param1 = abstract.TypeParameter("S", self._vm)
    param2 = abstract.TypeParameter("T", self._vm)
    cls = abstract.InterpreterClass("S", [], {}, None, self._vm)
    self.assertEquals(param1, param1)
    self.assertNotEquals(param1, param2)
    self.assertNotEquals(param1, cls)

  def testUnionEquality(self):
    union1 = abstract.Union((self._vm.convert.unsolvable,), self._vm)
    union2 = abstract.Union((self._vm.convert.none,), self._vm)
    cls = abstract.InterpreterClass("Union", [], {}, None, self._vm)
    self.assertEquals(union1, union1)
    self.assertNotEquals(union1, union2)
    self.assertNotEquals(union1, cls)

  def testInstantiateTypeParameterType(self):
    params = {abstract.T: abstract.TypeParameter(abstract.T, self._vm)}
    cls = abstract.ParameterizedClass(
        self._vm.convert.type_type, params, self._vm)
    self.assertListEqual(cls.instantiate(self._node).data,
                         [self._vm.convert.unsolvable])

  def testSuperType(self):
    supercls = special_builtins.Super(self._vm)
    self.assertListEqual(supercls.get_class().data,
                         [self._vm.convert.type_type])

  def testMixinSuper(self):
    """Test the imitation 'super' method on MixinMeta."""
    # pylint: disable=g-wrong-blank-lines
    class A(object):
      def f(self, x):
        return x
    class MyMixin(object):
      __metaclass__ = abstract.MixinMeta
      overloads = ("f",)
      def f(self, x):
        if x == 0:
          return "hello"
        return MyMixin.super(self.f)(x)
    class B(A, MyMixin):
      pass
    # pylint: enable=g-wrong-blank-lines
    b = B()
    v_mixin = b.f(0)
    v_a = b.f(1)
    self.assertEquals(v_mixin, "hello")
    self.assertEquals(v_a, 1)

  def testInstantiateInterpreterClass(self):
    cls = abstract.InterpreterClass("X", [], {}, None, self._vm)
    # When there is no current frame, create a new instance every time.
    v1 = abstract.get_atomic_value(cls.instantiate(self._node))
    v2 = abstract.get_atomic_value(cls.instantiate(self._node))
    self.assertIsNot(v1, v2)
    # Create one instance per opcode.
    fake_opcode = object()
    self._vm.push_frame(frame_state.SimpleFrame(fake_opcode))
    v3 = abstract.get_atomic_value(cls.instantiate(self._node))
    v4 = abstract.get_atomic_value(cls.instantiate(self._node))
    self.assertIsNot(v1, v3)
    self.assertIsNot(v2, v3)
    self.assertIs(v3, v4)

  def testSetModuleOnModule(self):
    # A module's 'module' attribute should always remain None, and no one
    # should attempt to set it to something besides the module's name or None.
    ast = pytd.TypeDeclUnit("some_mod", (), (), (), (), ())
    mod = abstract.Module(self._vm, ast.name, {}, ast)
    mod.module = ast.name
    self.assertIsNone(mod.module)
    self.assertEquals(ast.name, mod.full_name)
    mod.module = None
    self.assertIsNone(mod.module)
    self.assertEquals(ast.name, mod.full_name)
    def set_module():
      mod.module = "other_mod"
    self.assertRaises(AssertionError, set_module)

  def testCallTypeParameterInstance(self):
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    instance.initialize_type_parameter(
        self._node, abstract.T,
        self._vm.convert.int_type.to_variable(self._vm.root_cfg_node))
    t = abstract.TypeParameter(abstract.T, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    node, ret = t_instance.call(
        self._node, t_instance.to_variable(self._node).bindings[0],
        abstract.FunctionArgs(posargs=()))
    self.assertIs(node, self._node)
    retval, = ret.data
    self.assertListEqual(retval.cls.data, [self._vm.convert.int_type])

  def testCallEmptyTypeParameterInstance(self):
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    instance.initialize_type_parameter(
        self._node, abstract.T, self._vm.program.NewVariable())
    t = abstract.TypeParameter(abstract.T, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    node, ret = t_instance.call(
        self._node, t_instance.to_variable(self._node).bindings[0],
        abstract.FunctionArgs(posargs=()))
    self.assertIs(node, self._node)
    retval, = ret.data
    self.assertIs(retval, self._vm.convert.empty)

  def testCallTypeParameterInstanceWithWrongArgs(self):
    instance = abstract.Instance(self._vm.convert.list_type, self._vm)
    instance.initialize_type_parameter(
        self._node, abstract.T,
        self._vm.convert.int_type.to_variable(self._vm.root_cfg_node))
    t = abstract.TypeParameter(abstract.T, self._vm)
    t_instance = abstract.TypeParameterInstance(t, instance, self._vm)
    posargs = (self._vm.convert.create_new_unsolvable(self._node),) * 3
    node, ret = t_instance.call(
        self._node, t_instance.to_variable(self._node).bindings[0],
        abstract.FunctionArgs(posargs=posargs))
    self.assertIs(node, self._node)
    self.assertTrue(ret.bindings)
    error, = self._vm.errorlog
    self.assertEquals(error.name, "wrong-arg-count")


if __name__ == "__main__":
  unittest.main()
