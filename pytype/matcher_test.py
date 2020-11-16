"""Tests for matcher.py."""

import textwrap

from pytype import abstract
from pytype import abstract_utils
from pytype import config
from pytype import errors
from pytype import file_utils
from pytype import load_pytd
from pytype import vm
from pytype.tests import test_base

import six

import unittest


class MatcherTest(test_base.UnitTest):
  """Test matcher.AbstractMatcher."""

  def setUp(self):
    super().setUp()
    options = config.Options.create(python_version=self.python_version)
    self.vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))
    self.type_type = self.vm.convert.type_type

  def _make_class(self, name):
    return abstract.InterpreterClass(name, [], {}, None, self.vm)

  def _parse_and_lookup(self, src, objname, filename=None):
    if filename is None:
      filename = str(hash(src))
    with file_utils.Tempdir() as d:
      d.create_file(filename + ".pyi", src)
      self.vm.loader.pythonpath = [d.path]   # monkeypatch
      ast = self.vm.loader.import_name(filename)
      return ast.Lookup(filename + "." + objname)

  def _convert(self, x, name, as_instance=False):
    pyval = self._parse_and_lookup(x, name)
    if as_instance:
      pyval = abstract_utils.AsInstance(pyval)
    return self.vm.convert.constant_to_value(pyval, {}, self.vm.root_cfg_node)

  def _convert_type(self, t, as_instance=False):
    """Convenience function for turning a string into an abstract value.

    Note that this function cannot be called more than once per test with
    the same arguments, since we hash the arguments to get a filename for
    the temporary pyi.

    Args:
      t: The string representation of a type.
      as_instance: Whether to convert as an instance.

    Returns:
      An AtomicAbstractValue.
    """
    src = textwrap.dedent(f"""
      from typing import Any, Callable, Iterator, Tuple, Type, Union
      from protocols import Sequence, SupportsLower
      x = ...  # type: {t}
    """)
    filename = str(hash((t, as_instance)))
    x = self._parse_and_lookup(src, "x", filename).type
    if as_instance:
      x = abstract_utils.AsInstance(x)
    return self.vm.convert.constant_to_value(x, {}, self.vm.root_cfg_node)

  def _match_var(self, left, right):
    var = self.vm.program.NewVariable()
    var.AddBinding(left, [], self.vm.root_cfg_node)
    for view in abstract_utils.get_views([var], self.vm.root_cfg_node):
      yield self.vm.matcher.match_var_against_type(
          var, right, {}, self.vm.root_cfg_node, view)

  def assertMatch(self, left, right):
    for match in self._match_var(left, right):
      self.assertEqual(match, {})

  def assertNoMatch(self, left, right):
    for match in self._match_var(left, right):
      self.assertIsNone(match)

  def test_basic(self):
    self.assertMatch(abstract.Empty(self.vm), abstract.Empty(self.vm))

  def test_type(self):
    left = self._make_class("dummy")
    type_parameters = {
        abstract_utils.T: abstract.TypeParameter(abstract_utils.T, self.vm)}
    other_type = abstract.ParameterizedClass(
        self.type_type, type_parameters, self.vm)
    for result in self._match_var(left, other_type):
      instance_binding, = result[abstract_utils.T].bindings
      self.assertEqual(instance_binding.data.cls, left)

  def test_union(self):
    left_option1 = self._make_class("o1")
    left_option2 = self._make_class("o2")
    left = abstract.Union([left_option1, left_option2], self.vm)
    self.assertMatch(left, self.type_type)

  def test_metaclass(self):
    left = self._make_class("left")
    meta1 = self._make_class("m1")
    meta2 = self._make_class("m2")
    left.set_class(self.vm.root_cfg_node,
                   self.vm.program.NewVariable(
                       [meta1, meta2], [], self.vm.root_cfg_node))
    self.assertMatch(left, meta1)
    self.assertMatch(left, meta2)

  def test_empty_against_class(self):
    var = self.vm.program.NewVariable()
    right = self._make_class("bar")
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEqual(result, {})

  def test_empty_var_against_empty(self):
    var = self.vm.program.NewVariable()
    right = abstract.Empty(self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEqual(result, {})

  def test_empty_against_type_parameter(self):
    var = self.vm.program.NewVariable()
    right = abstract.TypeParameter("T", self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    six.assertCountEqual(self, result.keys(), ["T"])
    self.assertFalse(result["T"].bindings)

  def test_empty_against_unsolvable(self):
    var = self.vm.program.NewVariable()
    right = abstract.Empty(self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEqual(result, {})

  def test_class_against_type_union(self):
    left = self._make_class("foo")
    union = abstract.Union((left,), self.vm)
    right = abstract.ParameterizedClass(
        self.type_type, {abstract_utils.T: union}, self.vm)
    self.assertMatch(left, right)

  def test_none_against_bool(self):
    # See pep484.COMPAT_ITEMS.
    left = self._convert_type("None", as_instance=True)
    right = self._convert_type("bool")
    self.assertMatch(left, right)

  def test_homogeneous_tuple(self):
    left = self._convert_type("Tuple[int, ...]", as_instance=True)
    right1 = self._convert_type("Tuple[int, ...]")
    right2 = self._convert_type("Tuple[str, ...]")
    self.assertMatch(left, right1)
    self.assertNoMatch(left, right2)

  def test_heterogeneous_tuple(self):
    left1 = self._convert_type("Tuple[Union[int, str]]", as_instance=True)
    left2 = self._convert_type("Tuple[int, str]", as_instance=True)
    left3 = self._convert_type("Tuple[str, int]", as_instance=True)
    right = self._convert_type("Tuple[int, str]")
    self.assertNoMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

  def test_heterogeneous_tuple_against_homogeneous_tuple(self):
    left = self._convert_type("Tuple[bool, int]", as_instance=True)
    right1 = self._convert_type("Tuple[bool, ...]")
    right2 = self._convert_type("Tuple[int, ...]")
    right3 = self._convert_type("tuple")
    self.assertNoMatch(left, right1)
    self.assertMatch(left, right2)
    self.assertMatch(left, right3)

  def test_homogeneous_tuple_against_heterogeneous_tuple(self):
    left1 = self._convert_type("Tuple[bool, ...]", as_instance=True)
    left2 = self._convert_type("Tuple[int, ...]", as_instance=True)
    left3 = self._convert_type("tuple", as_instance=True)
    right = self._convert_type("Tuple[bool, int]")
    self.assertMatch(left1, right)
    self.assertNoMatch(left2, right)
    self.assertMatch(left3, right)

  def test_tuple_type(self):
    # homogeneous against homogeneous
    left = self._convert_type("Type[Tuple[float, ...]]", as_instance=True)
    right1 = self._convert_type("Type[Tuple[float, ...]]")
    right2 = self._convert_type("Type[Tuple[str, ...]]")
    self.assertMatch(left, right1)
    self.assertNoMatch(left, right2)

    # heterogeneous against heterogeneous
    left1 = self._convert_type("Type[Tuple[Union[int, str]]]", as_instance=True)
    left2 = self._convert_type("Type[Tuple[int, str]]", as_instance=True)
    left3 = self._convert_type("Type[Tuple[str, int]]", as_instance=True)
    right = self._convert_type("Type[Tuple[int, str]]")
    self.assertNoMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

    # heterogeneous against homogeneous
    left = self._convert_type("Type[Tuple[bool, int]]", as_instance=True)
    right1 = self._convert_type("Type[Tuple[bool, ...]]")
    right2 = self._convert_type("Type[Tuple[int, ...]]")
    right3 = self._convert_type("Type[tuple]")
    self.assertNoMatch(left, right1)
    self.assertMatch(left, right2)
    self.assertMatch(left, right3)

    # homogeneous against heterogeneous
    left1 = self._convert_type("Type[Tuple[bool, ...]]", as_instance=True)
    left2 = self._convert_type("Type[Tuple[int, ...]]", as_instance=True)
    left3 = self._convert_type("Type[tuple]", as_instance=True)
    right = self._convert_type("Type[Tuple[bool, int]]")
    self.assertMatch(left1, right)
    self.assertNoMatch(left2, right)
    self.assertMatch(left3, right)

  def test_tuple_subclass(self):
    left = self._convert("""
      from typing import Tuple
      class A(Tuple[bool, int]): ...""", "A", as_instance=True)
    right1 = self._convert_type("Tuple[bool, int]")
    right2 = self._convert_type("Tuple[int, bool]")
    right3 = self._convert_type("Tuple[int, int]")
    right4 = self._convert_type("Tuple[int]")
    right5 = self._convert_type("tuple")
    right6 = self._convert_type("Tuple[bool, ...]")
    right7 = self._convert_type("Tuple[int, ...]")
    self.assertMatch(left, right1)
    self.assertNoMatch(left, right2)
    self.assertMatch(left, right3)
    self.assertNoMatch(left, right4)
    self.assertMatch(left, right5)
    self.assertNoMatch(left, right6)
    self.assertMatch(left, right7)

  def test_annotation_class(self):
    left = abstract.AnnotationClass("Dict", self.vm)
    right = self.vm.convert.object_type
    self.assertMatch(left, right)

  def test_empty_tuple_class(self):
    var = self.vm.program.NewVariable()
    params = {0: abstract.TypeParameter(abstract_utils.K, self.vm),
              1: abstract.TypeParameter(abstract_utils.V, self.vm)}
    params[abstract_utils.T] = abstract.Union((params[0], params[1]), self.vm)
    right = abstract.TupleClass(self.vm.convert.tuple_type, params, self.vm)
    match = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertSetEqual(set(match), {abstract_utils.K, abstract_utils.V})

  def test_unsolvable_against_tuple_class(self):
    left = self.vm.convert.unsolvable
    params = {0: abstract.TypeParameter(abstract_utils.K, self.vm),
              1: abstract.TypeParameter(abstract_utils.V, self.vm)}
    params[abstract_utils.T] = abstract.Union((params[0], params[1]), self.vm)
    right = abstract.TupleClass(self.vm.convert.tuple_type, params, self.vm)
    for match in self._match_var(left, right):
      self.assertSetEqual(set(match), {abstract_utils.K, abstract_utils.V})
      self.assertEqual(match[abstract_utils.K].data,
                       [self.vm.convert.unsolvable])
      self.assertEqual(match[abstract_utils.V].data,
                       [self.vm.convert.unsolvable])

  def test_bool_against_float(self):
    left = self.vm.convert.true
    right = self.vm.convert.primitive_classes[float]
    self.assertMatch(left, right)

  def test_pytd_function_against_callable(self):
    f = self._convert("def f(x: int) -> bool: ...", "f")
    plain_callable = self._convert_type("Callable")
    good_callable1 = self._convert_type("Callable[[bool], int]")
    good_callable2 = self._convert_type("Callable[..., int]")
    self.assertMatch(f, plain_callable)
    self.assertMatch(f, good_callable1)
    self.assertMatch(f, good_callable2)

  def test_pytd_function_against_callable_bad_return(self):
    f = self._convert("def f(x: int) -> bool: ...", "f")
    callable_bad_ret = self._convert_type("Callable[[int], str]")
    self.assertNoMatch(f, callable_bad_ret)

  def test_pytd_function_against_callable_bad_arg_count(self):
    f = self._convert("def f(x: int) -> bool: ...", "f")
    callable_bad_count1 = self._convert_type("Callable[[], bool]")
    callable_bad_count2 = self._convert_type("Callable[[int, str], bool]")
    self.assertNoMatch(f, callable_bad_count1)
    self.assertNoMatch(f, callable_bad_count2)

  def test_pytd_function_against_callable_bad_arg_type(self):
    f = self._convert("def f(x: bool) -> bool: ...", "f")
    callable_bad_arg1 = self._convert_type("Callable[[int], bool]")
    callable_bad_arg2 = self._convert_type("Callable[[str], bool]")
    self.assertNoMatch(f, callable_bad_arg1)
    self.assertNoMatch(f, callable_bad_arg2)

  def test_bound_pytd_function_against_callable(self):
    instance = self._convert("""
      class A(object):
        def f(self, x: int) -> bool: ...
    """, "A", as_instance=True)
    binding = instance.to_binding(self.vm.root_cfg_node)
    _, var = self.vm.attribute_handler.get_attribute(
        self.vm.root_cfg_node, instance, "f", binding)
    bound = var.data[0]
    _, var = self.vm.attribute_handler.get_attribute(
        self.vm.root_cfg_node, instance.cls, "f")
    unbound = var.data[0]
    callable_no_self = self._convert_type("Callable[[int]]")
    callable_self = self._convert_type("Callable[[Any, int]]")
    self.assertMatch(bound, callable_no_self)
    self.assertNoMatch(unbound, callable_no_self)
    self.assertNoMatch(bound, callable_self)
    self.assertMatch(unbound, callable_self)

  def test_native_function_against_callable(self):
    # Matching a native function against a callable always succeeds, regardless
    # of argument and return types.
    f = abstract.NativeFunction("f", lambda x: x, self.vm)
    callable_type = self._convert_type("Callable[[int], int]")
    self.assertMatch(f, callable_type)

  def test_callable_instance(self):
    left1 = self._convert_type("Callable[[int], bool]", as_instance=True)
    left2 = self._convert_type("Callable", as_instance=True)
    left3 = self._convert_type("Callable[..., int]", as_instance=True)
    right1 = self._convert_type("Callable[[bool], int]")
    right2 = self._convert_type("Callable[..., int]")
    right3 = self._convert_type("Callable")
    self.assertMatch(left1, right1)
    self.assertMatch(left2, right1)
    self.assertMatch(left3, right1)
    self.assertMatch(left1, right2)
    self.assertMatch(left2, right2)
    self.assertMatch(left3, right2)
    self.assertMatch(left1, right3)
    self.assertMatch(left2, right3)
    self.assertMatch(left3, right3)

  def test_callable_instance_bad_return(self):
    left1 = self._convert_type("Callable[[int], float]", as_instance=True)
    left2 = self._convert_type("Callable[..., float]", as_instance=True)
    right1 = self._convert_type("Callable[[bool], int]")
    right2 = self._convert_type("Callable[..., int]")
    self.assertNoMatch(left1, right1)
    self.assertNoMatch(left2, right1)
    self.assertNoMatch(left1, right2)
    self.assertNoMatch(left2, right2)

  def test_callable_instance_bad_arg_count(self):
    left1 = self._convert_type("Callable[[], int]", as_instance=True)
    left2 = self._convert_type("Callable[[str, str], int]", as_instance=True)
    right = self._convert_type("Callable[[str], int]")
    self.assertNoMatch(left1, right)
    self.assertNoMatch(left2, right)

  def test_callable_instance_bad_arg_type(self):
    left1 = self._convert_type("Callable[[bool], Any]", as_instance=True)
    left2 = self._convert_type("Callable[[str], Any]", as_instance=True)
    right = self._convert_type("Callable[[int], Any]")
    self.assertNoMatch(left1, right)
    self.assertNoMatch(left2, right)

  def test_type_against_callable(self):
    left1 = self._convert_type("Type[int]", as_instance=True)
    left2 = self._convert_type("Type[str]", as_instance=True)
    right1 = self._convert_type("Callable[..., float]")
    right2 = self._convert_type("Callable[[], float]")
    self.assertMatch(left1, right1)
    self.assertMatch(left1, right2)
    self.assertNoMatch(left2, right1)
    self.assertNoMatch(left2, right2)

  def test_anystr_instance_against_anystr(self):
    right = self.vm.convert.name_to_value("typing.AnyStr")
    dummy_instance = abstract.Instance(self.vm.convert.tuple_type, self.vm)
    left = abstract.TypeParameterInstance(right, dummy_instance, self.vm)
    for result in self._match_var(left, right):
      six.assertCountEqual(self,
                           [(name, var.data) for name, var in result.items()],
                           [("typing.AnyStr", [left])])

  def test_protocol(self):
    left1 = self._convert_type("str", as_instance=True)
    left2 = self._convert("""
      class A(object):
        def lower(self) : ...
    """, "A", as_instance=True)
    left3 = self._convert_type("int", as_instance=True)
    right = self._convert_type("SupportsLower")
    self.assertMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

  def test_protocol_iterator(self):
    left1 = self._convert_type("Iterator", as_instance=True)
    left2 = self._convert("""
      class A(object):
        def __next__(self): ...
        def __iter__(self): ...
    """, "A", as_instance=True)
    left3 = self._convert_type("int", as_instance=True)
    right = self._convert_type("Iterator")
    self.assertMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

  def test_protocol_sequence(self):
    left1 = self._convert_type("list", as_instance=True)
    left2 = self._convert("""
      class A(object):
        def __getitem__(self, i) : ...
        def __len__(self): ...
    """, "A", as_instance=True)
    left3 = self._convert_type("int", as_instance=True)
    right = self._convert_type("Sequence")
    self.assertMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

  @unittest.skip("Needs to be fixed, tries to match protocol against A")
  def test_parameterized_protocol(self):
    left1 = self._convert("""
      from typing import Iterator
      class A(object):
        def __iter__(self) -> Iterator[int] : ...
    """, "A", as_instance=True)
    left2 = self._convert_type("int", as_instance=True)
    right = self._convert_type("Iterable[int]")
    self.assertMatch(left1, right)
    self.assertNoMatch(left2, right)

  def test_no_return(self):
    self.assertMatch(self.vm.convert.no_return, self.vm.convert.no_return)

  def test_empty_against_no_return(self):
    self.assertNoMatch(self.vm.convert.empty, self.vm.convert.no_return)

  def test_no_return_against_class(self):
    right = self._convert_type("int")
    self.assertNoMatch(self.vm.convert.no_return, right)

  def test_empty_against_parameterized_iterable(self):
    left = self.vm.convert.empty
    right = abstract.ParameterizedClass(
        self.vm.convert.list_type,
        {abstract_utils.T: abstract.TypeParameter(
            abstract_utils.T, self.vm)}, self.vm)
    for subst in self._match_var(left, right):
      self.assertSetEqual(set(subst), {abstract_utils.T})
      self.assertListEqual(subst[abstract_utils.T].data,
                           [self.vm.convert.empty])

  def test_list_against_mapping(self):
    left = self._convert_type("list", as_instance=True)
    right = self.vm.convert.name_to_value("typing.Mapping")
    self.assertNoMatch(left, right)

  def test_list_against_parameterized_mapping(self):
    left = self._convert_type("list", as_instance=True)
    right = abstract.ParameterizedClass(
        self.vm.convert.name_to_value("typing.Mapping"),
        {abstract_utils.K: abstract.TypeParameter(abstract_utils.K, self.vm),
         abstract_utils.V: abstract.TypeParameter(
             abstract_utils.V, self.vm)}, self.vm)
    self.assertNoMatch(left, right)


if __name__ == "__main__":
  unittest.main()
