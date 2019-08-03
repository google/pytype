# Lint as: python2, python3
"""Tests for traces.traces."""

import ast
import collections
import textwrap
from pytype import config
from pytype import file_utils
from pytype.pytd import pytd
from pytype.tools.traces import traces
import unittest


class _NotImplementedVisitor(traces.MatchAstVisitor):

  def visit_Module(self, node):
    self.match(node)


class _TestVisitor(traces.MatchAstVisitor):

  def __init__(self, *args, **kwargs):
    super(_TestVisitor, self).__init__(*args, **kwargs)
    self.traces_by_node_type = collections.defaultdict(list)

  def generic_visit(self, node):
    try:
      matches = self.match(node)
    except NotImplementedError:
      return
    self.traces_by_node_type[node.__class__].extend(matches)


class TraceTest(unittest.TestCase):
  """Tests for traces.trace."""

  def test_traces(self):
    src = traces.trace("")
    trace, = src.traces[1]
    self.assertEqual(trace.op, "LOAD_CONST")
    self.assertEqual(trace.symbol, None)
    pyval, = trace.types
    self.assertEqual(pyval.name, "__builtin__.NoneType")
    self.assertEqual(pyval.cls.name, "__builtin__.NoneType")

  def test_options(self):
    src = traces.trace("", config.Options.create("rumpelstiltskin"))
    self.assertEqual(src.filename, "rumpelstiltskin")

  def test_external_type(self):
    with file_utils.Tempdir() as d:
      pyi_path = d.create_file("foo.pyi", "class Foo(object): ...")
      imports_info = d.create_file("imports_info", "foo %s" % pyi_path)
      src = traces.trace(
          "import foo\nx = foo.Foo()",
          config.Options.create(imports_map=imports_info))
    trace, = (x for x in src.traces[2] if x.op == "STORE_NAME")
    pyval, = trace.types
    self.assertEqual(pyval.name, "foo.Foo")
    self.assertEqual(pyval.cls.name, "foo.Foo")


class MatchAstVisitorTest(unittest.TestCase):
  """Tests for traces.MatchAstVisitor."""

  def _parse(self, text):
    text = textwrap.dedent(text)
    return ast.parse(text), traces.trace(text)

  def _get_traces(self, text, node_type):
    module, src = self._parse(text)
    v = _TestVisitor(src, ast)
    v.visit(module)
    return v.traces_by_node_type[node_type]

  def assertTraceEqual(self, loc_and_trace, expected_loc, expected_op,
                       expected_symbol, expected_annots):
    loc, trace = loc_and_trace
    self.assertEqual(loc, expected_loc)
    self.assertEqual(trace.op, expected_op)
    self.assertEqual(trace.symbol, expected_symbol)
    self.assertEqual(len(trace.types), len(expected_annots))
    for t, annot in zip(trace.types, expected_annots):
      self.assertEqual(pytd.Print(t), annot)

  def test_not_implemented(self):
    module, src = self._parse("")
    v = _NotImplementedVisitor(src, ast)
    with self.assertRaises(NotImplementedError):
      v.visit(module)

  def test_attr(self):
    trace, = self._get_traces("""\
      x = 0
      print(x.real)
    """, ast.Attribute)
    self.assertTraceEqual(trace, (2, 8), "LOAD_ATTR", "real", ("int", "int"))

  def test_import(self):
    os_trace, tzt_trace = self._get_traces("import os, sys as tzt", ast.Import)
    self.assertTraceEqual(os_trace, (1, 7), "IMPORT_NAME", "os", ("module",))
    self.assertTraceEqual(tzt_trace, (1, 18), "STORE_NAME", "tzt", ("module",))

  def test_import_from(self):
    path_trace, environ_trace = self._get_traces(
        "from os import path as _path, environ", ast.ImportFrom)
    self.assertTraceEqual(path_trace,
                          (1, 23), "STORE_NAME", "_path", ("module",))
    self.assertTraceEqual(
        environ_trace,
        (1, 30), "STORE_NAME", "environ", ("os._Environ[str]",))

  def test_name(self):
    trace, = self._get_traces("x = 42", ast.Name)
    self.assertTraceEqual(trace, (1, 0), "STORE_NAME", "x", ("int",))

  def test_name_multiline(self):
    trace, = self._get_traces("""\
      x = (1 +
           2)
    """, ast.Name)
    self.assertTraceEqual(trace, (1, 0), "STORE_NAME", "x", ("int",))

  def test_name_multiline_subscr(self):
    store_trace, load_trace = self._get_traces("""\
      x = [0]
      x[0] = (1,
              2)
    """, ast.Name)
    x_annot = "List[Union[int, Tuple[int, int]]]"
    self.assertTraceEqual(store_trace, (1, 0), "STORE_NAME", "x", (x_annot,))
    self.assertTraceEqual(load_trace, (2, 0), "LOAD_NAME", "x", (x_annot,))


if __name__ == "__main__":
  unittest.main()
