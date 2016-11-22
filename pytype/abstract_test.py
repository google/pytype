"""Tests for abstract.py."""

import unittest


from pytype import abstract
from pytype import config
from pytype import errors
from pytype import exceptions
from pytype import function
from pytype import vm
from pytype.pytd import cfg
from pytype.pytd import pytd

import unittest


def binding_name(binding):
  """Return a name based on the variable name and binding position."""
  var = binding.variable
  return "%s:%d" % (var.name, var.bindings.index(binding))


class FakeFrame(object):

  def __init__(self):
    self.current_opcode = None


class AbstractTestBase(unittest.TestCase):

  def setUp(self):
    self._vm = vm.VirtualMachine(errors.ErrorLog(), config.Options([""]))
    self._program = cfg.Program()
    self._node = self._program.NewCFGNode("test_node")

  def new_var(self, name, *values):
    """Create a Variable bound to the given values."""
    var = self._program.NewVariable(name)
    for value in values:
      var.AddBinding(value, source_set=(), where=self._node)
    return var

  def new_dict(self, **kwargs):
    """Create a Dict from keywords mapping names to Variable objects."""
    d = abstract.Dict(self._vm, self._node)
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
    i = abstract.Instance(
        self._vm.convert.object_type, self._vm, self._node)
    self.assertIs(True, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))

  def test_compatible_with_list(self):
    i = abstract.Instance(
        self._vm.convert.list_type, self._vm, self._node)
    i.init_type_parameters(abstract.T)
    # Empty list is not compatible with True.
    self.assertIs(False, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))
    # Once a type parameter is set, list is compatible with True and False.
    i.merge_type_parameter(self._node, abstract.T, self._vm.convert.object_type)
    self.assertIs(True, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))

  def test_compatible_with_set(self):
    i = abstract.Instance(
        self._vm.convert.set_type, self._vm, self._node)
    i.init_type_parameters(abstract.T)
    # Empty list is not compatible with True.
    self.assertIs(False, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))
    # Once a type parameter is set, list is compatible with True and False.
    i.merge_type_parameter(self._node, abstract.T, self._vm.convert.object_type)
    self.assertIs(True, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))

  def test_compatible_with_none(self):
    # This test is specifically for abstract.Instance, so we don't use
    # self._vm.convert.none, which is an AbstractOrConcreteValue.
    i = abstract.Instance(
        self._vm.convert.none_type, self._vm, self._node)
    self.assertIs(False, i.compatible_with(True))
    self.assertIs(True, i.compatible_with(False))


class DictTest(AbstractTestBase):

  def setUp(self):
    super(DictTest, self).setUp()
    self._d = abstract.Dict(self._vm, self._node)
    self._var = self._program.NewVariable("test_var")
    self._var.AddBinding(abstract.Unknown(self._vm))

  def test_compatible_with__when_empty(self):
    self.assertIs(False, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  @unittest.skip("setitem() does not update the parameters")
  def test_compatible_with__after_setitem(self):
    # Once a slot is added, dict is ambiguous.
    self._d.setitem(self._node, self._var, self._var)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  def test_compatible_with__after_set_str_item(self):
    # set_str_item() will make the dict ambiguous.
    self._d.set_str_item(self._node, "key", self._var)
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))

  @unittest.skip("update() does not update the parameters")
  def test_compatible_with__after_update(self):
    # Updating an empty dict also makes it ambiguous.
    self._d.update(self._node, abstract.Unknown(self._vm))
    self.assertIs(True, self._d.compatible_with(True))
    self.assertIs(True, self._d.compatible_with(False))


class IsInstanceTest(AbstractTestBase):

  def setUp(self):
    super(IsInstanceTest, self).setUp()
    self._is_instance = abstract.IsInstance(self._vm)
    # Easier access to some primitive instances.
    self._bool = self._vm.convert.primitive_class_instances[bool]
    self._int = self._vm.convert.primitive_class_instances[int]
    self._str = self._vm.convert.primitive_class_instances[str]
    # Values that represent primitive classes.
    self._obj_class = abstract.get_atomic_value(
        self._vm.convert.primitive_classes[object])
    self._int_class = abstract.get_atomic_value(
        self._vm.convert.primitive_classes[int])
    self._str_class = abstract.get_atomic_value(
        self._vm.convert.primitive_classes[str])

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
    node, result = self._is_instance.call(
        self._node, None, abstract.FunctionArgs((left, right), self.new_dict(),
                                                None, None))
    self.assertEquals(self._node, node)
    result_map = {}
    # Turning source sets into canonical string representations of the binding
    # names makes it much easier to debug failures.
    for b in result.bindings:
      terms = set()
      for o in b.origins:
        self.assertEquals(self._node, o.where)
        for sources in o.source_sets:
          terms.add(" ".join(sorted(binding_name(b) for b in sources)))
      result_map[b.data] = terms
    self.assertEquals(expected, result_map)

  def test_call_single_bindings(self):
    right = self.new_var("right", self._str_class)
    self.assert_call(
        {self._vm.convert.true: {"left:0 right:0"}},
        self.new_var("left", self._str),
        right)
    self.assert_call(
        {self._vm.convert.false: {"left:0 right:0"}},
        self.new_var("left", self._int),
        right)
    self.assert_call(
        {self._bool: {"left:0 right:0"}},
        self.new_var("left", abstract.Unknown(self._vm)),
        right)

  def test_call_multiple_bindings(self):
    self.assert_call(
        {
            self._vm.convert.true: {"left:0 right:0", "left:1 right:1"},
            self._vm.convert.false: {"left:0 right:1", "left:1 right:0"},
        },
        self.new_var("left", self._int, self._str),
        self.new_var("right", self._int_class, self._str_class)
    )

  def test_call_wrong_argcount(self):
    self._vm.push_frame(FakeFrame())
    node, result = self._is_instance.call(
        self._node, None, abstract.FunctionArgs((), self.new_dict(),
                                                None, None))
    self.assertEquals(self._node, node)
    self.assertIsInstance(abstract.get_atomic_value(result),
                          abstract.Unsolvable)
    self.assertRegexpMatches(
        str(self._vm.errorlog),
        r"isinstance .* 0 args .* expected 2.*\[wrong-arg-count\]")

  def test_call_wrong_keywords(self):
    self._vm.push_frame(FakeFrame())
    x = self.new_var("x", abstract.Unknown(self._vm))
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

    obj_class = self._vm.convert.primitive_classes[object].bindings[0].data

    # Unknown and Unsolvable are ambiguous.
    check(None, abstract.Unknown(self._vm), obj_class)
    check(None, abstract.Unsolvable(self._vm), obj_class)

    # If the object's class has multiple bindings, result is ambiguous.
    obj = abstract.SimpleAbstractValue("foo", self._vm)
    check(None, obj, obj_class)
    obj.set_class(self._node, self.new_var(
        "foo_class", self._str_class, self._int_class))
    check(None, obj, self._str_class)

    # If the class_spec is not a class, result is ambiguous.
    check(None, self._str, self._str)

    # Result is True/False depending on if the class is in the object's mro.
    check(True, self._str, obj_class)
    check(True, self._str, self._str_class)
    check(False, self._str, self._int_class)

  def test_flatten(self):
    def maybe_var(v):
      return v if isinstance(v, cfg.Variable) else self.new_var("v", v)

    def new_tuple(*args):
      pyval = tuple(maybe_var(a) for a in args)
      return abstract.AbstractOrConcreteValue(
          pyval, self._vm.convert.tuple_type, self._vm, self._node)

    def check(expected_ambiguous, expected_classes, value):
      classes = []
      ambiguous = self._is_instance._flatten(value, classes)
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
                    self.new_var("v", self._int_class, self._obj_class)))


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


# TODO(rechen): Test InterpreterFunction.
class FunctionTest(AbstractTestBase):

  def _make_pytd_function(self, params):
    pytd_params = []
    for i, p in enumerate(params):
      p_type = pytd.ClassType(p.name)
      p_type.cls = p
      pytd_params.append(
          pytd.Parameter("_" + str(i), p_type, False, False, None))
    pytd_sig = pytd.Signature(
        tuple(pytd_params), None, None, pytd.AnythingType(), (), ())
    sig = abstract.PyTDSignature("f", pytd_sig, self._vm)
    return abstract.PyTDFunction(
        "f", (sig,), pytd.METHOD, self._vm, self._vm.root_cfg_node)

  def _call_pytd_function(self, f, args):
    b = f.to_variable(self._vm.root_cfg_node).bindings[0]
    return f.call(
        self._vm.root_cfg_node, b, abstract.FunctionArgs(posargs=args))

  def test_call_with_empty_arg(self):
    self.assertRaises(exceptions.ByteCodeTypeError, self._call_pytd_function,
                      self._make_pytd_function(params=()),
                      (self._vm.program.NewVariable("empty"),))

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
    arg = self._vm.program.NewVariable("arg")
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
    self.assertFalse(sig.kwonly_params)
    self.assertIs(sig.kwargs_name, None)
    self.assertSetEqual(set(sig.annotations), {"self", "args"})
    self.assertFalse(sig.late_annotations)
    self.assertFalse(sig.has_return_annotation)
    self.assertTrue(sig.has_param_annotations)

  def test_signature_annotations(self):
    # def f(self: Any, *args: Any)
    self_param = pytd.Parameter("self", pytd.AnythingType(), False, False, None)
    args_param = pytd.Parameter("args", pytd.AnythingType(), False, True, None)
    sig = function.Signature.from_pytd(
        self._vm, "f", pytd.Signature(
            (self_param,), args_param, None, pytd.AnythingType(), (), ()))
    self.assertIs(sig.annotations["self"], self._vm.convert.unsolvable)
    args_type = sig.annotations["args"]  # Should be Tuple[Any]
    self.assertIsInstance(args_type, abstract.ParameterizedClass)
    self.assertIs(args_type.base_cls,
                  abstract.get_atomic_value(self._vm.convert.tuple_type))
    self.assertDictEqual(args_type.type_parameters,
                         {abstract.T: self._vm.convert.unsolvable})
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
            "v": function.LateAnnotation("X", "v", None),
            "return": function.LateAnnotation("Y", "return", None)
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


if __name__ == "__main__":
  unittest.main()
