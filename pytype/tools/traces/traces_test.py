# Lint as: python2, python3
"""Tests for traces.traces."""

import ast
from pytype import config
from pytype.tools.traces import traces
import unittest


class _NotImplementedVisitor(traces.MatchAstVisitor):

  def visit_Module(self, node):
    self.match(node)


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
    pyi = self.create_tempfile(
        file_path="foo.pyi", content="class Foo(object): ...")
    imports_info = self.create_tempfile(content="foo %s" % pyi.full_path)
    src = traces.trace(
        "import foo\nx = foo.Foo()",
        config.Options.create(imports_map=imports_info.full_path))
    trace, = (x for x in src.traces[2] if x.op == "STORE_NAME")
    pyval, = trace.types
    self.assertEqual(pyval.name, "foo.Foo")
    self.assertEqual(pyval.cls.name, "foo.Foo")


class MatchAstVisitorTest(unittest.TestCase):
  """Tests for traces.MatchAstVisitor."""

  def test_not_implemented(self):
    module = ast.parse("")
    src = traces.trace("")
    v = _NotImplementedVisitor(src, ast)
    with self.assertRaises(NotImplementedError):
      v.visit(module)


if __name__ == "__main__":
  unittest.main()
