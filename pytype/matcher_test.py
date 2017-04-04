"""Tests for matcher.py."""


from pytype import abstract
from pytype import config
from pytype import errors
from pytype import load_pytd
from pytype import utils
from pytype import vm

import unittest


class MatcherTest(unittest.TestCase):
  """Test matcher.AbstractMatcher."""

  def setUp(self):
    options = config.Options([""])
    self.vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, options))
    self.type_type = abstract.get_atomic_value(self.vm.convert.type_type)

  def _make_class(self, name):
    return abstract.InterpreterClass(name, [], {}, None, self.vm)

  def _parse_and_lookup(self, src, objname, filename=None):
    if filename is None:
      filename = str(hash(src))
    with utils.Tempdir() as d:
      d.create_file(filename + ".pyi", src)
      self.vm.options.tweak(pythonpath=[d.path])
      ast = self.vm.loader.import_name(filename)
      return ast.Lookup(filename + "." + objname)

  def _convert(self, t, as_instance):
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
    src = "from typing import Tuple, Type\n"
    src += "x = ...  # type: " + t
    filename = str(hash((t, as_instance)))
    x = self._parse_and_lookup(src, "x", filename).type
    if as_instance:
      x = abstract.AsInstance(x)
    return self.vm.convert.constant_to_value(x, {}, self.vm.root_cfg_node)

  def _match_var(self, left, right):
    var = self.vm.program.NewVariable()
    var.AddBinding(left, [], self.vm.root_cfg_node)
    for view in abstract.get_views([var], self.vm.root_cfg_node):
      yield self.vm.matcher.match_var_against_type(
          var, right, {}, self.vm.root_cfg_node, view)

  def assertMatch(self, left, right):
    for match in self._match_var(left, right):
      self.assertEquals(match, {})

  def assertNoMatch(self, left, right):
    for match in self._match_var(left, right):
      self.assertIsNone(match)

  def testBasic(self):
    self.assertMatch(abstract.Empty(self.vm), abstract.Nothing(self.vm))

  def testType(self):
    left = self._make_class("dummy")
    type_parameters = {abstract.T: abstract.TypeParameter(abstract.T, self.vm)}
    other_type = abstract.ParameterizedClass(
        self.type_type, type_parameters, self.vm)
    for result in self._match_var(left, other_type):
      instance_binding, = result[abstract.T].bindings
      cls_binding, = instance_binding.data.cls.bindings
      self.assertEquals(cls_binding.data, left)

  def testUnion(self):
    left_option1 = self._make_class("o1")
    left_option2 = self._make_class("o2")
    left = abstract.Union([left_option1, left_option2], self.vm)
    self.assertMatch(left, self.type_type)

  def testMetaclass(self):
    left = self._make_class("left")
    meta1 = self._make_class("m1")
    meta2 = self._make_class("m2")
    left.cls = self.vm.program.NewVariable(
        [meta1, meta2], [], self.vm.root_cfg_node)
    self.assertMatch(left, meta1)
    self.assertMatch(left, meta2)

  def testEmptyAgainstClass(self):
    var = self.vm.program.NewVariable()
    right = self._make_class("bar")
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEquals(result, {})

  def testEmptyAgainstNothing(self):
    var = self.vm.program.NewVariable()
    right = abstract.Nothing(self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEquals(result, {})

  def testEmptyAgainstTypeParameter(self):
    var = self.vm.program.NewVariable()
    right = abstract.TypeParameter("T", self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertItemsEqual(result, ["T"])
    self.assertFalse(result["T"].bindings)

  def testEmptyAgainstUnsolvable(self):
    var = self.vm.program.NewVariable()
    right = abstract.Empty(self.vm)
    result = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertEquals(result, {})

  def testClassAgainstTypeUnion(self):
    left = self._make_class("foo")
    union = abstract.Union((left,), self.vm)
    right = abstract.ParameterizedClass(
        self.type_type, {abstract.T: union}, self.vm)
    self.assertMatch(left, right)

  def testNoneAgainstBool(self):
    # See pep484.COMPAT_ITEMS.
    left = self._convert("None", as_instance=True)
    right = self._convert("bool", as_instance=False)
    self.assertMatch(left, right)

  def testHomogeneousTuple(self):
    left = self._convert("Tuple[int, ...]", as_instance=True)
    right1 = self._convert("Tuple[int, ...]", as_instance=False)
    right2 = self._convert("Tuple[str, ...]", as_instance=False)
    self.assertMatch(left, right1)
    self.assertNoMatch(left, right2)

  def testHeterogeneousTuple(self):
    left1 = self._convert("Tuple[int or str]", as_instance=True)
    left2 = self._convert("Tuple[int, str]", as_instance=True)
    left3 = self._convert("Tuple[str, int]", as_instance=True)
    right = self._convert("Tuple[int, str]", as_instance=False)
    self.assertNoMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

  def testHeterogeneousTupleAgainstHomogeneousTuple(self):
    left = self._convert("Tuple[bool, int]", as_instance=True)
    right1 = self._convert("Tuple[bool, ...]", as_instance=False)
    right2 = self._convert("Tuple[int, ...]", as_instance=False)
    right3 = self._convert("tuple", as_instance=False)
    self.assertNoMatch(left, right1)
    self.assertMatch(left, right2)
    self.assertMatch(left, right3)

  def testHomogeneousTupleAgainstHeterogeneousTuple(self):
    left1 = self._convert("Tuple[bool, ...]", as_instance=True)
    left2 = self._convert("Tuple[int, ...]", as_instance=True)
    left3 = self._convert("tuple", as_instance=True)
    right = self._convert("Tuple[bool, int]", as_instance=False)
    self.assertMatch(left1, right)
    self.assertNoMatch(left2, right)
    self.assertMatch(left3, right)

  def testTupleType(self):
    # homogeneous against homogeneous
    left = self._convert("Type[Tuple[float, ...]]", as_instance=True)
    right1 = self._convert("Type[Tuple[float, ...]]", as_instance=False)
    right2 = self._convert("Type[Tuple[str, ...]]", as_instance=False)
    self.assertMatch(left, right1)
    self.assertNoMatch(left, right2)

    # heterogeneous against heterogeneous
    left1 = self._convert("Type[Tuple[int or str]]", as_instance=True)
    left2 = self._convert("Type[Tuple[int, str]]", as_instance=True)
    left3 = self._convert("Type[Tuple[str, int]]", as_instance=True)
    right = self._convert("Type[Tuple[int, str]]", as_instance=False)
    self.assertNoMatch(left1, right)
    self.assertMatch(left2, right)
    self.assertNoMatch(left3, right)

    # heterogeneous against homogeneous
    left = self._convert("Type[Tuple[bool, int]]", as_instance=True)
    right1 = self._convert("Type[Tuple[bool, ...]]", as_instance=False)
    right2 = self._convert("Type[Tuple[int, ...]]", as_instance=False)
    right3 = self._convert("Type[tuple]", as_instance=False)
    self.assertNoMatch(left, right1)
    self.assertMatch(left, right2)
    self.assertMatch(left, right3)

    # homogeneous against heterogeneous
    left1 = self._convert("Type[Tuple[bool, ...]]", as_instance=True)
    left2 = self._convert("Type[Tuple[int, ...]]", as_instance=True)
    left3 = self._convert("Type[tuple]", as_instance=True)
    right = self._convert("Type[Tuple[bool, int]]", as_instance=False)
    self.assertMatch(left1, right)
    self.assertNoMatch(left2, right)
    self.assertMatch(left3, right)

  def testTupleSubclass(self):
    subclass = self._parse_and_lookup("""
      from typing import Tuple
      class A(Tuple[bool, int]): ...""", "A")
    left = self.vm.convert.constant_to_value(
        abstract.AsInstance(subclass), {}, self.vm.root_cfg_node)
    right1 = self._convert("Tuple[bool, int]", as_instance=False)
    right2 = self._convert("Tuple[int, bool]", as_instance=False)
    right3 = self._convert("Tuple[int, int]", as_instance=False)
    right4 = self._convert("Tuple[int]", as_instance=False)
    right5 = self._convert("tuple", as_instance=False)
    right6 = self._convert("Tuple[bool, ...]", as_instance=False)
    right7 = self._convert("Tuple[int, ...]", as_instance=False)
    self.assertMatch(left, right1)
    self.assertNoMatch(left, right2)
    self.assertMatch(left, right3)
    self.assertNoMatch(left, right4)
    self.assertMatch(left, right5)
    self.assertNoMatch(left, right6)
    self.assertMatch(left, right7)

  def testAnnotationClass(self):
    left = abstract.AnnotationClass("Dict", self.vm)
    right = self.vm.convert.object_type.data[0]
    self.assertMatch(left, right)

  def testEmptyTupleClass(self):
    var = self.vm.program.NewVariable()
    params = {0: abstract.TypeParameter(abstract.K, self.vm),
              1: abstract.TypeParameter(abstract.V, self.vm)}
    params[abstract.T] = abstract.Union((params[0], params[1]), self.vm)
    right = abstract.TupleClass(
        self.vm.convert.tuple_type.data[0], params, self.vm)
    match = self.vm.matcher.match_var_against_type(
        var, right, {}, self.vm.root_cfg_node, {})
    self.assertSetEqual(set(match), {abstract.K, abstract.V})

  def testUnsolvableAgainstTupleClass(self):
    left = self.vm.convert.unsolvable
    params = {0: abstract.TypeParameter(abstract.K, self.vm),
              1: abstract.TypeParameter(abstract.V, self.vm)}
    params[abstract.T] = abstract.Union((params[0], params[1]), self.vm)
    right = abstract.TupleClass(
        self.vm.convert.tuple_type.data[0], params, self.vm)
    for match in self._match_var(left, right):
      self.assertSetEqual(set(match), {abstract.K, abstract.V})
      self.assertEquals(match[abstract.K].data, [self.vm.convert.unsolvable])
      self.assertEquals(match[abstract.V].data, [self.vm.convert.unsolvable])

  def testBoolAgainstFloat(self):
    left = self.vm.convert.true
    right = self.vm.convert.primitive_classes[float].data[0]
    self.assertMatch(left, right)


if __name__ == "__main__":
  unittest.main()
