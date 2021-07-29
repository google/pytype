"""Tests for constant_folding.py."""

import textwrap

from pytype import blocks
from pytype import config
from pytype import constant_folding
from pytype import errors
from pytype import load_pytd
from pytype import state as frame_state
from pytype import vm
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.tests import test_base
from pytype.tests import test_utils

import unittest


def fmt(code):
  if code.startswith("\n"):
    code = code[1:]
  return textwrap.dedent(code)


def show_op(op):
  literal = constant_folding.to_literal
  typ = literal(op.arg.typ)
  elements = op.arg.elements
  if isinstance(elements, dict):
    elements = {k: literal(v) for k, v in elements.items()}
  elif elements:
    elements = [literal(v) for v in elements]
  return (op.line, typ, op.arg.value, elements)


class TestFolding(test_base.UnitTest):
  """Tests for FoldConstant."""

  def _compile(self, src, mode="exec"):
    exe = (["python" + ".".join(map(str, self.python_version))], [])
    pyc_data = pyc.compile_src_string_to_pyc_string(
        src, filename="test_input.py", python_version=self.python_version,
        python_exe=exe, mode=mode)
    code = pyc.parse_pyc_string(pyc_data)
    code = blocks.process_code(code, self.python_version)
    return code

  def _find_load_folded(self, code):
    out = []
    for block in code.order:
      out.extend([x for x in block if isinstance(x, opcodes.LOAD_FOLDED_CONST)])
    return out

  def _fold(self, code):
    code = constant_folding.optimize(code)
    folded = self._find_load_folded(code)
    actual = [show_op(op) for op in folded]
    return actual

  def _process(self, src):
    src = fmt(src)
    code = self._compile(src)
    actual = self._fold(code)
    return actual

  @test_utils.skipFromPy((3, 9), "Constant lists get optimised in 3.9")
  def test_basic(self):
    actual = self._process("a = [1, 2, 3]")
    self.assertCountEqual(actual, [
        (1, ("list", int), [1, 2, 3], [int, int, int])
    ])

  @test_utils.skipFromPy((3, 9), "Constant lists get optimised in 3.9")
  def test_union(self):
    actual = self._process("a = [1, 2, '3']")
    self.assertCountEqual(actual, [
        (1, ("list", (int, str)), [1, 2, "3"], [int, int, str])
    ])

  def test_map(self):
    actual = self._process("a = {'x': 1, 'y': '2'}")
    self.assertCountEqual(actual, [
        (1, ("map", str, (int, str)), {"x": 1, "y": "2"}, {"x": int, "y": str})
    ])

  def test_tuple(self):
    actual = self._process("a = (1, '2', True)")
    # Tuples are already a single LOAD_CONST operation and so don't get folded
    self.assertCountEqual(actual, [])

  def test_list_of_tuple(self):
    actual = self._process("a = [(1, '2', 3), (4, '5', 6)]")
    val = [(1, "2", 3), (4, "5", 6)]
    elements = [("tuple", int, str, int), ("tuple", int, str, int)]
    self.assertCountEqual(actual, [
        (1, ("list", ("tuple", int, str, int)), val, elements)
    ])

  def test_list_of_varied_tuple(self):
    actual = self._process("a = [(1, '2', 3), ('4', '5', 6)]")
    val = [(1, "2", 3), ("4", "5", 6)]
    elements = [("tuple", int, str, int),
                ("tuple", str, str, int)]
    self.assertCountEqual(actual, [
        (1, ("list", (
            ("tuple", int, str, int),
            ("tuple", str, str, int)
        )), val, elements)
    ])

  @test_utils.skipFromPy((3, 8), "opcode line number changed in 3.8")
  def test_nested_pre38(self):
    actual = self._process("""
      a = {
        'x': [(1, '2', 3), ('4', '5', 6)],
        'y': [{'a': 'b'}, {'c': 'd'}],
        ('p', 'q'): 'r'
      }
    """)
    val = {
        "x": [(1, "2", 3), ("4", "5", 6)],
        "y": [{"a": "b"}, {"c": "d"}],
        ("p", "q"): "r"
    }
    x = ("list", (
        ("tuple", int, str, int),
        ("tuple", str, str, int)
    ))
    y = ("list", ("map", str, str))
    k = (("tuple", str, str), str)
    elements = {"x": x, "y": y, ("p", "q"): str}
    self.assertCountEqual(actual, [
        (4, ("map", k, (y, x, str)), val, elements)
    ])

  # TODO(b/175443170): Change the decorator to skipBeforePy once 3.9 works.
  @test_utils.skipUnlessPy((3, 8), reason="Constant lists get optimised in 3.9")
  def test_nested(self):
    actual = self._process("""
      a = {
        'x': [(1, '2', 3), ('4', '5', 6)],
        'y': [{'a': 'b'}, {'c': 'd'}],
        ('p', 'q'): 'r'
      }
    """)
    val = {
        "x": [(1, "2", 3), ("4", "5", 6)],
        "y": [{"a": "b"}, {"c": "d"}],
        ("p", "q"): "r"
    }
    x = ("list", (
        ("tuple", int, str, int),
        ("tuple", str, str, int)
    ))
    y = ("list", ("map", str, str))
    k = (("tuple", str, str), str)
    elements = {"x": x, "y": y, ("p", "q"): str}
    self.assertCountEqual(actual, [
        (1, ("map", k, (y, x, str)), val, elements)
    ])

  def test_partial(self):
    actual = self._process("""
      x = 1
      a = {
        "x": x,
        "y": [{"a": "b"}, {"c": "d"}],
      }
    """)
    val = [{"a": "b"}, {"c": "d"}]
    map_type = ("map", str, str)
    self.assertCountEqual(actual, [
        (4, ("list", map_type), val, [map_type, map_type])
    ])

  def test_nested_partial(self):
    # Test that partial expressions get cleaned off the stack properly. The 'if'
    # is there to introduce block boundaries.
    actual = self._process("""
      v = None
      x = {
         [{'a': 'c', 'b': v}],
         [{'a': 'd', 'b': v}]
      }
      if __random__:
        y = [{'value': v, 'type': 'a'}]
      else:
        y = [{'value': v, 'type': 'b'}]
    """)
    self.assertCountEqual(actual, [])


class TypeBuilderTestBase(test_base.UnitTest):
  """Base class for constructing and testing vm types."""

  def setUp(self):
    super().setUp()
    options = config.Options.create(python_version=self.python_version)
    self.vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))
    self.vm._fold_constants = True

  def assertPytd(self, val, expected):
    pytd_tree = val.to_type()
    pytd_tree = pytd_tree.Visit(visitors.CanonicalOrderingVisitor())
    actual = pytd_utils.Print(pytd_tree)
    self.assertEqual(actual, expected)


class TypeBuilderTest(TypeBuilderTestBase):
  """Test constructing vm types from folded constants."""

  def setUp(self):
    super().setUp()
    self.state = frame_state.FrameState.init(self.vm.root_node, self.vm)

  def _convert(self, typ):
    typ = constant_folding.from_literal(typ)
    const = constant_folding._Constant(typ, None, None, None)
    _, var = constant_folding.build_folded_type(self.vm, self.state, const)
    val, = var.data
    return val

  def _is_primitive(self, val, cls):
    return (val.isinstance_Instance() and
            val.cls.isinstance_PyTDClass() and
            val.cls.pytd_cls.name == "builtins." + cls)

  def test_prim(self):
    val = self._convert(("prim", str))
    self.assertTrue(self._is_primitive(val, "str"))

  def test_homogeneous_list(self):
    val = self._convert(("list", int))
    self.assertPytd(val, "List[int]")

  def test_heterogeneous_list(self):
    val = self._convert(("list", (int, str)))
    self.assertPytd(val, "List[Union[int, str]]")

  def test_homogeneous_map(self):
    val = self._convert(("map", str, int))
    self.assertPytd(val, "Dict[str, int]")

  def test_heterogeneous_map(self):
    val = self._convert(("map", (str, int), (("list", str), str)))
    self.assertPytd(val, "Dict[Union[int, str], Union[List[str], str]]")

  def test_tuple(self):
    val = self._convert(("tuple", str, int, bool))
    self.assertPytd(val, "Tuple[str, int, bool]")


class PyvalTest(TypeBuilderTestBase):
  """Test preservation of concrete values."""

  def _process(self, src):
    src = fmt(src)
    _, defs = self.vm.run_program(src, "", maximum_depth=4)
    return defs

  def assertNoPyval(self, val):
    self.assertFalse(hasattr(val, "pyval"))

  def test_simple_list(self):
    defs = self._process("""
      a = [1, '2', 3]
      b = a[1]
    """)
    a = defs["a"].data[0]
    b = defs["b"].data[0]
    self.assertPytd(a, "List[Union[int, str]]")
    self.assertPytd(b, "str")
    self.assertEqual(a.pyval[0].data[0].pyval, 1)

  @test_utils.skipFromPy((3, 9), "assertNoPyval check fails in 3.9")
  def test_nested_list(self):
    defs = self._process("""
      a = [[1, '2', 3], [4, 5]]
      b, c = a
    """)
    a = defs["a"].data[0]
    b = defs["b"].data[0]
    c = defs["c"].data[0]
    t1 = "List[Union[int, str]]"
    t2 = "List[int]"
    self.assertPytd(a, f"List[Union[{t2}, {t1}]]")
    self.assertPytd(b, t1)
    self.assertPytd(c, t2)
    self.assertNoPyval(a.pyval[0].data[0])

  def test_long_list(self):
    elts = ["  [1, 2],", "  ['a'],"] * 42
    src = ["a = ["] + elts + ["]"]
    defs = self._process("\n".join(src))
    a = defs["a"].data[0]
    t1 = "List[int]"
    t2 = "List[str]"
    self.assertPytd(a, f"List[Union[{t1}, {t2}]]")
    self.assertNoPyval(a)

  def test_simple_map(self):
    defs = self._process("""
      a = {'b': 1, 'c': '2'}
      b = a['b']
      c = a['c']
    """)
    a = defs["a"].data[0]
    b = defs["b"].data[0]
    c = defs["c"].data[0]
    self.assertPytd(a, "Dict[str, Union[int, str]]")
    self.assertPytd(b, "int")
    self.assertPytd(c, "str")
    self.assertEqual(a.pyval["b"].data[0].pyval, 1)

  @test_utils.skipFromPy((3, 9), "assertNoPyval check fails in 3.9")
  def test_nested_map(self):
    defs = self._process("""
      a = {'b': [1, '2', 3], 'c': {'x': 4}}
      b = a['b']
      c = a['c']
    """)
    a = defs["a"].data[0]
    b = defs["b"].data[0]
    c = defs["c"].data[0]
    t1 = "List[Union[int, str]]"
    t2 = "Dict[str, int]"
    self.assertPytd(a, f"Dict[str, Union[{t2}, {t1}]]")
    self.assertPytd(b, t1)
    self.assertPytd(c, t2)
    self.assertNoPyval(a.pyval["b"].data[0])
    # We create an empty pyval by default for abstract.Dict
    self.assertFalse(a.pyval["c"].data[0].pyval)

  def test_long_map(self):
    elts = [f"  'k{i}': [1, 2]," for i in range(64)]
    src = ["a = {"] + elts + ["}"]
    defs = self._process("\n".join(src))
    a = defs["a"].data[0]
    self.assertPytd(a, "Dict[str, List[int]]")
    self.assertFalse(a.pyval)


if __name__ == "__main__":
  unittest.main()
