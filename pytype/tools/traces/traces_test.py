# Lint as: python2, python3
"""Tests for traces.traces."""

import ast
import collections
import sys
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

  def test_py3_class(self):
    src = traces.trace(textwrap.dedent("""\
      class Foo(object):
        pass
    """), config.Options.create(python_version=(3, 6)))
    trace, = (x for x in src.traces[1] if x.op == "LOAD_BUILD_CLASS")
    pyval, = trace.types
    self.assertEqual(pyval.name, "typing.Callable")

  def test_unknown(self):
    # pytype represents unannotated function parameters as unknowns. Make sure
    # unknowns don't appear in the traced types.
    src = traces.trace("def f(x): return x")
    trace, = (x for x in src.traces[1] if x.op == "LOAD_FAST")
    pyval, = trace.types
    self.assertIsInstance(pyval, pytd.AnythingType)


class MatchAstTestCase(unittest.TestCase):
  """Base class for testing traces.MatchAstVisitor."""

  def _parse(self, text):
    text = textwrap.dedent(text)
    return ast.parse(text), traces.trace(text)

  def _get_traces(self, text, node_type):
    module, src = self._parse(text)
    v = _TestVisitor(src, ast)
    v.visit(module)
    return v.traces_by_node_type[node_type]

  def assertTracesEqual(self, actual_traces, expected_traces):
    self.assertEqual(len(actual_traces), len(expected_traces))
    for trace, expected_trace in zip(actual_traces, expected_traces):
      loc, trace = trace
      expected_loc, expected_op, expected_symbol, expected_annots = (
          expected_trace)
      self.assertEqual(loc, expected_loc)
      self.assertEqual(trace.op, expected_op)
      self.assertEqual(trace.symbol, expected_symbol)
      self.assertEqual(len(trace.types), len(expected_annots))
      for t, annot in zip(trace.types, expected_annots):
        self.assertEqual(pytd.Print(t), annot)


class MatchAstVisitorTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisitor."""

  def test_not_implemented(self):
    module, src = self._parse("")
    v = _NotImplementedVisitor(src, ast)
    with self.assertRaises(NotImplementedError):
      v.visit(module)

  def test_attr(self):
    matches = self._get_traces("""\
      x = 0
      print(x.real)
    """, ast.Attribute)
    self.assertTracesEqual(matches, [
        ((2, 8), "LOAD_ATTR", "real", ("int", "int"))])

  def test_import(self):
    matches = self._get_traces("import os, sys as tzt", ast.Import)
    self.assertTracesEqual(matches, [
        ((1, 7), "IMPORT_NAME", "os", ("module",)),
        ((1, 18), "STORE_NAME", "tzt", ("module",))])

  def test_import_from(self):
    matches = self._get_traces(
        "from os import path as _path, environ", ast.ImportFrom)
    self.assertTracesEqual(matches, [
        ((1, 23), "STORE_NAME", "_path", ("module",)),
        ((1, 30), "STORE_NAME", "environ", ("os._Environ[str]",))])


class MatchNameTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisitor.match_Name."""

  def test_basic(self):
    matches = self._get_traces("x = 42", ast.Name)
    self.assertTracesEqual(matches, [((1, 0), "STORE_NAME", "x", ("int",))])

  def test_multiline(self):
    matches = self._get_traces("""\
      x = (1 +
           2)
    """, ast.Name)
    self.assertTracesEqual(matches, [((1, 0), "STORE_NAME", "x", ("int",))])

  def test_multiline_subscr(self):
    matches = self._get_traces("""\
      x = [0]
      x[0] = (1,
              2)
    """, ast.Name)
    x_annot = "List[Union[int, Tuple[int, int]]]"
    self.assertTracesEqual(matches, [((1, 0), "STORE_NAME", "x", (x_annot,)),
                                     ((2, 0), "LOAD_NAME", "x", (x_annot,))])


class MatchCallTest(MatchAstTestCase):
  """Tests for traces.MatchAstVisitor.match_Call."""

  def test_basic(self):
    matches = self._get_traces("""\
      def f(x):
        return x + 1.0
      f(42)
    """, ast.Call)
    self.assertTracesEqual(matches, [
        ((3, 0), "CALL_FUNCTION", "f", ("Callable[[Any], Any]", "float"))])

  def test_chain(self):
    matches = self._get_traces("""\
      class Foo(object):
        def f(self, x):
          return x
      Foo().f(42)
    """, ast.Call)
    if sys.version_info >= (3, 7):
      call_method_op = "CALL_METHOD"
    else:
      call_method_op = "CALL_FUNCTION"
    self.assertTracesEqual(matches, [
        ((4, 0), "CALL_FUNCTION", "Foo", ("Type[Foo]", "Foo")),
        ((4, 0), call_method_op, "f", ("Callable[[Any], Any]", "int"))])

  def test_multiple_bindings(self):
    matches = self._get_traces("""\
      class Foo(object):
        @staticmethod
        def f(x):
          return x
      class Bar(object):
        @staticmethod
        def f(x):
          return x + 1.0
      f = Foo.f if __random__ else Bar.f
      f(42)
    """, ast.Call)
    self.assertTracesEqual(matches, [
        ((10, 0), "CALL_FUNCTION", "f", ("Callable[[Any], Any]", "int")),
        ((10, 0), "CALL_FUNCTION", "f", ("Callable[[Any], Any]", "float"))])

  def test_bad_call(self):
    matches = self._get_traces("""\
      def f(): pass
      f(42)
    """, ast.Call)
    self.assertTracesEqual(
        matches, [((2, 0), "CALL_FUNCTION", "f", ("Callable[[], Any]", "Any"))])


if __name__ == "__main__":
  unittest.main()
