# Lint as: python2, python3
"""Tests for traces.traces."""

import ast
from pytype.tools.traces import source
from pytype.tools.traces import traces
import unittest


class _FakeTrace(source.AbstractTrace):
  """Fake trace class for testing."""


class _NotImplementedVisitor(traces.MatchAstVisitor):

  def visit_Module(self, node):
    self.match(node)


class MatchAstVisitorTest(unittest.TestCase):
  """Tests for traces.MatchAstVisitor."""

  def test_not_implemented(self):
    module = ast.parse("")
    src = source.Code("", [], _FakeTrace, "")
    v = _NotImplementedVisitor(src, ast)
    with self.assertRaises(NotImplementedError):
      v.visit(module)


if __name__ == "__main__":
  unittest.main()
