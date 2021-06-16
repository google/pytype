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
    actual = [(op.line, constant_folding.to_literal(op.arg.typ), op.arg.value)
              for op in folded]
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
        (1, ("list", int), [1, 2, 3])
    ])

  @test_utils.skipFromPy((3, 9), "Constant lists get optimised in 3.9")
  def test_union(self):
    actual = self._process("a = [1, 2, '3']")
    self.assertCountEqual(actual, [
        (1, ("list", (int, str)), [1, 2, "3"])
    ])

  def test_map(self):
    actual = self._process("a = {'x': 1, 'y': '2'}")
    self.assertCountEqual(actual, [
        (1, ("map", str, (int, str)), {"x": 1, "y": "2"})
    ])

  def test_tuple(self):
    actual = self._process("a = (1, '2', True)")
    self.assertCountEqual(actual, [
        (1, ("tuple", int, str, bool), (1, "2", True))
    ])

  def test_list_of_tuple(self):
    actual = self._process("a = [(1, '2', 3), (4, '5', 6)]")
    val = [(1, "2", 3), (4, "5", 6)]
    self.assertCountEqual(actual, [
        (1, ("list", ("tuple", int, str, int)), val)
    ])

  def test_list_of_varied_tuple(self):
    actual = self._process("a = [(1, '2', 3), ('4', '5', 6)]")
    val = [(1, "2", 3), ("4", "5", 6)]
    self.assertCountEqual(actual, [
        (1, ("list", (
            ("tuple", int, str, int),
            ("tuple", str, str, int)
        )), val)
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
    self.assertCountEqual(actual, [
        (4, ("map", k, (y, x, str)), val)
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
    self.assertCountEqual(actual, [
        (1, ("map", k, (y, x, str)), val)
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
    self.assertCountEqual(actual, [
        (4, ("list", ("map", str, str)), val)
    ])


class TypeBuilderTest(test_base.UnitTest):
  """Test constructing vm types from folded constants."""

  def setUp(self):
    super().setUp()
    options = config.Options.create(python_version=self.python_version)
    self.vm = vm.VirtualMachine(
        errors.ErrorLog(), options, load_pytd.Loader(None, self.python_version))
    self.state = frame_state.FrameState.init(self.vm.root_node, self.vm)

  def _convert(self, typ):
    typ = constant_folding.from_literal(typ)
    _, var = constant_folding.build_folded_type(self.vm, self.state, typ)
    val, = var.data
    return val

  def _is_primitive(self, val, cls):
    return (val.isinstance_Instance() and
            val.cls.isinstance_PyTDClass() and
            val.cls.pytd_cls.name == "builtins." + cls)

  def assertPytd(self, val, expected):
    pytd_tree = val.to_type()
    pytd_tree = pytd_tree.Visit(visitors.CanonicalOrderingVisitor())
    actual = pytd_utils.Print(pytd_tree)
    self.assertEqual(actual, expected)

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


if __name__ == "__main__":
  unittest.main()
