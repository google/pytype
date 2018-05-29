"""Tests for utils.py."""

import logging
import textwrap

from pytype import debug
from pytype.typegraph import cfg

import unittest


log = logging.getLogger(__name__)


class Node(object):
  """A graph node, for testing tree printing."""

  def __init__(self, name, *incoming):
    self.name = name
    self.outgoing = []
    self.incoming = list(incoming)
    for n in incoming:
      n.outgoing.append(self)

  def connect_to(self, other_node):
    self.outgoing.append(other_node)
    other_node.incoming.append(self)

  def __repr__(self):
    return "Node(%s)" % self.name


class DebugTest(unittest.TestCase):

  def setUp(self):
    self.prog = cfg.Program()
    self.current_location = self.prog.NewCFGNode()

  def testAsciiTree(self):
    n1 = Node("n1")
    n2 = Node("n2", n1)
    n3 = Node("n3", n2)
    n4 = Node("n4", n3)
    n5 = Node("n5", n1)
    n6 = Node("n6", n5)
    n7 = Node("n7", n5)
    del n4, n6  # make pylint happy
    s = debug.ascii_tree(n1, lambda n: n.outgoing)
    self.assertMultiLineEqual(textwrap.dedent("""\
      Node(n1)
      |
      +-Node(n2)
      | |
      | +-Node(n3)
      |   |
      |   +-Node(n4)
      |
      +-Node(n5)
        |
        +-Node(n6)
        |
        +-Node(n7)
    """), s)
    s = debug.ascii_tree(n7, lambda n: n.incoming)
    self.assertMultiLineEqual(textwrap.dedent("""\
      Node(n7)
      |
      +-Node(n5)
        |
        +-Node(n1)
    """), s)

  def testAsciiGraph(self):
    n1 = Node("n1")
    n2 = Node("n2", n1)
    n3 = Node("n3", n2)
    n3.connect_to(n1)
    s = debug.ascii_tree(n1, lambda n: n.outgoing)
    self.assertMultiLineEqual(textwrap.dedent("""\
      Node(n1)
      |
      +-Node(n2)
        |
        +-Node(n3)
          |
          +-[Node(n1)]
    """), s)

  def testAsciiGraphWithCustomText(self):
    n1 = Node("n1")
    n2 = Node("n2", n1)
    n3 = Node("n3", n2)
    n3.connect_to(n1)
    s = debug.ascii_tree(n1, lambda n: n.outgoing, lambda n: n.name.upper())
    self.assertMultiLineEqual(textwrap.dedent("""\
      N1
      |
      +-N2
        |
        +-N3
          |
          +-[N1]
    """), s)

  def testRootCause(self):
    n1 = self.prog.NewCFGNode()
    n2 = self.prog.NewCFGNode()
    self.assertEqual((None, None), debug.root_cause([], n1))
    v = self.prog.NewVariable()
    b1 = v.AddBinding("foo", (), n2)  # not connected to n1
    self.assertEqual((b1, n1), debug.root_cause([b1], n1))
    v = self.prog.NewVariable()
    b2 = v.AddBinding("foo", (b1,), n1)
    self.assertEqual((b1, n1), debug.root_cause([b2], n1))

  def testTreePrettyPrinter(self):
    n1 = self.prog.NewCFGNode("root")
    n2 = self.prog.NewCFGNode("init")
    n2.ConnectTo(n1)
    v = self.prog.NewVariable()
    b1 = v.AddBinding("foo", (), n2)
    v = self.prog.NewVariable()
    _ = v.AddBinding("bar", (b1,), n1)
    s = debug.prettyprint_cfg_tree(n1)
    assert isinstance(s, str)  # smoke test

  def testPrettyPrintBindingSet(self):
    v = self.prog.NewVariable()
    b1 = v.AddBinding("x", [], self.current_location)
    b2 = v.AddBinding("y", [], self.current_location)
    # smoke test
    assert isinstance(debug.prettyprint_binding_set({b1, b2}), str)

  def testPrettyPrintBindingNested(self):
    v1 = self.prog.NewVariable()
    b1 = v1.AddBinding("x", [], self.current_location)
    v2 = self.prog.NewVariable()
    b2 = v2.AddBinding("y", {b1}, self.current_location)
    assert isinstance(debug.prettyprint_binding_nested(b2), str)  # smoke test

  def testProgramToText(self):
    v1 = self.prog.NewVariable()
    b = v1.AddBinding("x", [], self.current_location)
    n = self.current_location.ConnectNew()
    v2 = self.prog.NewVariable()
    v2.AddBinding("y", {b}, n)
    assert isinstance(debug.program_to_text(self.prog), str)  # smoke test

  def testProgramToDot(self):
    v1 = self.prog.NewVariable()
    b = v1.AddBinding("x", [], self.current_location)
    n = self.current_location.ConnectNew()
    v2 = self.prog.NewVariable()
    v2.AddBinding("y", {b}, n)
    # smoke test
    assert isinstance(debug.program_to_dot(self.prog, ignored=()), str)

  def testRootCauseVisible(self):
    v = self.prog.NewVariable()
    b = v.AddBinding("x", [], self.current_location)
    self.assertEqual(debug.root_cause(b, self.current_location), (None, None))

  def testRootCauseNotVisible(self):
    v = self.prog.NewVariable()
    b = v.AddBinding("x", [], self.current_location)
    n = self.current_location.ConnectNew()
    v.AddBinding("y", [], n)
    self.assertEqual(debug.root_cause(b, n), (b, n))

  def testSaveLoggingLevel(self):
    logging.root.setLevel(logging.INFO)
    self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.INFO)
    with debug.save_logging_level():
      logging.root.setLevel(logging.ERROR)
      self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.ERROR)
    self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.INFO)


if __name__ == "__main__":
  unittest.main()
