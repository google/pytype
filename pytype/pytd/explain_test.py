"""Test for the typegraph explanation mechanism."""

from pytype.pytd import cfg as typegraph
from pytype.pytd import explain
import unittest


class ExplainTest(unittest.TestCase):
  """Test explanations."""

  def setUp(self):
    # n1------->n2
    #  |        |
    #  v        v
    # n3------->n4
    # [n2] x = a; y = a
    # [n3] x = b; y = b
    # [n4] z = x & y
    self.p = typegraph.Program()
    self.n1 = self.p.NewCFGNode("n1")
    self.n2 = self.n1.ConnectNew("n2")
    self.n3 = self.n1.ConnectNew("n3")
    self.n4 = self.n2.ConnectNew("n4")
    self.n3.ConnectTo(self.n4)
    self.x = self.p.NewVariable("x")
    self.y = self.p.NewVariable("y")
    self.z = self.p.NewVariable("z")
    self.w = self.p.NewVariable("w")
    self.xa = self.x.AddBinding("a", source_set=[], where=self.n2)
    self.ya = self.y.AddBinding("a", source_set=[], where=self.n2)
    self.xb = self.x.AddBinding("b", source_set=[], where=self.n3)
    self.yb = self.y.AddBinding("b", source_set=[], where=self.n3)
    self.za = self.z.AddBinding(
        "a", source_set=[self.xa, self.ya], where=self.n4)
    self.zb = self.z.AddBinding(
        "b", source_set=[self.xb, self.yb], where=self.n4)
    self.zab = self.z.AddBinding("a&b")
    self.zab.AddOrigin(source_set=[self.xa, self.yb], where=self.n4)
    self.zab.AddOrigin(source_set=[self.xb, self.ya], where=self.n4)
    self.p.entrypoint = self.n1
    self.p.Freeze()

  def testValid(self):
    self.assertTrue(explain.Explain([self.xa, self.ya], self.n4))

  def testBadApple(self):
    # x = 'a' spoils y = 'b'
    self.assertFalse(explain.Explain([self.xa, self.yb], self.n4))

  def testConflicting(self):
    self.assertFalse(explain.Explain([self.xa, self.xb], self.n4))

  def testBadSources(self):
    self.assertFalse(explain.Explain([self.zab], self.n4))

  def testUnordered(self):
    p = typegraph.Program()
    n0 = p.NewCFGNode("n0")
    n1 = n0.ConnectNew("n1")
    x = p.NewVariable("x")
    y = p.NewVariable("y")
    x0 = x.AddBinding(0, [], n0)
    x1 = x.AddBinding(1, [], n0)
    x2 = x.AddBinding(2, [], n0)
    y0 = y.AddBinding(0, [x0], n1)
    y1 = y.AddBinding(1, [x1], n1)
    y2 = y.AddBinding(2, [x2], n1)
    p.entrypoint = n0
    p.Freeze()
    self.assertTrue(explain.Explain([x0], n0))
    self.assertTrue(explain.Explain([x1], n0))
    self.assertTrue(explain.Explain([x2], n0))
    self.assertTrue(explain.Explain([y0], n1))
    self.assertTrue(explain.Explain([y1], n1))
    self.assertTrue(explain.Explain([y2], n1))

if __name__ == "__main__":
  unittest.main()
