"""Tests for utils.py."""

import logging
import textwrap


from pytype import debug
from pytype.typegraph import cfg

import unittest


log = logging.getLogger(__name__)


class Node(object):
  """A graph node, for testing topological sorting."""

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

  def testTraceLogLevel(self):
    log.trace("hello world")

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
    assert isinstance(s, str)


if __name__ == "__main__":
  unittest.main()
